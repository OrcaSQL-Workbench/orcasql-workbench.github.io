import json
from pathlib import Path
import sys
import tempfile
import unittest
from urllib.parse import unquote, urlsplit


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from build_docs import MANUALS, Documentation, build_site, export_wiki
from validate_site import Page


FIXTURES = Path(__file__).parent / "fixtures"


class ArkDbManualTests(unittest.TestCase):
    def setUp(self):
        self.manual = MANUALS["arkdb"]
        self.documentation = Documentation(self.manual.source, self.manual)

    def test_examples_match_the_downloaded_release_guide(self):
        baseline = json.loads((FIXTURES / "arkdb-mysql-1.0.2-examples.json").read_text(encoding="utf-8"))
        examples = baseline["examples"]
        found = set()
        for page in self.documentation.pages:
            _, tokens, _ = self.documentation.parsed(page)
            for token in tokens:
                if token.type == "fence" and token.info == "typescript":
                    names = [name for name, source in examples.items() if source == token.content]
                    self.assertTrue(names, f"{page.source}: ArkTS example differs from the released guide")
                    found.update(names)
        self.assertEqual(found, set(examples), "A released usage example is missing from the manual")

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
