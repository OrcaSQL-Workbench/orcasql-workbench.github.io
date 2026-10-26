import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET


PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "scripts"))
from build_docs import ARKDB_VIEWER_ROUTE, ARKDB_VIEWER_URL, MANUALS, Documentation, build_site, export_wiki
from validate_site import Page, frame_errors, script_errors


class ArchitectureViewerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.manual = MANUALS["arkdb"]
        pages = [
            {"source": "Home.md", "slug": "", "title": "首页", "section": "开始使用"},
            {"source": "Architecture.md", "slug": "architecture",
             "title": "总览架构与源码导读", "section": "贡献与维护"},
        ]
        (self.source / "navigation.json").write_text(
            json.dumps({"version": 2, "pages": pages}), encoding="utf-8")
        (self.source / "Home.md").write_text("# 首页\n", encoding="utf-8")
        (self.source / "Architecture.md").write_text(
            "# 总览架构与源码导读\n\n![架构图](assets/arkdb-architecture.svg)\n\n"
            f"[交互图]({ARKDB_VIEWER_URL})\n", encoding="utf-8")
        (self.source / "assets").mkdir()
        self.svg = self.source / "assets" / "arkdb-architecture.svg"
        shutil.copyfile(self.manual.source / "assets" / self.svg.name, self.svg)
        shutil.copytree(self.manual.source / "viewer", self.source / "viewer")

    def test_site_has_a_scoped_iframe_and_an_independent_local_viewer(self):
        destination = self.root / "site"
        build_site(self.source, destination, manual=self.manual)
        guide = Page(destination / "architecture" / "index.html")
        viewer = Page(destination / "architecture" / "explore" / "index.html")
        self.assertEqual(script_errors(guide), [])
        self.assertEqual(frame_errors(guide, architecture=True), [])
        self.assertEqual(script_errors(viewer, viewer=True), [])
        self.assertEqual(frame_errors(viewer), [])
        self.assertTrue(script_errors(viewer))
        self.assertTrue(script_errors(viewer, viewer=True, archived=True))
        self.assertIn(ARKDB_VIEWER_ROUTE, guide.references)
        self.assertNotIn(ARKDB_VIEWER_URL, guide.references)
        self.assertEqual((viewer.h1_count, viewer.main_count), (1, 1))
        source = viewer.path.read_text(encoding="utf-8")
        self.assertNotIn("ARKDB_ARCHITECTURE_SVG", source)
        self.assertIn("KILL QUERY", source)
        self.assertIn('class="viewer-fallback"', source)
        diagram = ET.fromstring(re.search(r"<svg\b.*?</svg>", source, re.DOTALL)[0])
        self.assertEqual(diagram.get("role"), "img")
        self.assertEqual(diagram.get("focusable"), "false")
        self.assertFalse(diagram.findall("{http://www.w3.org/2000/svg}style"))
        self.assertFalse(any("tabindex" in node.attrib for node in diagram.iter()))
        for name in ("init.js", "viewer.js", "LICENSE-Archify.txt", "LICENSE-JetBrainsMono.txt"):
            self.assertTrue((viewer.path.parent / name).is_file())
        guide_text = guide.path.read_text(encoding="utf-8")
        self.assertIn("<noscript><style>", guide_text)
        self.assertIn(".docs-diagram-static{display:block!important}", guide_text)

    def test_wiki_keeps_the_static_asset_and_canonical_interactive_link_only(self):
        destination = self.root / "wiki"
        export_wiki(self.source, destination, manual=self.manual)
        content = (destination / "总览架构与源码导读.md").read_text(encoding="utf-8")
        self.assertIn("![架构图](assets/arkdb-architecture.svg)", content)
        self.assertIn(ARKDB_VIEWER_URL, content)
        self.assertNotIn("<iframe", content)
        self.assertFalse((destination / "viewer").exists())
        self.assertFalse((destination / "architecture").exists())
        self.assertEqual((destination / "assets" / self.svg.name).read_bytes(), self.svg.read_bytes())

    def test_raw_markdown_html_cannot_add_scripts_or_another_frame(self):
        page = self.source / "Architecture.md"
        page.write_text(page.read_text(encoding="utf-8") +
                        '\n<script>alert(1)</script><iframe src="https://example.com"></iframe>\n',
                        encoding="utf-8")
        build_site(self.source, self.root / "site", manual=self.manual)
        parsed = Page(self.root / "site" / "architecture" / "index.html")
        self.assertEqual(len(parsed.scripts), 1)
        self.assertEqual(frame_errors(parsed, architecture=True), [])
        self.assertIn("&lt;script&gt;", parsed.path.read_text(encoding="utf-8"))

    def test_inline_svg_rejects_active_content_and_external_references(self):
        original = self.svg.read_text(encoding="utf-8")
        replacements = [
            original.replace("<svg ", '<svg onload="alert(1)" ', 1),
            original.replace("<svg ", '<svg tabindex="0" ', 1),
            original.replace('role="img"', 'role="button"', 1),
            original.replace("<svg ", '<svg href="https://example.com/" ', 1),
            original.replace("</svg>", "<script>alert(1)</script></svg>"),
            original.replace("</svg>", "<foreignObject>unsafe</foreignObject></svg>"),
            "<svg",
        ]
        for content in replacements:
            with self.subTest(content=content[:80]):
                self.svg.write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError):
                    Documentation(self.source, self.manual).viewer_files()

    def test_viewer_and_shared_svg_must_have_the_same_source_revision_and_nodes(self):
        original = self.svg.read_text(encoding="utf-8")
        first_node = next(node.get("data-node-id") for node in ET.fromstring(original).iter()
                          if node.get("data-node-id"))
        for content in (
            re.sub(r'("revision"\s*:\s*")[a-f0-9]{40}(")', r"\g<1>" + "a" * 40 + r"\g<2>",
                   original, count=1),
            original.replace(f'data-node-id="{first_node}"', f'data-node-id="{first_node}-mismatch"'),
        ):
            with self.subTest(content=content[-80:]):
                self.svg.write_text(content, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "different source provenance or nodes"):
                    Documentation(self.source, self.manual).viewer_files()

    def test_workbench_does_not_receive_the_interactive_exception(self):
        destination = self.root / "site"
        build_site(self.source, destination, manual=MANUALS["workbench"])
        self.assertFalse((destination / "architecture" / "explore").exists())
        guide = Page(destination / "architecture" / "index.html")
        self.assertEqual(script_errors(guide), [])
        self.assertFalse(guide.iframes)

    def test_live_diagram_text_stays_high_contrast_in_all_bundled_presets(self):
        template = (self.source / "viewer" / "index.html").read_text(encoding="utf-8")
        self.assertIn("svg[data-reader-fit] text { fill: var(--text); }", template)
        self.assertIn('data-reader-fit="intrinsic-height"', self.svg.read_text(encoding="utf-8"))
        palettes = re.findall(
            r'(?m)^\s*(?::root,\s*\[data-theme="dark"\]|\[data-theme="light"\]|'
            r'\[data-preset="(?:signal-flow|blueprint|editorial)"\]\[data-theme="(?:light|dark)"\])'
            r'\s*\{([^{}]+)\}', template,
        )
        self.assertEqual(len(palettes), 8)

        def rgb(value):
            self.assertRegex(value, r"^#[a-fA-F0-9]{6}$")
            return tuple(int(value[index:index + 2], 16) / 255 for index in (1, 3, 5))

        def luminance(color):
            values = [channel / 12.92 if channel <= 0.04045
                      else ((channel + 0.055) / 1.055) ** 2.4 for channel in color]
            return sum(channel * weight for channel, weight in
                       zip(values, (0.2126, 0.7152, 0.0722)))

        for index, declarations in enumerate(palettes):
            palette = {name: value.strip() for name, value in
                       re.findall(r"(--[\w-]+):\s*([^;]+);", declarations)}
            foreground = rgb(palette["--text"])
            mask = rgb(palette["--mask"])
            backgrounds = [rgb(palette["--bg"]), mask]
            for name, value in palette.items():
                if not name.endswith("-fill"):
                    continue
                match = re.fullmatch(
                    r"rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)", value)
                self.assertIsNotNone(match)
                alpha = float(match[4])
                backgrounds.append(tuple(int(match[channel + 1]) / 255 * alpha +
                                         mask[channel] * (1 - alpha) for channel in range(3)))
            for background in backgrounds:
                light, dark = sorted((luminance(foreground), luminance(background)), reverse=True)
                self.assertGreaterEqual((light + 0.05) / (dark + 0.05), 4.5, f"Palette {index}")


if __name__ == "__main__":
    unittest.main()
