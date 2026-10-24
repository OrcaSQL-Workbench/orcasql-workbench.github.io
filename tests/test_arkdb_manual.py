import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from urllib.parse import unquote, urlsplit


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from build_docs import MANUALS, Documentation, build_site, export_wiki
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


if __name__ == "__main__":
    unittest.main()
