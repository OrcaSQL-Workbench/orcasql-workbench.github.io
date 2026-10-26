import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from build_docs import ARKDB_VIEWER_ROUTE, MANUALS, Documentation, build_site, export_wiki
from validate_site import Page


FIXTURES = Path(__file__).parent / "fixtures"

AUTHORED_EXAMPLES = {
    "connection-config": "Connections.md",
    "connection-lifecycle": "Connections.md",
    "connection-call": "Connections.md",
    "crud-create": "Queries.md",
    "crud-insert": "Queries.md",
    "crud-read": "Queries.md",
    "crud-update": "Queries.md",
    "crud-delete": "Queries.md",
    "crud-call": "Queries.md",
    "streaming-call": "Streaming.md",
    "transaction-call": "Transactions.md",
    "cancellation-call": "Cancellation-and-Timeouts.md",
    "metadata-columns": "Metadata-and-Metrics.md",
    "metrics-availability": "Metadata-and-Metrics.md",
    "values-read": "Data-Types-and-Results.md",
    "error-cleanup": "Errors-and-Logging.md",
    "logging-level": "Errors-and-Logging.md",
    "worker-messages": "Worker-Integration.md",
    "worker-host": "Worker-Integration.md",
    "worker-entry": "Worker-Integration.md",
}


class ArkDbManualTests(unittest.TestCase):
    def setUp(self):
        self.manual = MANUALS["arkdb"]
        self.documentation = Documentation(self.manual.source, self.manual)

    def test_examples_match_the_downloaded_release_guide(self):
        baseline = json.loads((FIXTURES / "arkdb-mysql-1.0.2-examples.json").read_text(encoding="utf-8"))
        examples = baseline["examples"]
        found = set()
        authored = {}
        for page in self.documentation.pages:
            _, tokens, _ = self.documentation.parsed(page)
            lines = page.content.splitlines()
            for token in tokens:
                if token.type != "fence" or token.info != "typescript":
                    continue
                previous = lines[token.map[0] - 1] if token.map[0] else ""
                marker = re.fullmatch(r"\[//\]: # \(arkdb-example: ([a-z-]+)\)", previous)
                if marker:
                    identifier = marker[1]
                    self.assertIn(identifier, AUTHORED_EXAMPLES, f"Unknown manual example: {identifier}")
                    self.assertNotIn(identifier, authored, f"Duplicate manual example: {identifier}")
                    self.assertEqual(page.source, AUTHORED_EXAMPLES[identifier])
                    authored[identifier] = token.content
                else:
                    names = [name for name, source in examples.items() if source == token.content]
                    self.assertTrue(names, f"{page.source}: unmarked ArkTS example differs from the released guide")
                    found.update(names)
        self.assertEqual(found, set(examples), "A released usage example is missing from the manual")
        self.assertEqual(set(authored), set(AUTHORED_EXAMPLES), "A topic-specific example is missing")

    def test_example_markers_are_hidden_in_site_and_wiki(self):
        for page in self.documentation.pages:
            html = self.documentation.html(page)
            self.assertNotIn("arkdb-example:", html)
            renderer, _, _ = self.documentation.parsed(page)
            wiki_html = renderer.render(self.documentation.wiki_markdown(page))
            self.assertNotIn("arkdb-example:", wiki_html)

    def test_connection_inputs_and_crud_sequence_are_explicit(self):
        connection = self.documentation.source.joinpath("Connections.md").read_text(encoding="utf-8")
        for setting in ("host", "port", "database", "user", "caPemPath"):
            self.assertRegex(connection, rf"const {setting}: (?:string|number) = ")
        for mapping in ("config.host = host", "config.port = port", "config.defaultSchema = database",
                        "config.user = user", "password: string = passwordFromUi"):
            self.assertIn(mapping, connection)
        self.assertIn("SslMode.VERIFY_IDENTITY", connection)
        self.assertIn("await connection.close()", connection)
        self.assertIn("this.primaryFailure = primary", connection)
        self.assertIn("this.cleanupFailure = cleanup", connection)

        queries = self.documentation.source.joinpath("Queries.md").read_text(encoding="utf-8")
        _, tokens, _ = self.documentation.parsed(self.documentation.by_source["Queries.md"])
        call = next(token.content for token in tokens if token.type == "fence" and
                    "export async function runCrudExample(" in token.content)
        operations = re.findall(r"await (createSampleTable|insertSampleRows|readSampleRows|"
                                r"updateSampleRow|deleteSampleRow)\(connection\)", call)
        self.assertEqual(operations, ["createSampleTable", "insertSampleRows", "readSampleRows",
                                     "updateSampleRow", "readSampleRows", "deleteSampleRow",
                                     "readSampleRows"])
        self.assertIn("CREATE TEMPORARY TABLE arkdb_sample_inventory", queries)
        self.assertNotIn("DROP TABLE", queries)
        self.assertIn("CREATE TEMPORARY TABLES", queries)
        self.assertIn("result.truncated", queries)
        self.assertIn("1 | banana | 200", queries)
        self.assertIn("不是实机运行记录", queries)

    def test_old_page_routes_titles_and_heading_links_remain_available(self):
        legacy = json.loads((FIXTURES / "arkdb-legacy-routes.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build_site(self.manual.source, root / "site", manual=self.manual)
            export_wiki(self.manual.source, root / "wiki", manual=self.manual)
            for previous in legacy:
                with self.subTest(source=previous["source"]):
                    page = self.documentation.by_source[previous["source"]]
                    self.assertEqual(page.slug, previous["slug"])
                    self.assertEqual(page.title, previous["title"])
                    html = root / "site" / previous["slug"] / "index.html"
                    self.assertTrue(html.is_file())
                    rendered = Page(html)
                    for identifier in previous["anchors"]:
                        self.assertIn(identifier, rendered.ids, f"Missing old heading link: {identifier}")
                    name = previous["title"] if previous["slug"] else "Home"
                    self.assertTrue((root / "wiki" / (name + ".md")).is_file())

    def test_generated_manual_links_resolve_and_tasks_are_within_two_steps(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build_site(self.manual.source, root, manual=self.manual)
            asset_urls = {
                self.manual.site_path + path for path in self.documentation.assets()
            }
            pages = {
                page.site_url: Page(root / page.slug / "index.html")
                for page in self.documentation.pages
            }
            edges = {route: set() for route in pages}
            for route, page in pages.items():
                for reference in page.references:
                    url = urlsplit(reference)
                    if url.scheme or url.netloc:
                        continue
                    target = unquote(url.path) or route
                    if not target.startswith("/arkdb/"):
                        continue
                    if target in asset_urls:
                        self.assertTrue(
                            (root / target.removeprefix(self.manual.site_path)).is_file(),
                            f"{route}: missing asset {reference}",
                        )
                        continue
                    if target == ARKDB_VIEWER_ROUTE:
                        self.assertTrue((root / "architecture" / "explore" / "index.html").is_file())
                        continue
                    self.assertIn(target, pages, f"{route}: missing target {reference}")
                    if url.fragment:
                        self.assertIn(unquote(url.fragment), pages[target].ids,
                                      f"{route}: missing heading target {reference}")
                    edges[route].add(target)
            reachable = {"/arkdb/"}
            for _ in range(2):
                reachable |= {target for route in tuple(reachable) for target in edges[route]}
            for page in self.documentation.pages:
                if page.in_navigation:
                    self.assertIn(page.site_url, reachable)
                else:
                    self.assertTrue(
                        any(page.site_url in targets for route, targets in edges.items()
                            if route != page.site_url),
                        f"Retained page has no incoming content link: {page.site_url}",
                    )

    def test_architecture_svg_is_static_accessible_and_shared_by_site_and_wiki(self):
        page = self.documentation.by_source["Architecture.md"]
        self.assertTrue(page.in_navigation)
        self.assertIn("(Architecture.md)", self.documentation.by_source["Home.md"].content)
        asset = "assets/arkdb-architecture.svg"
        source = self.manual.source.joinpath(asset).read_bytes()
        svg = ET.fromstring(source)
        namespace = {"svg": "http://www.w3.org/2000/svg"}
        self.assertEqual(svg.tag, "{http://www.w3.org/2000/svg}svg")
        self.assertEqual(svg.get("role"), "img")
        self.assertEqual(svg.get("focusable"), "false")
        title = svg.find("svg:title", namespace)
        description = svg.find("svg:desc", namespace)
        self.assertIsNotNone(title)
        self.assertIsNotNone(description)
        self.assertEqual(svg.get("aria-labelledby"),
                         title.get("id") + " " + description.get("id"))
        self.assertIn("MySqlConnection", description.text)
        self.assertIn("KILL QUERY", description.text)
        self.assertIn("prefers-color-scheme", source.decode("utf-8"))
        for element in svg.iter():
            self.assertNotIn(element.tag.rsplit("}", 1)[-1],
                             ("script", "foreignObject", "iframe", "animate", "animateTransform"))
            self.assertIn(element.get("role"), (None, "img", "presentation", "none"))
            self.assertNotEqual(element.get("focusable"), "true")
            for attribute in ("tabindex", "accesskey", "aria-pressed", "aria-expanded",
                              "aria-controls", "aria-haspopup", "aria-keyshortcuts"):
                self.assertNotIn(attribute, element.attrib)
            for attribute, value in element.attrib.items():
                self.assertFalse(attribute.lower().startswith("on"))
                if attribute.rsplit("}", 1)[-1] == "href":
                    self.assertTrue(value.startswith("#"), "SVG references must remain local")
            if element.tag.endswith("}style"):
                for target in re.findall(r"url\(\s*['\"]?([^)'\"\s]+)", element.text or ""):
                    self.assertTrue(target.startswith(("#", "data:")),
                                    "SVG styles must not fetch external assets")

        provenance = json.loads(svg.find("svg:metadata", namespace).text)
        self.assertEqual(provenance["repository"], "https://github.com/OrcaSQL-Workbench/ArkDB")
        self.assertRegex(provenance["revision"], r"^[a-f0-9]{40}$")
        _, tokens, _ = self.documentation.parsed(page)
        source_links = [
            child.attrGet("href")
            for token in tokens for child in token.children or []
            if child.type == "link_open" and
            child.attrGet("href").startswith(provenance["repository"] + "/blob/")
        ]
        self.assertTrue(source_links, "Architecture guide must link to source evidence")
        for link in source_links:
            self.assertTrue(link.startswith(
                provenance["repository"] + "/blob/" + provenance["revision"] + "/"),
                f"Source link differs from the diagram revision: {link}")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build_site(self.manual.source, root / "site", manual=self.manual)
            export_wiki(self.manual.source, root / "wiki", manual=self.manual)
            rendered = Page(root / "site" / page.slug / "index.html")
            self.assertIn(self.manual.site_path + asset, rendered.references)
            wiki = (root / "wiki" / (page.wiki_name + ".md")).read_text(encoding="utf-8")
            self.assertIn("](" + asset + ")", wiki)
            for surface in ("site", "wiki"):
                self.assertEqual((root / surface / asset).read_bytes(), source)

    def test_architecture_svg_labels_meet_aa_contrast_in_each_theme(self):
        svg = ET.fromstring(self.manual.source.joinpath(
            "assets/arkdb-architecture.svg").read_bytes())
        namespace = {"svg": "http://www.w3.org/2000/svg"}
        css = "\n".join(element.text or "" for element in svg.findall("svg:style", namespace))
        fills = dict(re.findall(r"(?m)^\.([\w-]+) \{ fill: ([^;]+);", css))
        parents = {child: parent for parent in svg.iter() for child in parent}
        themes = {
            "automatic-dark": r"(?m)^:root, svg \{([^{}]+)\}",
            "automatic-light": r"(?m)^@media \(prefers-color-scheme: light\) \{ :root, svg \{([^{}]+)\}",
            "explicit-dark": r'(?m)^svg\[data-theme="dark"\] \{([^{}]+)\}',
            "explicit-light": r'(?m)^svg\[data-theme="light"\] \{([^{}]+)\}',
        }

        def color(value, palette):
            if value.startswith("var("):
                value = palette[value[4:-1]]
            if re.fullmatch(r"#[a-fA-F0-9]{6}", value):
                return tuple(int(value[index:index + 2], 16) / 255 for index in (1, 3, 5)) + (1,)
            match = re.fullmatch(r"rgba\((\d+), (\d+), (\d+), ([\d.]+)\)", value)
            self.assertIsNotNone(match, f"Unsupported SVG contrast color: {value}")
            return tuple(int(match[index]) / 255 for index in (1, 2, 3)) + (float(match[4]),)

        def composite(foreground, background):
            return tuple(foreground[index] * foreground[3] +
                         background[index] * (1 - foreground[3]) for index in range(3))

        def luminance(rgb):
            linear = [channel / 12.92 if channel <= 0.04045
                      else ((channel + 0.055) / 1.055) ** 2.4 for channel in rgb]
            return sum(channel * weight for channel, weight in
                       zip(linear, (0.2126, 0.7152, 0.0722)))

        def fill(element, palette):
            values = [fills[name] for name in element.get("class", "").split() if name in fills]
            self.assertEqual(len(values), 1, f"Expected one SVG fill for {element.attrib}")
            return color(values[0], palette)

        for theme, pattern in themes.items():
            with self.subTest(theme=theme):
                match = re.search(pattern, css)
                self.assertIsNotNone(match, f"Missing SVG palette: {theme}")
                palette = dict(re.findall(r"(--[\w-]+): ([^;]+);", match[1]))
                failures = []
                labels = svg.findall(".//svg:text", namespace)
                self.assertTrue(labels)
                for text in labels:
                    parent = parents[text]
                    self.assertNotIn("transform", parent.attrib)
                    background = color(palette["--bg"], palette)[:3]
                    x, y = float(text.get("x")), float(text.get("y"))
                    for sibling in parent:
                        if sibling is text:
                            break
                        if sibling.tag == "{http://www.w3.org/2000/svg}rect":
                            left, top = float(sibling.get("x")), float(sibling.get("y"))
                            right = left + float(sibling.get("width"))
                            bottom = top + float(sibling.get("height"))
                            if left <= x <= right and top <= y <= bottom:
                                background = composite(fill(sibling, palette), background)
                    foreground = composite(fill(text, palette), background)
                    light, dark = sorted((luminance(foreground), luminance(background)), reverse=True)
                    ratio = (light + 0.05) / (dark + 0.05)
                    if ratio < 4.5:
                        failures.append(f"{text.text}: {ratio:.2f}:1")
                self.assertEqual(failures, [], f"SVG labels below WCAG AA 4.5:1 in {theme}")


if __name__ == "__main__":
    unittest.main()
