import copy
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "scripts"))
from build_privacy import (
    FILES, MANIFEST_FIELDS, Markup, POLICY_FILE, POLICY_URL, SOURCE,
    build, check_manifest, load_json, policy_files,
)
import validate_site


class InlineText(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.feed(html)
        self.close()

    def handle_data(self, data):
        self.parts.append(data)

    @property
    def text(self):
        return "".join(self.parts)


def source_paragraphs(source):
    year, month, day = map(int, source["effectiveDate"].split("-"))
    paragraphs = [
        source["title"], f"生效日期\n{year}年{month}月{day}日", InlineText(source["lead"]).text,
    ]
    headings = [source["title"]]
    for section in source["sections"]:
        paragraphs.append(section["title"])
        headings.append(section["title"])
        for block in section["blocks"]:
            if block["type"] == "paragraph":
                paragraphs.append(InlineText(block["html"]).text)
            elif block["type"] == "heading":
                paragraphs.append(block["text"])
                headings.append(block["text"])
            elif block["type"] == "list":
                paragraphs.append("\n".join(InlineText(item).text for item in block["items"]))
            elif block["type"] == "table":
                paragraphs.append("\n".join(InlineText(item).text for item in [block["caption"], *block["headers"]]))
                paragraphs.extend("\n".join(InlineText(cell).text for cell in row) for row in block["rows"])
            else:
                raise AssertionError(f"Untested source block type: {block['type']}")
    return ("\n\n".join(paragraphs) + "\n").encode("utf-8"), headings


class PrivacyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "policy.json"
        self.output = self.root / "site" / "privacy"
        self.data = {
            "schemaVersion": 1,
            "locale": "zh-Hans",
            "title": "政策标题",
            "description": "页面说明。",
            "effectiveDate": "2026-10-11",
            "lead": "介绍<strong>重点</strong>，保留 SQL 空格 &amp; 内容。",
            "sections": [{
                "id": "data",
                "title": "数据说明",
                "navigationTitle": "导航专用文字",
                "blocks": [
                    {"type": "paragraph", "html": '正文<a href="https://example.com/policy?x=1&amp;y=2">说明</a>与<code>SQL</code>。'},
                    {"type": "heading", "text": "详细范围"},
                    {"type": "table", "caption": "表格说明", "headers": ["数据", "用途"], "rows": [
                        ["<code>字段 A</code>", "第一行说明。"],
                        ["字段 B", "第二行说明。"],
                    ]},
                    {"type": "list", "items": ["第一项。", "第二项。"]},
                    {"type": "paragraph", "class": "contact", "html": '联系：<a href="mailto:policy@example.com">policy@example.com</a>'},
                ],
            }],
        }
        self.write_source()

    def write_source(self):
        self.source.write_bytes((json.dumps(self.data, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))

    def snapshot(self, root=None):
        root = root or self.output
        return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}

    def test_complete_text_format_and_inline_spacing(self):
        revision = build(self.source, self.output)
        expected = (
            "政策标题\n\n生效日期\n2026年10月11日\n\n"
            "介绍重点，保留 SQL 空格 & 内容。\n\n数据说明\n\n正文说明 (https://example.com/policy?x=1&y=2)与SQL。\n\n"
            "详细范围\n\n表格说明\n数据\n用途\n\n字段 A\n第一行说明。\n\n字段 B\n第二行说明。\n\n"
            "第一项。\n第二项。\n\n联系：policy@example.com\n"
        ).encode("utf-8")
        actual = (self.output / POLICY_FILE).read_bytes()
        self.assertEqual(actual, expected)
        self.assertEqual(revision, sha256(expected).hexdigest())
        self.assertNotIn("导航专用文字", actual.decode())
        self.assertNotIn("章节导航", actual.decode())
        self.assertNotIn("OrcaSQL Workbench · 隐私政策", actual.decode())

    def test_all_repository_source_wording_and_headings_are_preserved(self):
        source = json.loads(SOURCE.read_text(encoding="utf-8"))
        expected, headings = source_paragraphs(source)
        revision, files = policy_files(SOURCE)
        self.assertEqual(files[POLICY_FILE], expected)
        manifest = json.loads(files["manifest.json"])
        self.assertEqual(manifest["headings"], headings)
        self.assertEqual(manifest["sha256"], sha256(expected).hexdigest())
        self.assertEqual(manifest["sha256"], revision)
        self.assertEqual(manifest["effectiveDate"], source["effectiveDate"])
        self.assertNotIn("<dt>适用版本", files["index.html"].decode())

    def test_manifest_contract_hashes_complete_lf_bytes(self):
        revision = build(self.source, self.output)
        manifest = json.loads((self.output / "manifest.json").read_bytes())
        self.assertEqual(set(manifest), MANIFEST_FIELDS)
        self.assertEqual(manifest["schemaVersion"], 1)
        self.assertEqual(manifest["locale"], "zh-Hans")
        self.assertEqual(manifest["effectiveDate"], "2026-10-11")
        self.assertEqual(manifest["policyFile"], POLICY_FILE)
        self.assertEqual(manifest["policyUrl"], POLICY_URL + revision + "/")
        self.assertEqual(manifest["headings"], ["政策标题", "数据说明", "详细范围"])
        content = (self.output / POLICY_FILE).read_bytes()
        self.assertNotIn(b"\r", content)
        self.assertFalse(content.startswith(b"\xef\xbb\xbf"))
        self.assertTrue(content.endswith(b"\n"))
        self.assertFalse(content.endswith(b"\n\n"))
        self.assertNotEqual(sha256(content.rstrip(b"\n")).hexdigest(), manifest["sha256"])
        for name in FILES:
            self.assertEqual((self.output / name).read_bytes(), (self.output / "versions" / revision / name).read_bytes())

    def test_semantic_tables_links_csp_and_accessibility_are_retained(self):
        _, files = policy_files(self.source)
        html = files["index.html"].decode()
        document = Markup(html).root
        self.assertEqual([node.attrs["scope"] for node in document.descendants("th")], ["col", "col", "row", "row"])
        self.assertEqual([node.text() for node in document.descendants("caption")], ["表格说明"])
        links = [node.attrs["href"] for node in document.descendants("a")]
        self.assertIn("#policy", links)
        self.assertIn("#data", links)
        self.assertIn("/", links)
        self.assertIn("https://example.com/policy?x=1&y=2", links)
        self.assertIn("mailto:policy@example.com", links)
        self.assertIn('href="/assets/privacy.css"', html)
        self.assertIn('href="/assets/favicon.svg"', html)
        self.assertIn("default-src 'none'; img-src 'self'; style-src 'self'; base-uri 'none'; form-action 'none'; object-src 'none'", html)
        self.assertIn('<section id="data" tabindex="-1" aria-labelledby="data-title">', html)
        self.assertIn('<h2 id="data-title">数据说明</h2>', html)
        self.assertIn('<main id="policy" tabindex="-1">', html)
        self.assertIn('<nav aria-label="隐私政策章节">', html)
        self.assertNotIn("<script", html)

    def test_generation_is_deterministic_and_check_is_read_only(self):
        first = build(self.source, self.output)
        snapshot = self.snapshot()
        times = {path: path.stat().st_mtime_ns for path in self.output.rglob("*") if path.is_file()}
        self.assertEqual(build(self.source, self.output), first)
        self.assertEqual(build(self.source, self.output, check=True), first)
        self.assertEqual(self.snapshot(), snapshot)
        self.assertEqual({path: path.stat().st_mtime_ns for path in times}, times)

    def test_changed_policy_creates_new_revision_without_altering_old_archive(self):
        first = build(self.source, self.output)
        archive = self.output / "versions" / first
        original = self.snapshot(archive)
        self.data["sections"][0]["blocks"][0]["html"] = "修改后的正文。"
        self.data["effectiveDate"] = "2026-10-12"
        self.write_source()
        second = build(self.source, self.output)
        self.assertNotEqual(first, second)
        self.assertEqual(self.snapshot(archive), original)
        self.assertEqual({path.name for path in archive.parent.iterdir()}, {first, second})
        self.assertEqual(build(self.source, self.output, check=True), second)
        self.assertEqual(json.loads((self.output / "manifest.json").read_bytes())["effectiveDate"], "2026-10-12")

    def test_missing_and_stale_current_outputs_fail_check_and_are_rebuilt(self):
        build(self.source, self.output)
        original = self.snapshot()
        for name in sorted(FILES):
            path = self.output / name
            with self.subTest(name=name, state="stale"):
                path.write_bytes(b"stale\n")
                before = self.snapshot()
                with self.assertRaisesRegex(ValueError, "stale generated"):
                    build(self.source, self.output, check=True)
                self.assertEqual(self.snapshot(), before)
                build(self.source, self.output)
                self.assertEqual(self.snapshot(), original)
            with self.subTest(name=name, state="missing"):
                path.unlink()
                with self.assertRaisesRegex(ValueError, "stale generated"):
                    build(self.source, self.output, check=True)
                self.assertFalse(path.exists())
                build(self.source, self.output)
                self.assertEqual(self.snapshot(), original)

    def test_canonical_edits_cannot_leave_stale_outputs(self):
        build(self.source, self.output)
        original = self.snapshot()
        self.data["lead"] += "新增正文。"
        self.write_source()
        with self.assertRaisesRegex(ValueError, "stale generated"):
            build(self.source, self.output, check=True)
        self.assertEqual(self.snapshot(), original)

    def test_missing_archive_files_are_not_silently_repaired(self):
        revision = build(self.source, self.output)
        (self.output / "versions" / revision / POLICY_FILE).unlink()
        before = self.snapshot()
        for check in (False, True):
            with self.subTest(check=check), self.assertRaisesRegex(ValueError, "archive has missing"):
                build(self.source, self.output, check=check)
            self.assertEqual(self.snapshot(), before)

    def test_altered_historical_policy_is_rejected_before_current_outputs_change(self):
        first = build(self.source, self.output)
        archive = self.output / "versions" / first
        originals = self.snapshot(archive)
        self.data["lead"] += "更新。"
        self.write_source()
        build(self.source, self.output)
        changes = {
            POLICY_FILE: originals[POLICY_FILE] + b"changed\n",
            "index.html": originals["index.html"].replace("数据说明".encode(), "被改正文".encode()),
            "manifest.json": originals["manifest.json"].replace(b"2026-10-11", b"2026-10-12"),
        }
        for name, changed in changes.items():
            with self.subTest(name=name):
                (archive / name).write_bytes(changed)
                before = self.snapshot()
                for check in (False, True):
                    with self.assertRaisesRegex(ValueError, "Immutable policy archive"):
                        build(self.source, self.output, check=check)
                    self.assertEqual(self.snapshot(), before)
                (archive / name).write_bytes(originals[name])

    def test_href_only_changes_create_revisions_and_retain_archived_policy_links(self):
        first = build(self.source, self.output)
        archive = self.output / "versions" / first
        before = self.snapshot(archive)
        self.data["sections"][0]["blocks"][0]["html"] = self.data["sections"][0]["blocks"][0]["html"].replace("example.com", "other.example.com")
        self.write_source()
        second = build(self.source, self.output)
        self.assertNotEqual(first, second)
        self.assertEqual(self.snapshot(archive), before)
        self.assertIn(b"https://other.example.com/policy?x=1&y=2", (self.output / POLICY_FILE).read_bytes())

    def test_nonpolicy_page_updates_do_not_regenerate_existing_archives(self):
        revision = build(self.source, self.output)
        archive = self.output / "versions" / revision
        frozen = self.snapshot(archive)
        self.data["description"] = "更新后的页面说明。"
        self.write_source()
        self.assertEqual(build(self.source, self.output), revision)
        self.assertEqual(self.snapshot(archive), frozen)
        self.assertNotEqual((self.output / "index.html").read_bytes(), frozen["index.html"])
        self.assertEqual(build(self.source, self.output, check=True), revision)

    def test_malformed_and_unsupported_sources_are_rejected(self):
        original = copy.deepcopy(self.data)
        cases = [
            ("schemaVersion", 2), ("schemaVersion", True), ("locale", "en"),
            ("effectiveDate", "2026-02-30"), ("effectiveDate", "20261011"),
            ("title", ""), ("lead", "多行\n正文"), ("lead", "多行\u2028正文"), ("sections", []),
            ("lead", "<strong>未闭合"), ("lead", "<script>bad()</script>"),
            ("lead", '<a href="javascript:bad()">bad</a>'),
            ("lead", '<a href="https://example.com" onclick="bad()">bad</a>'),
            ("lead", "<strong class=\"unknown\">bad</strong>"),
            ("lead", "<!-- omitted -->正文"),
        ]
        for key, value in cases:
            with self.subTest(key=key, value=value):
                self.data = copy.deepcopy(original)
                self.data[key] = value
                self.write_source()
                with self.assertRaises(ValueError):
                    policy_files(self.source)
        self.data = copy.deepcopy(original)
        self.data["applicableVersions"] = ["0.1.0"]
        self.write_source()
        with self.assertRaisesRegex(ValueError, "Expected policy fields"):
            policy_files(self.source)
        for content in (b"{", b'{"schemaVersion": 1, "schemaVersion": 2}', b'{"schemaVersion": NaN}'):
            with self.subTest(content=content), self.assertRaises(ValueError):
                load_json(content)
        self.assertFalse(self.output.exists())

    def test_invalid_blocks_duplicate_headings_and_ids_are_rejected(self):
        original = copy.deepcopy(self.data)
        blocks = [
            {"type": "unknown"},
            {"type": "list", "items": []},
            {"type": "paragraph", "html": "正文", "class": "unknown"},
            {"type": "paragraph", "html": "正文", "unknown": "field"},
            {"type": "table", "caption": "表", "headers": ["列一", "列二"], "rows": [["缺一列"]]},
            {"type": "heading", "text": original["title"]},
        ]
        for block in blocks:
            with self.subTest(block=block):
                self.data = copy.deepcopy(original)
                self.data["sections"][0]["blocks"] = [block]
                self.write_source()
                with self.assertRaises(ValueError):
                    policy_files(self.source)
        for identifier in ("policy", "../escape", "data-title"):
            with self.subTest(identifier=identifier):
                self.data = copy.deepcopy(original)
                self.data["sections"].append({**copy.deepcopy(original["sections"][0]), "id": identifier})
                self.write_source()
                with self.assertRaises(ValueError):
                    policy_files(self.source)

    def test_manifests_are_strict_and_cannot_redirect_the_policy_file(self):
        revision, files = policy_files(self.source)
        manifest = json.loads(files["manifest.json"])
        changes = [
            ("schemaVersion", 2), ("schemaVersion", True), ("locale", "en"),
            ("effectiveDate", "bad"), ("policyFile", "../other.txt"),
            ("sha256", "0" * 64), ("policyUrl", "https://example.com/"),
            ("headings", []), ("headings", ["重复", "重复"]), ("headings", [""]),
            ("applicableVersions", ["0.1.0"]),
        ]
        for key, value in changes:
            with self.subTest(key=key):
                changed = {**manifest, key: value}
                with self.assertRaises(ValueError):
                    check_manifest(changed, revision)

    def test_primary_site_validator_blocks_stale_policy_exports(self):
        with patch("validate_site.build_policy", side_effect=ValueError("stale policy fixture")) as check:
            errors = validate_site.validate()
        self.assertTrue(any("stale policy fixture" in error for error in errors))
        self.assertEqual(check.call_args.kwargs["check"], True)
        self.assertEqual(check.call_args.kwargs["archive_base"], "HEAD")

    def test_offline_cli_check_never_writes_missing_outputs(self):
        command = [
            sys.executable, str(PROJECT / "scripts" / "build_privacy.py"),
            "--source", str(self.source), "--output", str(self.output), "--check",
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Missing or stale generated policy files", result.stderr)
        self.assertFalse(self.output.exists())
        build(self.source, self.output)
        before = self.snapshot()
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
