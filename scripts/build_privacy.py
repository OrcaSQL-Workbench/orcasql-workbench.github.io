import argparse
from dataclasses import dataclass, field
from datetime import date
import hashlib
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit


PROJECT = Path(__file__).resolve().parent.parent
SOURCE = PROJECT / "privacy" / "policy-zh-Hans.json"
OUTPUT = PROJECT / "site" / "privacy"
POLICY_FILE = "policy-zh-Hans.txt"
FILES = {"index.html", POLICY_FILE, "manifest.json"}
POLICY_URL = "https://orcasql-workbench.github.io/privacy/versions/"
MANIFEST_FIELDS = {"schemaVersion", "locale", "effectiveDate", "policyFile", "sha256", "headings", "policyUrl"}
MAX_POLICY_BYTES = 65536
MAX_MANIFEST_BYTES = 32768
FORBIDDEN_TEXT = re.compile(r"[\r\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ud800-\udfff\ufffd\ufeff]")
VOID_ELEMENTS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


def object_fields(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= value.keys() or value.keys() - set(required) - set(optional):
        raise ValueError(f"Expected policy fields {sorted(required)} with optional {sorted(optional)}.")


def check_characters(value):
    if FORBIDDEN_TEXT.search(value):
        raise ValueError("Policy text contains forbidden characters or malformed Unicode.")


def text(value):
    if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value.splitlines()) != 1 or re.search(r"[\x00-\x1f\x7f]", value):
        raise ValueError("Policy text must be a nonempty, single-line string without surrounding whitespace.")
    check_characters(value)
    return value


def entries(value):
    if not isinstance(value, list) or not value:
        raise ValueError("Policy collections must be nonempty lists.")
    return value


def policy_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("Policy effectiveDate must use YYYY-MM-DD.")
    return date.fromisoformat(value)


def json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate policy JSON field: {key}")
        result[key] = value
    return result


def invalid_constant(value):
    raise ValueError(f"Invalid JSON constant: {value}")


def load_json(content):
    return json.loads(content.decode("utf-8"), object_pairs_hook=json_object, parse_constant=invalid_constant)


@dataclass
class Element:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)

    def descendants(self, tag=None):
        for child in self.children:
            if isinstance(child, Element):
                if tag is None or child.tag == tag:
                    yield child
                yield from child.descendants(tag)

    def raw_text(self, destinations=False):
        value = "".join(child.raw_text(destinations) if isinstance(child, Element) else child for child in self.children)
        if destinations and self.tag == "a":
            href = self.attrs["href"]
            label = self.text()
            if href != "mailto:" + label or not re.fullmatch(r"[^@\s:?#,;]+@[^@\s:?#,;]+", label):
                value += f" ({href})"
        return value

    def text(self, destinations=False):
        return re.sub(r"\s*\n\s*", "", self.raw_text(destinations)).strip()


class Markup(HTMLParser):
    def __init__(self, content, fragment=False):
        super().__init__(convert_charrefs=True)
        self.root = Element("document")
        self.stack = [self.root]
        self.fragment = fragment
        self.feed(content)
        self.close()
        if len(self.stack) != 1:
            raise ValueError(f"Unclosed policy HTML element: {self.stack[-1].tag}")

    def handle_starttag(self, tag, attributes):
        if len(dict(attributes)) != len(attributes):
            raise ValueError("Duplicate policy HTML attributes.")
        node = Element(tag, dict(attributes))
        self.stack[-1].children.append(node)
        if tag not in VOID_ELEMENTS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attributes):
        if tag not in VOID_ELEMENTS:
            raise ValueError(f"Unsupported self-closing policy element: {tag}")
        self.handle_starttag(tag, attributes)

    def handle_endtag(self, tag):
        if len(self.stack) == 1 or self.stack[-1].tag != tag:
            raise ValueError(f"Mismatched policy HTML closing tag: {tag}")
        self.stack.pop()

    def handle_data(self, data):
        self.stack[-1].children.append(data)

    def handle_comment(self, data):
        if self.fragment:
            raise ValueError("Policy inline HTML must not contain comments.")

    def handle_decl(self, decl):
        if self.fragment or decl.lower() != "doctype html":
            raise ValueError("Unsupported policy HTML declaration.")

    def handle_pi(self, data):
        raise ValueError("Policy HTML must not contain processing instructions.")

    def unknown_decl(self, data):
        raise ValueError("Unsupported policy HTML declaration.")


def inline(value):
    value = text(value)
    for reference in re.finditer(r"&#(?:[xX]([0-9a-fA-F]+)|([0-9]+));?", value):
        try:
            character = chr(int(reference[1], 16) if reference[1] is not None else int(reference[2]))
        except ValueError as error:
            raise ValueError("Policy inline character reference is not a Unicode scalar.") from error
        check_characters(character)
    fragment = Markup(value, fragment=True).root

    def render(node, in_link=False):
        if isinstance(node, str):
            check_characters(node)
            return escape(node, quote=False)
        if node.tag not in {"strong", "code", "a"}:
            raise ValueError(f"Unsupported policy inline element: {node.tag}")
        attributes = ""
        if node.tag == "a":
            if in_link or set(node.attrs) != {"href"} or not node.text():
                raise ValueError("Policy links need one href, readable text and no nested links.")
            href = text(node.attrs["href"])
            url = urlsplit(href)
            if url.scheme not in {"https", "mailto"} or (url.scheme == "https" and not url.netloc):
                raise ValueError(f"Unsupported policy link: {href}")
            attributes = f' href="{escape(href, quote=True)}"'
        elif node.attrs:
            raise ValueError(f"Unsupported attributes on policy {node.tag}.")
        content = "".join(render(child, in_link or node.tag == "a") for child in node.children)
        return f"<{node.tag}{attributes}>{content}</{node.tag}>"

    if not fragment.text():
        raise ValueError("Policy inline HTML must contain readable text.")
    return "".join(render(child) for child in fragment.children)


def render_block(block):
    if not isinstance(block, dict):
        raise ValueError("Policy blocks must be objects.")
    kind = block.get("type")
    if kind == "paragraph":
        object_fields(block, {"type", "html"}, {"class"})
        if "class" in block and block["class"] != "contact":
            raise ValueError("Unsupported policy paragraph class.")
        attributes = ' class="contact"' if "class" in block else ""
        return f"      <p{attributes}>{inline(block['html'])}</p>"
    if kind == "heading":
        object_fields(block, {"type", "text"})
        return f"      <h3>{escape(text(block['text']))}</h3>"
    if kind == "list":
        object_fields(block, {"type", "items"})
        items = "\n".join(f"        <li>{inline(item)}</li>" for item in entries(block["items"]))
        return f"      <ul>\n{items}\n      </ul>"
    if kind == "table":
        object_fields(block, {"type", "caption", "headers", "rows"})
        headers = entries(block["headers"])
        if len(headers) < 2:
            raise ValueError("Policy tables need at least two columns.")
        columns = "".join(f'<th scope="col">{inline(header)}</th>' for header in headers)
        rows = []
        for row in entries(block["rows"]):
            if not isinstance(row, list) or len(row) != len(headers):
                raise ValueError("Policy table rows must match the header column count.")
            cells = f'<th scope="row">{inline(row[0])}</th>'
            cells += "".join(f"<td>{inline(cell)}</td>" for cell in row[1:])
            rows.append(f"          <tr>{cells}</tr>")
        body = "\n".join(rows)
        return (
            f"      <table>\n        <caption>{inline(block['caption'])}</caption>\n"
            f"        <thead>\n          <tr>{columns}</tr>\n        </thead>\n"
            f"        <tbody>\n{body}\n        </tbody>\n      </table>"
        )
    raise ValueError(f"Unsupported policy block type: {kind}")


def render_page(source, *, theme=True):
    object_fields(source, {"schemaVersion", "locale", "title", "description", "effectiveDate", "lead", "sections"})
    if type(source["schemaVersion"]) is not int or source["schemaVersion"] != 1 or source["locale"] != "zh-Hans":
        raise ValueError("Unsupported policy schemaVersion or locale.")
    effective = policy_date(source["effectiveDate"])
    title = escape(text(source["title"]))
    description = escape(text(source["description"]), quote=True)
    lead = inline(source["lead"])
    sections, navigation = [], []
    identifiers = {"policy"}
    for section in entries(source["sections"]):
        object_fields(section, {"id", "title", "navigationTitle", "blocks"})
        identifier = text(section["id"])
        if not re.fullmatch(r"[a-z][a-z0-9-]*", identifier) or identifiers & {identifier, identifier + "-title"}:
            raise ValueError(f"Invalid or duplicate policy section id: {identifier}")
        identifiers.update({identifier, identifier + "-title"})
        heading = escape(text(section["title"]))
        label = escape(text(section["navigationTitle"]))
        navigation.append(f'        <li><a href="#{identifier}">{label}</a></li>')
        body = "\n".join(render_block(block) for block in entries(section["blocks"]))
        sections.append(
            f'    <section id="{identifier}" tabindex="-1" aria-labelledby="{identifier}-title">\n'
            f'      <h2 id="{identifier}-title">{heading}</h2>\n{body}\n    </section>'
        )
    chapter_links = "\n".join(navigation)
    body = "\n\n".join(sections)
    script_permission = " script-src 'self';" if theme else ""
    theme_script = '  <script src="/assets/theme.js"></script>\n' if theme else ""
    theme_controls = """
    <div class="theme-settings" data-theme-settings hidden>
      <label>主题
        <select data-theme-control>
          <option value="system">跟随系统</option>
          <option value="light">浅色</option>
          <option value="dark">深色</option>
        </select>
      </label>
      <span class="theme-status" data-theme-status role="status" hidden>当前页面已切换，但浏览器未能保存主题。</span>
    </div>
  """ if theme else ""
    return f"""<!doctype html>
<!-- Generated by scripts/build_privacy.py; edit privacy/policy-zh-Hans.json. -->
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Content-Security-Policy"
    content="default-src 'none';{script_permission} img-src 'self'; style-src 'self'; base-uri 'none'; form-action 'none'; object-src 'none'">
  <meta name="description" content="{description}">
  <title>{title}</title>
{theme_script}  <link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="/assets/privacy.css">
</head>
<body>
  <a class="skip-link" href="#policy">跳转到隐私政策正文</a>
  <div class="site-header"><a href="/">← 返回首页</a><span>OrcaSQL Workbench</span>{theme_controls}</div>
  <main id="policy" tabindex="-1">
    <header>
      <h1>{title}</h1>
      <dl class="metadata">
        <div><dt>生效日期</dt><dd><time datetime="{effective.isoformat()}">{effective.year}年{effective.month}月{effective.day}日</time></dd></div>
      </dl>
      <p class="lead">{lead}</p>
    </header>

    <nav aria-label="隐私政策章节">
      <p>章节导航</p>
      <ul>
{chapter_links}
      </ul>
    </nav>

{body}

    <footer>
      <p>OrcaSQL Workbench · 隐私政策</p>
    </footer>
  </main>
</body>
</html>
"""


def policy_main(html):
    document = Markup(html).root
    mains = list(document.descendants("main"))
    if len(mains) != 1 or mains[0].attrs.get("id") != "policy":
        raise ValueError("Policy HTML needs exactly one main#policy.")
    return mains[0]


def policy_links(html):
    def collect(node):
        if node.tag in {"nav", "footer"}:
            return
        if node.tag == "a":
            yield node.attrs.get("href"), node.text()
        for child in node.children:
            if isinstance(child, Element):
                yield from collect(child)

    return list(collect(policy_main(html)))


def policy_content(html, destinations=True):
    main = policy_main(html)
    paragraphs, headings = [], []

    def collect(node):
        if node.tag in {"nav", "footer"}:
            return
        if node.tag in {"h1", "h2", "h3", "p"}:
            value = text(node.text(destinations))
            paragraphs.append(value)
            if node.tag != "p":
                headings.append(value)
        elif node.tag == "dl":
            paragraphs.append("\n".join(text(item.text(destinations)) for item in node.descendants() if item.tag in {"dt", "dd"}))
        elif node.tag == "table":
            header = [text(item.text(destinations)) for item in node.descendants("caption")]
            for group in node.descendants("thead"):
                header.extend(text(item.text(destinations)) for item in group.descendants("th"))
            paragraphs.append("\n".join(header))
            for group in node.descendants("tbody"):
                for row in group.descendants("tr"):
                    paragraphs.append("\n".join(text(cell.text(destinations)) for cell in row.children if isinstance(cell, Element)))
        elif node.tag == "ul":
            paragraphs.append("\n".join(text(item.text(destinations)) for item in node.descendants("li")))
        elif node.tag in {"main", "header", "section"}:
            for child in node.children:
                if isinstance(child, Element):
                    collect(child)
                elif child.strip():
                    raise ValueError("Policy text must be inside a supported semantic block.")
        else:
            raise ValueError(f"Unsupported policy content element: {node.tag}")

    collect(main)
    if not headings or len(set(headings)) != len(headings):
        raise ValueError("Policy headings must be nonempty and unique.")
    times = list(main.descendants("time"))
    if len(times) != 1:
        raise ValueError("Policy HTML needs exactly one effective date.")
    effective = policy_date(times[0].attrs.get("datetime")).isoformat()
    return ("\n\n".join(paragraphs) + "\n").encode("utf-8"), headings, effective


def check_text_bytes(content):
    if len(content) > MAX_POLICY_BYTES:
        raise ValueError(f"Policy TXT exceeds {MAX_POLICY_BYTES} UTF-8 bytes.")
    try:
        value = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Policy TXT must be valid UTF-8.") from error
    check_characters(value)
    if not value or not value.endswith("\n") or value.endswith("\n\n"):
        raise ValueError("Policy TXT must be nonempty with exactly one final LF.")
    return value


def check_text_structure(value, headings):
    paragraphs = value[:-1].split("\n\n")
    if headings[0] != paragraphs[0]:
        raise ValueError("Policy TXT must start with its document title.")
    previous = -1
    for heading in headings:
        positions = [index for index, paragraph in enumerate(paragraphs) if paragraph == heading]
        if len(positions) != 1 or positions[0] <= previous:
            raise ValueError("Policy headings must appear exactly once as complete paragraphs in order.")
        previous = positions[0]
    if previous >= len(paragraphs) - 1:
        raise ValueError("Policy TXT must contain body after the final heading.")


def render_policy_files(source):
    html = render_page(source)
    content, headings, effective = policy_content(html)
    value = check_text_bytes(content)
    revision = hashlib.sha256(content).hexdigest()
    manifest = {
        "schemaVersion": 1,
        "locale": "zh-Hans",
        "effectiveDate": effective,
        "policyFile": POLICY_FILE,
        "sha256": revision,
        "headings": headings,
        "policyUrl": POLICY_URL + revision + "/",
    }
    check_manifest(manifest, revision)
    check_text_structure(value, headings)
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if len(manifest_bytes) > MAX_MANIFEST_BYTES:
        raise ValueError(f"Policy manifest exceeds {MAX_MANIFEST_BYTES} UTF-8 bytes.")
    return revision, {
        "index.html": html.encode("utf-8"),
        POLICY_FILE: content,
        "manifest.json": manifest_bytes,
    }


def policy_files(source):
    return render_policy_files(load_json(source.read_bytes()))


def check_manifest(manifest, revision):
    object_fields(manifest, MANIFEST_FIELDS)
    if type(manifest["schemaVersion"]) is not int or manifest["schemaVersion"] != 1 or manifest["locale"] != "zh-Hans":
        raise ValueError("Unsupported policy manifest schemaVersion or locale.")
    policy_date(manifest["effectiveDate"])
    headings = entries(manifest["headings"])
    if not 2 <= len(headings) <= 64:
        raise ValueError("Policy manifest must contain 2 to 64 headings.")
    if any(isinstance(heading, str) and len(heading.encode("utf-16-le")) > 400 for heading in headings):
        raise ValueError("Policy headings must not exceed 200 UTF-16 code units.")
    if any(text(heading) != heading for heading in headings) or len(set(headings)) != len(headings):
        raise ValueError("Manifest headings must be nonempty and unique.")
    if manifest["policyFile"] != POLICY_FILE or manifest["sha256"] != revision or manifest["policyUrl"] != POLICY_URL + revision + "/":
        raise ValueError("Policy manifest does not match its immutable revision.")


def check_archives(destination):
    versions = destination / "versions"
    if versions.is_symlink() or (versions.exists() and not versions.is_dir()):
        raise ValueError("Policy versions must be a regular directory.")
    if not versions.exists():
        return
    for folder in sorted(versions.iterdir()):
        if folder.is_symlink() or not folder.is_dir() or not re.fullmatch(r"[a-f0-9]{64}", folder.name):
            raise ValueError(f"Unexpected policy archive path: {folder}")
        if {path.name for path in folder.iterdir()} != FILES:
            raise ValueError(f"Immutable policy archive has missing or unexpected files: {folder.name}")
        if any(path.is_symlink() or not path.is_file() for path in folder.iterdir()):
            raise ValueError(f"Immutable policy archive needs regular files: {folder.name}")
        content = (folder / POLICY_FILE).read_bytes()
        value = check_text_bytes(content)
        if hashlib.sha256(content).hexdigest() != folder.name:
            raise ValueError(f"Immutable policy archive TXT hash mismatch: {folder.name}")
        if b"\r" in content or content.startswith(b"\xef\xbb\xbf") or not content.endswith(b"\n") or content.endswith(b"\n\n"):
            raise ValueError(f"Immutable policy archive TXT must be UTF-8/LF with one final newline: {folder.name}")
        manifest_bytes = (folder / "manifest.json").read_bytes()
        if len(manifest_bytes) > MAX_MANIFEST_BYTES:
            raise ValueError(f"Policy manifest exceeds {MAX_MANIFEST_BYTES} UTF-8 bytes: {folder.name}")
        manifest = load_json(manifest_bytes)
        check_manifest(manifest, folder.name)
        check_text_structure(value, manifest["headings"])
        html = (folder / "index.html").read_text(encoding="utf-8")
        rendered, headings, effective = policy_content(html)
        # Keep pre-destination v1 archives byte-identical; new exports always include destinations.
        legacy = rendered != content and policy_content(html, destinations=False)[0] == content
        if (rendered != content and not legacy) or headings != manifest["headings"] or effective != manifest["effectiveDate"]:
            raise ValueError(f"Immutable policy archive HTML/TXT/manifest content mismatch: {folder.name}")


def check_archive_history(destination, base):
    try:
        relative = (destination.resolve() / "versions").relative_to(PROJECT).as_posix()
    except ValueError as error:
        raise ValueError("An archive baseline requires an output directory inside this repository.") from error
    def git(*arguments):
        result = subprocess.run(["git", *arguments], cwd=PROJECT, capture_output=True)
        if result.returncode:
            raise ValueError("Cannot read complete policy archive history: " + result.stderr.decode("utf-8", errors="replace").strip())
        return result.stdout

    if git("rev-parse", "--is-shallow-repository").strip() != b"false":
        raise ValueError("Complete policy archive history is required; use an unshallow checkout (CI fetch-depth: 0).")
    inventory, visited = {}, set()
    for reference in (base, "HEAD"):
        resolved = git("rev-parse", "--verify", "--end-of-options", reference + "^{commit}").decode().strip()
        if resolved in visited:
            continue
        visited.add(resolved)
        changes = git(
            "log", "--first-parent", "--full-history", "--reverse", "--format=", "--raw",
            "--no-abbrev", "--no-renames", "--no-ext-diff", "--no-textconv",
            "--root", "--diff-merges=first-parent", "-z", resolved, "--", relative,
        ).split(b"\0")
        for index in range(0, len(changes) - 1, 2):
            metadata, name = changes[index].strip(), changes[index + 1].decode("utf-8")
            if not metadata.startswith(b":") or len(metadata.split()) != 5:
                raise ValueError("Cannot read complete policy archive history: invalid Git change record.")
            _, mode, _, blob, status = metadata.split()
            if status != b"D":
                inventory.setdefault(name, (mode, blob.decode()))
    failures = []
    for name, (mode, blob) in inventory.items():
        path = PROJECT / name
        if mode not in {b"100644", b"100755"} or path.is_symlink() or not path.is_file():
            failures.append(f"Missing or invalid historical policy archive: {name}")
            continue
        content = path.read_bytes()
        digest = hashlib.sha1 if len(blob) == 40 else hashlib.sha256
        actual = digest(f"blob {len(content)}\0".encode() + content).hexdigest()
        if actual != blob:
            failures.append(f"Historical policy archive bytes changed; restore the original: {name}")
    if failures:
        raise ValueError("Policy archive history must retain its original files:\n" + "\n".join(failures))


def build(source=SOURCE, destination=OUTPUT, check=False, archive_base=None):
    source, destination = Path(source), Path(destination)
    data = load_json(source.read_bytes())
    revision, files = render_policy_files(data)
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        raise ValueError("Policy output must be a regular directory.")
    for name in files:
        path = destination / name
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ValueError(f"Policy output must be a regular file: {path}")
    if archive_base is not None:
        check_archive_history(destination, archive_base)
    check_archives(destination)
    archive = destination / "versions" / revision
    archive_files = {**files, "index.html": render_page(data, theme=False).encode("utf-8")}
    if archive.exists():
        archive_files = {name: (archive / name).read_bytes() for name in files}
        if archive_files[POLICY_FILE] != files[POLICY_FILE] or load_json(archive_files["manifest.json"]) != load_json(files["manifest.json"]):
            raise ValueError(f"Immutable policy revision {revision} already exists with different policy metadata; do not overwrite it.")
        if policy_links(archive_files["index.html"].decode("utf-8")) != policy_links(files["index.html"].decode("utf-8")):
            raise ValueError(f"Immutable policy revision {revision} already exists with different policy links; do not overwrite it.")
    expected = {destination / name: content for name, content in files.items()}
    expected.update({archive / name: content for name, content in archive_files.items()})
    if check:
        stale = [str(path) for path, content in expected.items() if not path.is_file() or path.read_bytes() != content]
        if stale:
            raise ValueError("Missing or stale generated policy files; run python scripts\\build_privacy.py:\n" + "\n".join(stale))
        return revision
    if not archive.exists():
        archive.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".policy-", dir=archive.parent) as temporary:
            staged = Path(temporary)
            for name, content in archive_files.items():
                (staged / name).write_bytes(content)
            staged.rename(archive)
    for name, content in files.items():
        path = destination / name
        if not path.exists() or path.read_bytes() != content:
            path.write_bytes(content)
    return revision


def main():
    parser = argparse.ArgumentParser(description="Generate privacy HTML/TXT/manifests and append immutable revisions.")
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--check", action="store_true", help="Check all generated files offline without writing.")
    parser.add_argument("--archive-base", help="Also retain the full first-parent archive history of this existing Git commit.")
    arguments = parser.parse_args()
    baseline = arguments.archive_base
    if baseline is None and arguments.output.resolve() == OUTPUT:
        baseline = "HEAD"
    revision = build(arguments.source, arguments.output, arguments.check, baseline)
    print(f"{'Checked' if arguments.check else 'Built'} privacy policy revision {revision}.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
