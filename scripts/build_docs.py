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
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name


PROJECT = Path(__file__).resolve().parent.parent
REPOSITORY_URL = "https://github.com/OrcaSQL-Workbench/orcasql-workbench.github.io"
ASSET_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
SITE_MANIFEST = ".docs-generated-manifest.json"
WIKI_MANIFEST = ".docs-sync-manifest.json"
CODE_LEXERS = {
    "typescript": "typescript",
    "json5": "json5",
    "powershell": "powershell",
    "sql": "mysql",
}


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


def highlight_code(code, language, _attributes):
    lexer_name = CODE_LEXERS.get(language)
    if lexer_name is None:
        return ""
    # Pygments strips leading BOMs and adds a newline to an unterminated final line.
    if code.startswith("\ufeff") or not code.endswith("\n"):
        return ""
    lexer = get_lexer_by_name(
        lexer_name, stripnl=False, stripall=False, ensurenl=False, tabsize=0,
    )
    return highlight(code, lexer, HtmlFormatter(nowrap=True, noclasses=False, classprefix="tok-"))


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
    section: str = ""
    in_navigation: bool = True

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
        version = manifest.get("version") if isinstance(manifest, dict) else None
        if type(version) is not int or version not in (1, 2):
            raise ValueError("Unsupported documentation navigation manifest.")
        entries = manifest.get("pages")
        if not isinstance(entries, list) or not entries:
            raise ValueError("Documentation navigation must contain pages.")
        self.pages = []
        sources, slugs, wiki_names = set(), set(), set()
        for entry in entries:
            required = {"source", "slug", "title"}
            optional = set()
            if version == 2:
                required.add("section")
                optional.add("nav")
            if not isinstance(entry, dict) or not required <= entry.keys() or entry.keys() - required - optional:
                raise ValueError("Invalid documentation page fields for this navigation version.")
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
            section = entry.get("section", "")
            if version == 2 and (
                not isinstance(section, str) or not section.strip() or section != section.strip()
                or "\n" in section or "\r" in section
            ):
                raise ValueError(f"Invalid navigation section for {filename}.")
            in_navigation = entry.get("nav", True)
            if not isinstance(in_navigation, bool):
                raise ValueError(f"Navigation visibility must be a boolean: {filename}")
            content = safe_path(self.source, filename).read_text(encoding="utf-8")
            page = Document(filename, slug, title, content, manual.site_path, section, in_navigation)
            if filename in sources or slug in slugs or page.wiki_name.casefold() in wiki_names:
                raise ValueError(f"Duplicate documentation source, slug or Wiki title: {filename}")
            sources.add(filename)
            slugs.add(slug)
            wiki_names.add(page.wiki_name.casefold())
            self.pages.append(page)
        if self.pages[0].slug or sum(page.slug == "" for page in self.pages) != 1:
            raise ValueError("The first page must be the only documentation homepage.")
        if not self.pages[0].in_navigation:
            raise ValueError("The documentation homepage must remain visible.")
        unlisted = {path.name for path in self.source.glob("*.md")} - sources
        if unlisted:
            raise ValueError(f"Markdown pages missing from navigation: {', '.join(sorted(unlisted))}")
        self.by_source = {page.source: page for page in self.pages}
        self.navigation = {}
        for page in self.pages:
            if page.in_navigation:
                self.navigation.setdefault(page.section, []).append(page)

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
        renderer.options["highlight"] = highlight_code
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
    groups = []
    for section, pages in documentation.navigation.items():
        links = "\n".join(
            f'<li><a href="{escape(item.site_url, quote=True)}"'
            + (' aria-current="page"' if item == page else "")
            + f">{escape(item.title)}</a></li>"
            for item in pages
        )
        if section:
            groups.append(
                f'<li><h2 class="docs-navigation-section">{escape(section)}</h2>\n'
                f"<ul>{links}</ul></li>"
            )
        else:
            groups.append(links)
    navigation = "<ul>" + "\n".join(groups) + "</ul>"
    navigation_class = "docs-navigation" + (" docs-navigation-grouped" if any(documentation.navigation) else "")
    main_class = "docs-main" + (" docs-main-wide" if manual == MANUALS["arkdb"] else "")
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
  <script src="/assets/theme.js"></script>
  <link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="/assets/site.css">
</head>
<body>
  <a class="skip-link" href="#main">跳到文档正文</a>
  <header class="portal-header wrap">
    <a class="brand" href="/"><img class="brand-mark" src="/assets/favicon.svg" alt=""><span class="brand-text">OrcaSQL <span>Workbench</span></span></a>
    <nav aria-label="主要导航">
      <a href="/">首页</a><a href="/docs/"{workbench_current}>用户文档</a><a href="/arkdb/"{arkdb_current}>ArkDB 开发手册</a><a href="/privacy/">隐私政策</a>
    </nav>
    <div class="header-tools">
      <div class="theme-settings" data-theme-settings hidden>
        <button class="theme-toggle" type="button" data-theme-control value="system" aria-label="主题：跟随系统；切换为浅色" title="主题：跟随系统；切换为浅色">
          <svg class="theme-icon-system" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8m-4-4v4"/></svg>
          <svg class="theme-icon-light" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/></svg>
          <svg class="theme-icon-dark" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20.5 13A8.5 8.5 0 0 1 11 3.5 8.5 8.5 0 1 0 20.5 13Z"/></svg>
        </button>
        <span class="theme-status" data-theme-status role="status" hidden>当前页面已切换，但浏览器未能保存主题。</span>
      </div>
      <a class="repo-link" href="{manual.repository_url}" target="_blank" rel="noopener noreferrer">GitHub</a>
    </div>
  </header>
  <main class="{main_class} wrap" id="main" tabindex="-1">
    <details class="{navigation_class}" open>
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
    sidebar = f"# {manual.title}\n\n" + "\n\n".join(
        (f"## {section}\n\n" if section else "")
        + "\n".join(f"- [{page.title}]({page.wiki_route})" for page in pages)
        for section, pages in documentation.navigation.items()
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
