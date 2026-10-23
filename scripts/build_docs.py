import argparse
from dataclasses import dataclass
from html import escape
import json
from pathlib import Path, PurePosixPath
import re
import sys
import unicodedata
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from markdown_it import MarkdownIt


PROJECT = Path(__file__).resolve().parent.parent
REPOSITORY_URL = "https://github.com/OrcaSQL-Workbench/orcasql-workbench.github.io"
ASSET_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
SITE_MANIFEST = ".docs-generated-manifest.json"
WIKI_MANIFEST = ".docs-sync-manifest.json"


@dataclass(frozen=True)
class Manual:
    product: str
    title: str
    source_path: str
    site_path: str
    wiki_repository: str

    @property
    def source(self):
        return PROJECT.joinpath(*self.source_path.split("/"))

    @property
    def site_output(self):
        return PROJECT / "site" / self.site_path.strip("/")

    @property
    def repository_url(self):
        return "https://github.com/" + self.wiki_repository

    @property
    def wiki_url(self):
        return self.repository_url + "/wiki"


MANUALS = {
    "workbench": Manual(
        "OrcaSQL Workbench", "用户文档", "docs", "/docs/",
        "OrcaSQL-Workbench/orcasql-workbench.github.io",
    ),
    "arkdb": Manual(
        "ArkDB", "ArkDB 开发者手册", "docs/arkdb", "/arkdb/",
        "OrcaSQL-Workbench/ArkDB",
    ),
}


def code_chunks(text):
    position = 0
    while position < len(text):
        opening = re.search(r"(?<!\\)`+", text[position:])
        if opening is None:
            yield False, text[position:]
            return
        start = position + opening.start()
        end = position + opening.end()
        length = end - start
        closing = next(
            (match for match in re.finditer(r"`+", text[end:])
             if match.end() - match.start() == length),
            None,
        )
        if closing is None:
            yield False, text[position:end]
            position = end
            continue
        close = end + closing.end()
        if start > position:
            yield False, text[position:start]
        yield True, text[start:close]
        position = close


@dataclass(frozen=True)
class Document:
    source: str
    slug: str
    title: str
    content: str
    site_path: str = "/docs/"

    @property
    def site_url(self):
        return self.site_path + (self.slug + "/" if self.slug else "")

    @property
    def wiki_name(self):
        return self.title if self.slug else "Home"

    @property
    def wiki_route(self):
        return quote(self.wiki_name.replace(" ", "-"), safe="")


def safe_path(root, relative):
    decoded = unquote(relative)
    parts = PurePosixPath(decoded).parts
    if not parts or PurePosixPath(decoded).is_absolute() or "\\" in decoded:
        raise ValueError(f"Invalid relative documentation path: {relative}")
    if any(part.casefold() in ("", ".", "..", ".git") for part in parts):
        raise ValueError(f"Unsafe documentation path: {relative}")
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"Documentation paths must not contain symlinks: {relative}")
    if not current.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Documentation path leaves its directory: {relative}")
    return current


class Documentation:
    def __init__(self, source, manual=MANUALS["workbench"]):
        self.source = source.resolve()
        self.manual = manual
        manifest = json.loads((self.source / "navigation.json").read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or manifest.get("version") != 1:
            raise ValueError("Unsupported documentation navigation manifest.")
        entries = manifest.get("pages")
        if not isinstance(entries, list) or not entries:
            raise ValueError("Documentation navigation must contain pages.")
        self.pages = []
        sources, slugs, wiki_names = set(), set(), set()
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {"source", "slug", "title"}:
                raise ValueError("Each page needs exactly source, slug and title.")
            filename, slug, title = entry["source"], entry["slug"], entry["title"]
            if not all(isinstance(value, str) for value in (filename, slug, title)):
                raise ValueError("Documentation page properties must be strings.")
            if not filename.endswith(".md") or "/" in filename:
                raise ValueError(f"Page sources must be top-level Markdown files: {filename}")
            if slug and not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
                raise ValueError(f"Invalid page slug: {slug}")
            if not title.strip() or title != title.strip() or title.startswith((".", "-")):
                raise ValueError(f"Invalid documentation title: {title}")
            if re.search(r'[\\/:*?"<>|\r\n]', title):
                raise ValueError(f"Title cannot be used as a Wiki filename: {title}")
            content = safe_path(self.source, filename).read_text(encoding="utf-8")
            page = Document(filename, slug, title, content, manual.site_path)
            if filename in sources or slug in slugs or page.wiki_name.casefold() in wiki_names:
                raise ValueError(f"Duplicate documentation source, slug or Wiki title: {filename}")
            sources.add(filename)
            slugs.add(slug)
            wiki_names.add(page.wiki_name.casefold())
            self.pages.append(page)
        if self.pages[0].slug or sum(page.slug == "" for page in self.pages) != 1:
            raise ValueError("The first page must be the only documentation homepage.")
        unlisted = {path.name for path in self.source.glob("*.md")} - sources
        if unlisted:
            raise ValueError(f"Markdown pages missing from navigation: {', '.join(sorted(unlisted))}")
        self.by_source = {page.source: page for page in self.pages}

    def link(self, page, destination, surface, image=False):
        url = urlsplit(destination)
        if url.scheme in ("https", "mailto") and not image:
            return destination
        if url.scheme or url.netloc:
            raise ValueError(f"{page.source}: unsupported documentation URL: {destination}")
        if not url.path:
            if image:
                raise ValueError(f"{page.source}: image needs a local asset path.")
            return destination
        if url.query:
            raise ValueError(f"{page.source}: local documentation links must not use queries.")
        path = unquote(url.path)
        if path in self.by_source and not image:
            target = self.by_source[path]
            route = target.site_url if surface == "site" else target.wiki_route
        elif path.startswith("assets/"):
            asset = safe_path(self.source, path)
            if not asset.is_file() or asset.suffix.lower() not in ASSET_EXTENSIONS:
                raise ValueError(f"{page.source}: missing or unsupported image asset: {path}")
            route = (self.manual.site_path if surface == "site" else "") + quote(path, safe="/")
        else:
            raise ValueError(f"{page.source}: unknown document or asset: {destination}")
        return urlunsplit(("", "", route, "", url.fragment))

    def assets(self):
        files = {}
        assets = self.source / "assets"
        if assets.is_symlink():
            raise ValueError("The documentation asset directory must not be a symlink.")
        if assets.exists():
            for path in sorted(assets.rglob("*")):
                if path.is_symlink():
                    raise ValueError("Documentation image assets must not be symlinks.")
                if path.is_file():
                    relative = path.relative_to(self.source).as_posix()
                    safe_path(self.source, relative)
                    if path.suffix.lower() not in ASSET_EXTENSIONS:
                        raise ValueError(f"Unsupported documentation asset: {relative}")
                    files[relative] = path.read_bytes()
        return files

    def parsed(self, page):
        renderer = MarkdownIt("commonmark", {"html": False}).enable("table")
        environment = {}
        tokens = renderer.parse(page.content, environment)
        headings = [token for token in tokens if token.type == "heading_open" and token.tag == "h1"]
        if len(headings) != 1:
            raise ValueError(f"{page.source}: expected exactly one level-one heading.")
        heading = next(tokens[index + 1].content for index, token in enumerate(tokens)
                       if token.type == "heading_open" and token.tag == "h1")
        if heading != page.title:
            raise ValueError(f"{page.source}: first heading must match its navigation title.")
        return renderer, tokens, environment

    def html(self, page):
        renderer, tokens, environment = self.parsed(page)
        identifiers = {}
        for index, token in enumerate(tokens):
            if token.type == "heading_open":
                label = tokens[index + 1].content
                base = re.sub(r"[^\w\s-]", "", unicodedata.normalize("NFKC", label).lower())
                base = re.sub(r"\s+", "-", base.strip()) or "section"
                count = identifiers.get(base, 0)
                identifiers[base] = count + 1
                token.attrSet("id", base + (f"-{count}" if count else ""))
            for child in token.children or []:
                if child.type == "link_open":
                    child.attrSet("href", self.link(page, child.attrGet("href"), "site"))
                elif child.type == "image":
                    child.attrSet("src", self.link(page, child.attrGet("src"), "site", image=True))
        return renderer.renderer.render(tokens, renderer.options, environment)

    def wiki_markdown(self, page):
        _, tokens, environment = self.parsed(page)
        destinations = set()
        for token in tokens:
            for child in token.children or []:
                if child.type == "link_open":
                    destinations.add((child.attrGet("href"), False))
                elif child.type == "image":
                    destinations.add((child.attrGet("src"), True))
        replacements = {}
        for destination, image in destinations:
            replacement = self.link(page, destination, "wiki", image)
            if destination != replacement:
                replacements[destination] = replacement
        for reference in environment.get("references", {}).values():
            destination = reference["href"]
            replacement = self.link(page, destination, "wiki")
            if destination != replacement:
                replacements[destination] = replacement

        protected = set()
        for token in tokens:
            if token.type in ("fence", "code_block") and token.map:
                protected.update(range(token.map[0], token.map[1]))
        def rewrite(block):
            output = []
            for is_code, chunk in code_chunks(block):
                if not is_code:
                    for original, replacement in replacements.items():
                        escaped = re.escape(original)
                        chunk = re.sub(
                            rf"(?<!\\)(\]\(\s*<?){escaped}(?=>?(?:\s+[\"']|[)\s]))",
                            lambda match: match.group(1) + replacement,
                            chunk,
                        )
                        chunk = re.sub(
                            rf"^(\s{{0,3}}\[[^\]]+\]:\s*<?){escaped}(?=>?(?:\s|$))",
                            lambda match: match.group(1) + replacement,
                            chunk,
                            flags=re.MULTILINE,
                        )
                output.append(chunk)
            return "".join(output)

        output, block = [], []
        for index, line in enumerate(page.content.splitlines(keepends=True)):
            if index in protected:
                if block:
                    output.append(rewrite("".join(block)))
                    block.clear()
                output.append(line)
            else:
                block.append(line)
        if block:
            output.append(rewrite("".join(block)))
        return "".join(output)


def write_managed_files(root, files, manifest_name):
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    manifest = safe_path(root, manifest_name)
    previous = []
    if manifest.exists():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("files"), list):
            raise ValueError("Invalid generated-document manifest.")
        previous = data["files"]
        if not all(isinstance(name, str) for name in previous):
            raise ValueError("Invalid generated-document file list.")
    for relative in [*previous, *files]:
        safe_path(root, relative)
    for relative, content in files.items():
        destination = safe_path(root, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    for relative in set(previous) - files.keys():
        destination = safe_path(root, relative)
        if destination.exists():
            if not destination.is_file():
                raise ValueError(f"Generated document is not a regular file: {relative}")
            destination.unlink()
    manifest.write_text(json.dumps({"version": 1, "files": sorted(files)}, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    return sorted(set(previous) | files.keys() | {manifest_name})


def site_page(documentation, page):
    manual = documentation.manual
    navigation = "\n".join(
        f'<a href="{escape(item.site_url, quote=True)}"'
        + (' aria-current="page"' if item == page else "")
        + f">{escape(item.title)}</a>"
        for item in documentation.pages
    )
    body = documentation.html(page)
    source_url = REPOSITORY_URL + "/blob/main/" + manual.source_path + "/" + quote(page.source, safe="")
    wiki_url = manual.wiki_url + "/" + page.wiki_route
    workbench_current = ' aria-current="page"' if manual == MANUALS["workbench"] else ""
    arkdb_current = ' aria-current="page"' if manual == MANUALS["arkdb"] else ""
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{escape(page.title, quote=True)} · {escape(manual.title, quote=True)}">
  <title>{escape(page.title)} · {escape(manual.product)}</title>
  <link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="/assets/site.css">
</head>
<body>
  <a class="skip-link" href="#main">跳到文档正文</a>
  <header class="portal-header wrap">
    <a class="brand" href="/"><img class="brand-mark" src="/assets/favicon.svg" alt=""><span class="brand-text">OrcaSQL <span>Workbench</span></span></a>
    <nav aria-label="主要导航"><a href="/">首页</a><a href="/docs/"{workbench_current}>用户文档</a><a href="/arkdb/"{arkdb_current}>ArkDB 开发手册</a><a href="/privacy/">隐私政策</a></nav>
    <a class="repo-link" href="{manual.repository_url}" target="_blank" rel="noopener noreferrer">GitHub</a>
  </header>
  <main class="docs-main wrap" id="main" tabindex="-1">
    <details class="docs-navigation" open>
      <summary>{escape(manual.title)}</summary>
      <nav aria-label="{escape(manual.title, quote=True)}目录">{navigation}</nav>
    </details>
    <article class="docs-article">
      {body}
      <footer class="docs-footer"><a href="{source_url}" target="_blank" rel="noopener noreferrer">在仓库中修改此文档</a><a href="{wiki_url}" target="_blank" rel="noopener noreferrer">对应 Wiki 页面</a></footer>
    </article>
  </main>
</body>
</html>
"""


def build_site(source=PROJECT / "docs", destination=PROJECT / "site" / "docs", *, manual=MANUALS["workbench"]):
    documentation = Documentation(source, manual)
    files = documentation.assets()
    for page in documentation.pages:
        relative = (page.slug + "/" if page.slug else "") + "index.html"
        files[relative] = site_page(documentation, page).encode("utf-8")
    write_managed_files(destination, files, SITE_MANIFEST)
    return len(documentation.pages)


def export_wiki(source, destination, *, manual=MANUALS["workbench"]):
    documentation = Documentation(source, manual)
    files = documentation.assets()
    for page in documentation.pages:
        files[page.wiki_name + ".md"] = documentation.wiki_markdown(page).encode("utf-8")
    sidebar = f"# {manual.title}\n\n" + "\n".join(
        f"- [{page.title}]({page.wiki_route})" for page in documentation.pages
    ) + "\n"
    footer = (
        f"本文档由文档仓库的 `{manual.source_path}` 目录自动同步。请在文档仓库提交修改，"
        "直接编辑 Wiki 可能被下次同步覆盖。\n\n"
        f"[文档源码]({REPOSITORY_URL}/tree/main/{manual.source_path}) · "
        f"[网站文档](https://orcasql-workbench.github.io{manual.site_path})\n"
    )
    files["_Sidebar.md"] = sidebar.encode("utf-8")
    files["_Footer.md"] = footer.encode("utf-8")
    return write_managed_files(destination, files, WIKI_MANIFEST)


def main():
    parser = argparse.ArgumentParser(description="Build website docs or export the same Markdown to GitHub Wiki.")
    parser.add_argument("--manual", choices=("all", *MANUALS))
    parser.add_argument("--source", type=Path)
    parser.add_argument("--site-output", type=Path)
    parser.add_argument("--wiki-output", type=Path)
    arguments = parser.parse_args()
    if arguments.manual is None:
        arguments.manual = "workbench" if arguments.source or arguments.site_output else "all"
    if arguments.manual == "all" and (arguments.source or arguments.site_output):
        parser.error("--source and --site-output require a single --manual.")
    names = MANUALS if arguments.manual == "all" else (arguments.manual,)
    for name in names:
        manual = MANUALS[name]
        source = arguments.source or manual.source
        count = build_site(source, arguments.site_output or manual.site_output, manual=manual)
        if arguments.wiki_output:
            destination = arguments.wiki_output
            if arguments.manual == "all":
                destination = destination / name
            export_wiki(source, destination, manual=manual)
        print(f"Built {count} {name} pages from {manual.source_path}.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
