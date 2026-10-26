from collections import Counter
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit
import sys

from build_privacy import VOID_ELEMENTS, build as build_policy


SITE = Path(__file__).resolve().parent.parent / "site"
PAGES_PATH = "/"
ARKDB_VIEWER = "arkdb/architecture/explore/index.html"
ARKDB_VIEWER_ROUTE = "/arkdb/architecture/explore/"
ARKDB_VIEWER_CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; font-src 'self' data:; media-src blob:; "
    "connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'"
)


class Page(HTMLParser):
    def __init__(self, path):
        super().__init__(convert_charrefs=True)
        self.path = path
        self.ids = Counter()
        self.references = []
        self.title = []
        self.in_title = False
        self.lang = None
        self.viewport = False
        self.doctype = False
        self.h1_count = 0
        self.main_count = 0
        self.scripts = []
        self.active_script = None
        self.parents = []
        self.base_elements = 0
        self.event_handlers = []
        self.theme_controls = 0
        self.theme_settings = []
        self.theme_buttons = []
        self.viewer_theme_buttons = []
        self.viewer_surfaces = []
        self.iframes = []
        self.csp = []
        self.feed(path.read_text(encoding="utf-8"))
        self.close()

    def handle_decl(self, decl):
        self.doctype = decl.lower() == "doctype html"

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "base":
            self.base_elements += 1
        if attrs.get("id"):
            self.ids[attrs["id"]] += 1
        if tag == "html":
            self.lang = attrs.get("lang")
        if tag == "meta" and attrs.get("name") == "viewport":
            self.viewport = "width=device-width" in attrs.get("content", "")
        if tag == "meta" and attrs.get("http-equiv", "").lower() == "content-security-policy":
            self.csp.append(attrs.get("content", ""))
        if tag == "title":
            self.in_title = True
        if tag == "h1":
            self.h1_count += 1
        if tag == "main":
            self.main_count += 1
        if tag == "script":
            self.active_script = {
                "attributes": attributes, "content": "",
                "head": self.parents == ["html", "head"], "self_closing": False,
                "parents": tuple(self.parents),
            }
            self.scripts.append(self.active_script)
        self.event_handlers.extend(name for name in attrs if name.startswith("on"))
        if "data-theme-settings" in attrs:
            self.theme_settings.append("hidden" in attrs)
        if "data-theme-control" in attrs:
            self.theme_controls += 1
            self.theme_buttons.append(
                tag == "button" and attrs.get("type") == "button"
                and attrs.get("value") == "system" and bool(attrs.get("aria-label"))
                and "nav" not in self.parents
            )
        if attrs.get("id") == "btn-theme":
            self.viewer_theme_buttons.append(
                tag == "button" and attrs.get("type") == "button" and bool(attrs.get("aria-label"))
            )
        for surface in ("toolbar", "diagram-container", "reader-rail"):
            if surface in attrs.get("class", "").split():
                self.viewer_surfaces.append((surface, "inert" in attrs))
        if tag == "iframe":
            self.iframes.append({
                "attributes": attributes, "parents": tuple(self.parents), "self_closing": False,
            })
        for attribute in ("href", "src"):
            if attrs.get(attribute):
                self.references.append(attrs[attribute])
        if tag not in VOID_ELEMENTS:
            self.parents.append(tag)

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag == "script":
            self.active_script = None
        for index in range(len(self.parents) - 1, -1, -1):
            if self.parents[index] == tag:
                del self.parents[index:]
                break

    def handle_startendtag(self, tag, attributes):
        self.handle_starttag(tag, attributes)
        if tag == "script":
            self.active_script["self_closing"] = True
        if tag == "iframe":
            self.iframes[-1]["self_closing"] = True
        self.handle_endtag(tag)

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)
        if self.active_script is not None:
            self.active_script["content"] += data


def script_errors(page, *, archived=False, viewer=False):
    failures = []
    if page.event_handlers:
        failures.append("inline event handlers are not allowed")
    if page.base_elements:
        failures.append("base elements must not change the local theme script's origin")
    if archived:
        if page.scripts or page.theme_controls or page.theme_settings:
            failures.append("historical policy pages must remain script-free without theme controls")
        return failures
    if viewer:
        expected = [
            ([("src", ARKDB_VIEWER_ROUTE + "init.js")], ("html", "head")),
            ([("id", "archify-source-evidence-data"), ("type", "application/json")],
             ("html", "body", "main")),
            ([("id", "archify-i18n-data"), ("type", "application/json")],
             ("html", "body", "main")),
            ([("src", ARKDB_VIEWER_ROUTE + "viewer.js")], ("html", "body")),
        ]
        if len(page.scripts) != len(expected):
            failures.append("the architecture viewer requires its exact local scripts and inert data blocks")
        for script, (attributes, parents) in zip(page.scripts, expected):
            if (script["attributes"] != attributes or script["parents"] != parents
                    or script["self_closing"]):
                failures.append("only the approved architecture viewer scripts and data are allowed")
                continue
            if attributes[0][0] == "src":
                if script["content"].strip():
                    failures.append("architecture viewer executable scripts must be external and empty")
            else:
                try:
                    data = json.loads(script["content"])
                except ValueError:
                    failures.append("architecture viewer data blocks must contain valid JSON objects")
                else:
                    if not isinstance(data, dict):
                        failures.append("architecture viewer data blocks must contain JSON objects")
        if page.csp != [ARKDB_VIEWER_CSP]:
            failures.append("the architecture viewer requires its restrictive local-resource CSP")
        if (page.viewer_theme_buttons != [True] or page.theme_controls
                or page.theme_settings):
            failures.append("expected one labelled architecture viewer theme button")
        if sorted(page.viewer_surfaces) != [
                ("diagram-container", True), ("reader-rail", True), ("toolbar", True)]:
            failures.append("architecture viewer controls must remain inert until initialization")
        return failures
    if len(page.scripts) != 1:
        failures.append("expected exactly one approved local theme script")
    for script in page.scripts:
        if (script["attributes"] != [("src", "/assets/theme.js")] or script["content"].strip()
                or not script["head"] or script["self_closing"]):
            failures.append("only an empty head script with src=\"/assets/theme.js\" is allowed")
    if (page.theme_controls != 1 or page.theme_settings != [True]
            or page.theme_buttons != [True]):
        failures.append("expected one initially hidden labelled theme button outside navigation")
    return failures


def frame_errors(page, *, architecture=False):
    if not architecture:
        return ["iframes are allowed only on the ArkDB architecture manual page"] if page.iframes else []
    expected = [
        ("class", "docs-diagram-frame"), ("src", ARKDB_VIEWER_ROUTE),
        ("title", "ArkDB 交互架构图"), ("loading", "lazy"),
        ("referrerpolicy", "no-referrer"),
        ("allow", "clipboard-write; fullscreen; camera 'none'; microphone 'none'; geolocation 'none'"),
        ("allowfullscreen", None),
    ]
    if (len(page.iframes) != 1 or page.iframes[0]["attributes"] != expected
            or page.iframes[0]["self_closing"] or "main" not in page.iframes[0]["parents"]
            or any(parent in page.iframes[0]["parents"] for parent in ("template", "noscript", "title"))):
        return ["expected one labelled local architecture viewer iframe with approved permissions"]
    return []


def validate():
    failures = []
    try:
        build_policy(destination=SITE / "privacy", check=True, archive_base="HEAD")
    except (ValueError, OSError) as error:
        failures.append(f"Privacy policy generation: {error}")
    required = (
        "index.html", "privacy/index.html", "404.html", "assets/site.css",
        "assets/privacy.css", "assets/theme.css", "assets/theme.js", "assets/favicon.svg", ".nojekyll",
    )
    for name in required:
        if not (SITE / name).is_file():
            failures.append(f"Missing required site file: {name}")
    if failures:
        return failures

    pages = {path.resolve(): Page(path) for path in SITE.rglob("*.html")}
    for path, page in pages.items():
        name = path.relative_to(SITE).as_posix()
        if not page.doctype or page.lang != "zh-CN" or not page.viewport:
            failures.append(f"{name}: missing HTML5, Chinese language or responsive viewport metadata")
        if not "".join(page.title).strip() or page.h1_count != 1 or page.main_count != 1:
            failures.append(f"{name}: expected a title, one h1 and one main element")
        failures.extend(
            f"{name}: {error}"
            for error in script_errors(
                page, archived=path.is_relative_to(SITE / "privacy" / "versions"),
                viewer=name == ARKDB_VIEWER,
            )
        )
        failures.extend(
            f"{name}: {error}"
            for error in frame_errors(page, architecture=name == "arkdb/architecture/index.html")
        )
        for identifier, count in page.ids.items():
            if count > 1:
                failures.append(f"{name}: duplicate id {identifier}")
        for reference in page.references:
            url = urlsplit(reference)
            if url.scheme in ("https", "mailto"):
                continue
            if url.scheme or url.netloc:
                failures.append(f"{name}: unsupported URL scheme in {reference}")
                continue
            route = unquote(url.path)
            if route.startswith("/"):
                if not route.startswith(PAGES_PATH):
                    failures.append(f"{name}: URL leaves the GitHub Pages site path: {reference}")
                    continue
                target = SITE / route.removeprefix(PAGES_PATH)
            elif route:
                target = path.parent / route
            else:
                target = path
            target = target.resolve()
            if not target.is_relative_to(SITE):
                failures.append(f"{name}: local URL leaves the site directory: {reference}")
                continue
            if target.is_dir():
                target = target / "index.html"
            if not target.is_file():
                failures.append(f"{name}: missing local target: {reference}")
                continue
            if url.fragment and target.suffix == ".html":
                fragment = unquote(url.fragment)
                if fragment not in pages[target].ids:
                    failures.append(f"{name}: missing fragment target: {reference}")

    homepage = (SITE / "index.html").read_text(encoding="utf-8")
    for marker in ("data-design=", "data-choice=", "prototype-controls", "设计预览", "?variant="):
        if marker in homepage:
            failures.append(f"index.html: prototype-only content remains: {marker}")
    policy = (SITE / "privacy" / "index.html").read_text(encoding="utf-8")
    for marker in ("隐私政策草稿", "拟生效日期", "供开发者确认的本地草稿", "尚未公开发布"):
        if marker in policy:
            failures.append(f"privacy/index.html: an approved formal policy still has draft labels: {marker}")
    return failures


if __name__ == "__main__":
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
    print("Validated policy exports and archives, scoped scripts and viewer frames, site structure, site-root links, local assets and formal-policy release labels.")
