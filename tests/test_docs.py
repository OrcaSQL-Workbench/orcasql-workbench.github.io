import json
from pathlib import Path
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from build_docs import Documentation, SITE_MANIFEST, WIKI_MANIFEST, build_site, export_wiki, write_managed_files


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

    def write_navigation(self):
        self.write("navigation.json", json.dumps({"version": 1, "pages": self.pages}, ensure_ascii=False))

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


if __name__ == "__main__":
    unittest.main()
