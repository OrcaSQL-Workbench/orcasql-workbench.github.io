import json
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from build_docs import MANUALS, Documentation, SITE_MANIFEST, WIKI_MANIFEST, build_site, export_wiki, main, write_managed_files


class NavigationParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.list_depth = 0
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "nav" and attrs.get("aria-label", "").endswith("目录"):
            self.active = True
        if self.active and tag == "ul":
            self.list_depth += 1
        if self.active and tag == "a":
            self.links.append((attrs["href"], self.list_depth))

    def handle_endtag(self, tag):
        if self.active and tag == "ul":
            self.list_depth -= 1
        if tag == "nav":
            self.active = False


class DocumentationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "docs"
        self.source.mkdir()
        self.pages = [
            {"source": "Home.md", "slug": "", "title": "文档首页"},
            {"source": "Guide.md", "slug": "guide", "title": "使用指南"},
        ]
        self.write_navigation()
        self.write("Home.md", "# 文档首页\n\n[指南](Guide.md)\n")
        self.write("Guide.md", "# 使用指南\n\n[首页](Home.md)\n\n## 内容\n\n说明。\n")

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, name, text):
        (self.source / name).write_text(text, encoding="utf-8")

    def write_navigation(self, version=1):
        self.write("navigation.json", json.dumps({"version": version, "pages": self.pages}, ensure_ascii=False))

    def grouped_documentation(self):
        self.pages[0]["section"] = "开始使用"
        self.pages[1]["section"] = "MySQL 使用指南"
        self.write_navigation(version=2)
        try:
            return Documentation(self.source)
        except ValueError as error:
            self.fail(f"Valid grouped navigation was rejected: {error}")

    def test_grouped_sections_appear_in_the_website_and_wiki(self):
        self.grouped_documentation()
        site, wiki = self.root / "site", self.root / "wiki"
        build_site(self.source, site)
        export_wiki(self.source, wiki)
        html = (site / "guide" / "index.html").read_text(encoding="utf-8")
        navigation = re.search(r'<nav aria-label="用户文档目录">(.*?)</nav>', html, re.DOTALL).group(1)
        self.assertLess(navigation.index(">开始使用</h2>"), navigation.index('href="/docs/"'))
        self.assertLess(navigation.index(">MySQL 使用指南</h2>"), navigation.index('href="/docs/guide/"'))
        self.assertIn('href="/docs/guide/" aria-current="page"', navigation)
        sidebar = (wiki / "_Sidebar.md").read_text(encoding="utf-8")
        self.assertIn("## 开始使用\n\n- [文档首页](Home)", sidebar)
        self.assertIn("## MySQL 使用指南\n\n- [使用指南](%E4%BD%BF%E7%94%A8%E6%8C%87%E5%8D%97)", sidebar)

    def test_grouped_pages_are_nested_under_their_sections(self):
        self.grouped_documentation()
        site = self.root / "site"
        build_site(self.source, site)
        parser = NavigationParser()
        parser.feed((site / "guide" / "index.html").read_text(encoding="utf-8"))
        self.assertEqual(parser.links, [("/docs/", 2), ("/docs/guide/", 2)])

    def test_both_published_manuals_have_section_hierarchy(self):
        for manual in MANUALS.values():
            with self.subTest(manual=manual.product):
                documentation = Documentation(manual.source, manual)
                self.assertTrue(all(documentation.navigation))
                site = self.root / manual.site_path.strip("/")
                build_site(manual.source, site, manual=manual)
                parser = NavigationParser()
                parser.feed((site / "index.html").read_text(encoding="utf-8"))
                self.assertEqual(
                    parser.links,
                    [(page.site_url, 2) for pages in documentation.navigation.values() for page in pages],
                )

    def test_hidden_legacy_pages_are_linkable_and_exported_but_not_in_navigation(self):
        self.pages.append({
            "source": "Legacy.md", "slug": "legacy", "title": "旧版入口",
            "section": "旧链接", "nav": False,
        })
        self.write("Legacy.md", "# 旧版入口\n\n[指南](Guide.md)\n")
        self.write("Home.md", "# 文档首页\n\n[原入口](Legacy.md)\n")
        documentation = self.grouped_documentation()
        site, wiki = self.root / "site", self.root / "wiki"
        self.assertEqual(build_site(self.source, site), 3)
        export_wiki(self.source, wiki)
        html = (site / "index.html").read_text(encoding="utf-8")
        navigation = re.search(r'<nav aria-label="用户文档目录">(.*?)</nav>', html, re.DOTALL).group(1)
        self.assertNotIn("旧版入口", navigation)
        self.assertNotIn("旧链接", navigation)
        self.assertIn('href="/docs/legacy/"', documentation.html(documentation.pages[0]))
        self.assertTrue((site / "legacy" / "index.html").is_file())
        self.assertTrue((wiki / "旧版入口.md").is_file())
        self.assertNotIn("旧版入口", (wiki / "_Sidebar.md").read_text(encoding="utf-8"))
        self.assertIn("[原入口](%E6%97%A7%E7%89%88%E5%85%A5%E5%8F%A3)",
                      (wiki / "Home.md").read_text(encoding="utf-8"))

    def test_nonadjacent_pages_in_the_same_section_share_one_heading(self):
        self.pages.append({
            "source": "Next.md", "slug": "next", "title": "下一步", "section": "开始使用",
        })
        self.write("Next.md", "# 下一步\n")
        self.grouped_documentation()
        wiki = self.root / "wiki"
        export_wiki(self.source, wiki)
        sidebar = (wiki / "_Sidebar.md").read_text(encoding="utf-8")
        self.assertEqual(sidebar.count("## 开始使用\n"), 1)
        self.assertLess(sidebar.index("[下一步]"), sidebar.index("## MySQL 使用指南"))

    def test_version_one_keeps_its_ungrouped_navigation(self):
        site, wiki = self.root / "site", self.root / "wiki"
        build_site(self.source, site)
        export_wiki(self.source, wiki)
        html = (site / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("docs-navigation-grouped", html)
        self.assertEqual((wiki / "_Sidebar.md").read_text(encoding="utf-8"),
                         "# 用户文档\n\n- [文档首页](Home)\n- [使用指南](%E4%BD%BF%E7%94%A8%E6%8C%87%E5%8D%97)\n")

    def test_invalid_group_metadata_is_rejected(self):
        for change in (
            {"section": ""},
            {"section": " 开始使用"},
            {"section": "开始\n使用"},
            {"section": []},
            {"section": "开始使用", "nav": "false"},
            {"section": "开始使用", "nav": 0},
            {"section": "开始使用", "unexpected": True},
        ):
            with self.subTest(change=change):
                self.pages[0] = {"source": "Home.md", "slug": "", "title": "文档首页", **change}
                self.pages[1]["section"] = "MySQL 使用指南"
                self.write_navigation(version=2)
                with self.assertRaises(ValueError):
                    Documentation(self.source)

    def test_the_homepage_cannot_be_hidden(self):
        self.pages[0].update({"section": "开始使用", "nav": False})
        self.pages[1]["section"] = "MySQL 使用指南"
        self.write_navigation(version=2)
        with self.assertRaisesRegex(ValueError, "homepage.*visible"):
            Documentation(self.source)

    def test_website_and_wiki_share_page_content_and_links(self):
        documentation = Documentation(self.source)
        page = documentation.pages[0]
        self.assertIn('href="/docs/guide/"', documentation.html(page))
        self.assertIn("[指南](%E4%BD%BF%E7%94%A8%E6%8C%87%E5%8D%97)", documentation.wiki_markdown(page))
        site = self.root / "site"
        wiki = self.root / "wiki"
        self.assertEqual(build_site(self.source, site), 2)
        export_wiki(self.source, wiki)
        self.assertTrue((site / "guide" / "index.html").is_file())
        self.assertTrue((wiki / "使用指南.md").is_file())
        self.assertIn("使用指南", (wiki / "_Sidebar.md").read_text(encoding="utf-8"))
        self.assertTrue((site / SITE_MANIFEST).is_file())
        self.assertTrue((wiki / WIKI_MANIFEST).is_file())

    def test_code_examples_are_not_rewritten(self):
        self.write("Home.md", "# 文档首页\n\n[指南](Guide.md)\n\n`[示例](Guide.md)`\n\n```markdown\n[示例](Guide.md)\n```\n")
        documentation = Documentation(self.source)
        wiki = documentation.wiki_markdown(documentation.pages[0])
        self.assertIn("`[示例](Guide.md)`", wiki)
        self.assertIn("```markdown\n[示例](Guide.md)\n```", wiki)
        self.assertIn("[指南](%E4%BD%BF%E7%94%A8%E6%8C%87%E5%8D%97)", wiki)

    def test_reference_links_are_rewritten(self):
        self.write("Home.md", "# 文档首页\n\n[指南][guide]\n\n[guide]: Guide.md\n")
        documentation = Documentation(self.source)
        self.assertIn("[guide]: %E4%BD%BF%E7%94%A8%E6%8C%87%E5%8D%97",
                      documentation.wiki_markdown(documentation.pages[0]))

    def test_multiline_and_nested_backticks_are_not_rewritten(self):
        example = "``文字 ` [示例](Guide.md)\n下一行``"
        self.write("Home.md", "# 文档首页\n\n[指南](Guide.md)\n\n" + example + "\n")
        documentation = Documentation(self.source)
        rendered = documentation.wiki_markdown(documentation.pages[0])
        self.assertIn(example, rendered)
        self.assertIn("[指南](%E4%BD%BF%E7%94%A8%E6%8C%87%E5%8D%97)", rendered)

    def test_wiki_titles_with_spaces_use_hyphenated_routes(self):
        self.pages[1]["title"] = "连接管理与 TLS"
        self.write_navigation()
        self.write("Guide.md", "# 连接管理与 TLS\n")
        documentation = Documentation(self.source)
        self.assertIn("%E8%BF%9E%E6%8E%A5%E7%AE%A1%E7%90%86%E4%B8%8E-TLS",
                      documentation.wiki_markdown(documentation.pages[0]))

    def test_images_have_valid_paths_on_both_surfaces(self):
        assets = self.source / "assets"
        assets.mkdir()
        (assets / "screen.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
        self.write("Home.md", "# 文档首页\n\n![截图](assets/screen.svg)\n")
        documentation = Documentation(self.source)
        self.assertIn('src="/docs/assets/screen.svg"', documentation.html(documentation.pages[0]))
        self.assertIn("![截图](assets/screen.svg)", documentation.wiki_markdown(documentation.pages[0]))

    def test_unknown_local_document_is_an_error(self):
        self.write("Home.md", "# 文档首页\n\n[丢失](Missing.md)\n")
        documentation = Documentation(self.source)
        with self.assertRaisesRegex(ValueError, "unknown document"):
            documentation.html(documentation.pages[0])

    def test_heading_validation_and_unique_heading_ids(self):
        self.write("Guide.md", "# 使用指南\n\n## 同一标题\n\n内容。\n\n## 同一标题\n\n内容。\n")
        documentation = Documentation(self.source)
        rendered = documentation.html(documentation.pages[1])
        self.assertIn('id="同一标题"', rendered)
        self.assertIn('id="同一标题-1"', rendered)
        self.write("Home.md", "# 不同标题\n")
        with self.assertRaisesRegex(ValueError, "match"):
            Documentation(self.source).html(Documentation(self.source).pages[0])

    def test_duplicate_slug_is_an_error(self):
        self.pages[1]["slug"] = ""
        self.write_navigation()
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            Documentation(self.source)

    def test_unlisted_markdown_is_an_error(self):
        self.write("Unlisted.md", "# 额外页面\n")
        with self.assertRaisesRegex(ValueError, "missing from navigation"):
            Documentation(self.source)

    def test_raw_html_is_not_executed(self):
        self.write("Home.md", "# 文档首页\n\n<script>alert(1)</script>\n")
        documentation = Documentation(self.source)
        rendered = documentation.html(documentation.pages[0])
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)

    def test_managed_cleanup_preserves_unmanaged_wiki_pages(self):
        wiki = self.root / "wiki"
        wiki.mkdir()
        (wiki / "Manual.md").write_text("保留", encoding="utf-8")
        write_managed_files(wiki, {"Old.md": b"old"}, WIKI_MANIFEST)
        write_managed_files(wiki, {"New.md": b"new"}, WIKI_MANIFEST)
        self.assertFalse((wiki / "Old.md").exists())
        self.assertTrue((wiki / "New.md").exists())
        self.assertEqual((wiki / "Manual.md").read_text(encoding="utf-8"), "保留")

    def test_manifest_traversal_is_rejected_before_deletion(self):
        wiki = self.root / "wiki"
        wiki.mkdir()
        sentinel = self.root / "keep.md"
        sentinel.write_text("保留", encoding="utf-8")
        (wiki / WIKI_MANIFEST).write_text(json.dumps({"version": 1, "files": ["../keep.md"]}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            write_managed_files(wiki, {}, WIKI_MANIFEST)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "保留")

    def test_git_directory_is_not_a_generated_target(self):
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            write_managed_files(self.root / "wiki", {".git/config": b"bad"}, WIKI_MANIFEST)
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            write_managed_files(self.root / "wiki", {".GIT/config": b"bad"}, WIKI_MANIFEST)

    def test_manual_routes_sources_and_wiki_links_stay_separate(self):
        for name, manual in MANUALS.items():
            with self.subTest(manual=name):
                destination = self.root / name
                build_site(self.source, destination, manual=manual)
                html = (destination / "index.html").read_text(encoding="utf-8")
                self.assertIn(f'href="{manual.site_path}guide/"', html)
                self.assertIn(f"/blob/main/{manual.source_path}/Home.md", html)
                self.assertIn(f'href="{manual.wiki_url}/Home"', html)
                self.assertIn(f'href="{manual.site_path}" aria-current="page"', html)
                self.assertIn(f'<title>文档首页 · {manual.product}</title>', html)
                other = MANUALS["arkdb" if name == "workbench" else "workbench"]
                self.assertNotIn(f'href="{other.site_path}" aria-current="page"', html)

    def test_arkdb_assets_use_arkdb_site_root(self):
        (self.source / "assets").mkdir()
        (self.source / "assets" / "screen.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
        self.write("Home.md", "# 文档首页\n\n![截图](assets/screen.svg)\n")
        manual = MANUALS["arkdb"]
        documentation = Documentation(self.source, manual)
        self.assertIn('src="/arkdb/assets/screen.svg"', documentation.html(documentation.pages[0]))
        site, wiki = self.root / "site", self.root / "wiki"
        build_site(self.source, site, manual=manual)
        export_wiki(self.source, wiki, manual=manual)
        self.assertEqual((site / "assets" / "screen.svg").read_bytes(),
                         (wiki / "assets" / "screen.svg").read_bytes())

    def test_wide_layout_is_scoped_to_arkdb(self):
        for name, manual in MANUALS.items():
            destination = self.root / name
            build_site(self.source, destination, manual=manual)
            for path in destination.rglob("*.html"):
                with self.subTest(manual=name, page=path.relative_to(destination)):
                    html = path.read_text(encoding="utf-8")
                    classes = re.search(r'<main class="([^"]+)"', html).group(1).split()
                    self.assertIn("docs-main", classes)
                    self.assertIn("wrap", classes)
                    self.assertEqual("docs-main-wide" in classes, name == "arkdb")

    def test_wiki_footer_points_to_canonical_source_not_target_repository(self):
        for name, manual in MANUALS.items():
            with self.subTest(manual=name):
                wiki = self.root / name
                export_wiki(self.source, wiki, manual=manual)
                footer = (wiki / "_Footer.md").read_text(encoding="utf-8")
                sidebar = (wiki / "_Sidebar.md").read_text(encoding="utf-8")
                self.assertIn(f"/tree/main/{manual.source_path}", footer)
                self.assertIn(f"https://orcasql-workbench.github.io{manual.site_path}", footer)
                self.assertIn("orcasql-workbench.github.io/tree/main/", footer)
                self.assertTrue(sidebar.startswith(f"# {manual.title}\n"))
                self.assertTrue((wiki / "Home.md").is_file())

    def test_default_cli_builds_and_exports_both_manuals_separately(self):
        wiki = self.root / "wiki"
        with patch.object(sys, "argv", ["build_docs.py", "--wiki-output", str(wiki)]), \
                patch("build_docs.build_site", return_value=2) as build, \
                patch("build_docs.export_wiki") as export:
            main()
        self.assertEqual(build.call_count, 2)
        self.assertEqual(export.call_count, 2)
        for name, manual in MANUALS.items():
            build.assert_any_call(manual.source, manual.site_output, manual=manual)
            export.assert_any_call(manual.source, wiki / name, manual=manual)

    def test_single_manual_cli_honors_custom_output_and_source(self):
        manual = MANUALS["arkdb"]
        site, wiki = self.root / "site", self.root / "wiki"
        with patch.object(sys, "argv", [
            "build_docs.py", "--manual", "arkdb", "--source", str(self.source),
            "--site-output", str(site), "--wiki-output", str(wiki),
        ]):
            main()
        self.assertTrue((site / "guide" / "index.html").is_file())
        self.assertTrue((wiki / "Home.md").is_file())
        self.assertIn(manual.wiki_url, (site / "index.html").read_text(encoding="utf-8"))

    def test_legacy_custom_source_defaults_to_workbench(self):
        site = self.root / "site"
        with patch.object(sys, "argv", [
            "build_docs.py", "--source", str(self.source), "--site-output", str(site),
        ]):
            main()
        self.assertIn('href="/docs/guide/"', (site / "index.html").read_text(encoding="utf-8"))

    def test_all_manuals_cannot_share_custom_output(self):
        with patch.object(sys, "argv", [
            "build_docs.py", "--manual", "all", "--site-output", str(self.root / "site"),
        ]), patch("sys.stderr"):
            with self.assertRaises(SystemExit) as error:
                main()
        self.assertEqual(error.exception.code, 2)

    def test_repository_manuals_build_and_export_without_cross_cleanup(self):
        site, wiki = self.root / "site", self.root / "wiki"
        for name, manual in MANUALS.items():
            with self.subTest(manual=name):
                count = build_site(manual.source, site / name, manual=manual)
                exported = export_wiki(manual.source, wiki / name, manual=manual)
                pages = json.loads((manual.source / "navigation.json").read_text(encoding="utf-8"))["pages"]
                self.assertEqual(count, len(pages))
                self.assertEqual(sum(path.suffix == ".md" for path in (wiki / name).iterdir()), count + 2)
                self.assertIn("Home.md", exported)
        original = (wiki / "workbench" / "Home.md").read_bytes()
        export_wiki(MANUALS["arkdb"].source, wiki / "arkdb", manual=MANUALS["arkdb"])
        self.assertEqual((wiki / "workbench" / "Home.md").read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
