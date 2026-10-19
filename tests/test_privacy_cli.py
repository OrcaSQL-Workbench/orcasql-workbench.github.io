from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parent.parent


class PrivacyCliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="privacy-cli-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.script = self.root / "scripts" / "build_privacy.py"
        self.source = self.root / "privacy" / "policy-zh-Hans.json"
        self.output = self.root / "site" / "privacy"
        self.hooks = self.root / "empty-hooks"
        self.script.parent.mkdir()
        self.source.parent.mkdir()
        self.hooks.mkdir()
        shutil.copyfile(PROJECT / "scripts" / "build_privacy.py", self.script)
        shutil.copyfile(PROJECT / "privacy" / "policy-zh-Hans.json", self.source)
        self.data = json.loads(self.source.read_bytes())
        self.environment = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
        self.environment.update({
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "PYTHONIOENCODING": "utf-8",
        })
        self.git("init", "--quiet", "--initial-branch=main", "--template=" + str(self.hooks))
        self.commit("fixture inputs")

    def command(self, arguments):
        return subprocess.run(
            arguments, cwd=self.root, env=self.environment, capture_output=True,
            text=True, encoding="utf-8", timeout=120,
        )

    def git(self, *arguments):
        result = self.command([
            "git", "--no-pager", "-c", "user.name=Policy tests",
            "-c", "user.email=privacy-tests@example.invalid", "-c", "commit.gpgsign=false",
            "-c", "core.autocrlf=false", "-c", "core.hooksPath=" + str(self.hooks), *arguments,
        ])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.strip()

    def commit(self, subject):
        self.git("add", "--all")
        self.git(
            "commit", "--quiet", "-m",
            subject + "\n\nCo-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>",
        )
        return self.git("rev-parse", "HEAD")

    def run_cli(self, *arguments):
        return self.command([sys.executable, "-B", str(self.script), *arguments])

    def require_success(self, *arguments):
        result = self.run_cli(*arguments)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def write_source(self):
        self.source.write_bytes((json.dumps(self.data, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))

    def manifest(self):
        return json.loads((self.output / "manifest.json").read_bytes())

    def snapshot(self):
        return {
            path.relative_to(self.output).as_posix(): path.read_bytes()
            for path in self.output.rglob("*") if path.is_file()
        }

    def assert_rejected_without_writes(self, reason):
        original = self.snapshot()
        for arguments in [(), ("--check",)]:
            with self.subTest(arguments=arguments):
                result = self.run_cli(*arguments)
                self.assertEqual(result.returncode, 1, "Incompatible policy was accepted: " + result.stdout)
                self.assertIn(reason, result.stderr)
                self.assertEqual(self.snapshot(), original, "Rejected policy partially rewrote generated exports.")

    def test_committed_archive_damage_is_remembered_and_original_bytes_can_be_restored(self):
        self.require_success()
        first = self.manifest()["sha256"]
        self.commit("publish first fixture policy")
        archive = self.output / "versions" / first
        original = {path.name: path.read_bytes() for path in archive.iterdir()}
        self.data["lead"] += " Fixture revision B."
        self.write_source()
        self.require_success()
        published = self.commit("publish second fixture policy retaining history")
        for path in archive.iterdir():
            path.unlink()
        archive.rmdir()
        deletion = self.commit("fixture committed archive deletion")
        for arguments in [("--check",), ("--check", "--archive-base", "HEAD"),
                          ("--check", "--archive-base", published), ()]:
            with self.subTest(damage="deletion", arguments=arguments):
                before = self.snapshot()
                result = self.run_cli(*arguments)
                self.assertEqual(result.returncode, 1, "Committed archive deletion was forgotten: " + result.stdout)
                self.assertIn(first, result.stderr)
                self.assertEqual(self.snapshot(), before)
        (self.root / "unrelated.txt").write_bytes(b"Later unrelated push.\n")
        self.commit("fixture later push after archive loss")
        result = self.run_cli("--check", "--archive-base", deletion)
        self.assertEqual(result.returncode, 1, "A later baseline forgot the deleted archive.")
        self.assertIn(first, result.stderr)
        archive.mkdir()
        for name, content in original.items():
            (archive / name).write_bytes(content)
        self.require_success("--check", "--archive-base", deletion)
        self.commit("restore original fixture archive")
        (archive / "index.html").write_bytes(original["index.html"] + b"<!-- changed archived bytes -->\n")
        mutation = self.commit("fixture committed archive byte mutation")
        result = self.run_cli("--check")
        self.assertEqual(result.returncode, 1, "Committed archive byte mutation was forgotten.")
        self.assertIn(first, result.stderr)
        (archive / "index.html").write_bytes(original["index.html"])
        self.require_success("--check", "--archive-base", mutation)
        self.commit("restore original archived bytes after mutation")
        self.data["lead"] += " Fixture revision C."
        self.write_source()
        self.require_success()
        self.require_success("--check")
        self.assertEqual({path.name: path.read_bytes() for path in archive.iterdir()}, original)

    def test_all_inline_surfaces_export_destinations_and_href_only_changes_create_revisions(self):
        blocks = self.data["sections"][0]["blocks"]
        table = blocks[1]
        items = {"type": "list", "items": ["list link"]}
        blocks.append(items)
        surfaces = [
            (self.data, "lead"), (blocks[0], "html"), (items["items"], 0),
            (table, "caption"), (table["headers"], 0),
            (table["rows"][0], 0), (table["rows"][0], 1),
        ]
        for index, (container, key) in enumerate(surfaces):
            container[key] = f'<a href="https://example.com/{index}?a=1&amp;b=2#old">Service policy {index}</a>'
        self.write_source()
        self.require_success()
        self.commit("publish fixture links in all inline surfaces")
        first = self.manifest()["sha256"]
        archive = self.output / "versions" / first
        original = {path.name: path.read_bytes() for path in archive.iterdir()}
        txt = (self.output / "policy-zh-Hans.txt").read_text(encoding="utf-8")
        for index, (container, key) in enumerate(surfaces):
            with self.subTest(surface=index, state="readable"):
                self.assertTrue(
                    f"Service policy {index} (https://example.com/{index}?a=1&b=2#old)" in txt,
                    f"Missing readable destination on inline surface {index}.",
                )
            previous = self.manifest()["sha256"]
            container[key] = container[key].replace("#old", "#new")
            self.write_source()
            with self.subTest(surface=index, state="href-only"):
                self.require_success()
                self.assertNotEqual(self.manifest()["sha256"], previous)
                self.assertIn(
                    f"https://example.com/{index}?a=1&b=2#new",
                    (self.output / "policy-zh-Hans.txt").read_text(encoding="utf-8"),
                )
                self.require_success("--check")
                self.assertEqual({path.name: path.read_bytes() for path in archive.iterdir()}, original)

    def test_missing_or_shallow_history_is_an_explicit_failure_without_writes(self):
        self.require_success()
        self.commit("publish fixture before testing incomplete history")
        before = self.snapshot()
        result = self.run_cli("--check", "--archive-base", "missing-fixture-reference")
        self.assertEqual(result.returncode, 1)
        self.assertIn("history", result.stderr)
        self.assertEqual(self.snapshot(), before)
        shallow = self.root / "shallow"
        self.git("clone", "--quiet", "--depth=1", self.root.as_uri(), str(shallow))
        output = shallow / "site" / "privacy"
        frozen = {path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()}
        result = self.command([sys.executable, "-B", str(shallow / "scripts" / "build_privacy.py"), "--check"])
        self.assertEqual(result.returncode, 1)
        self.assertIn("Complete policy archive history is required", result.stderr)
        self.assertEqual({path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()}, frozen)

    def test_unmerged_branches_are_excluded_but_first_parent_merges_are_remembered(self):
        self.require_success()
        self.commit("publish fixture main policy")
        self.git("switch", "--quiet", "-c", "unrelated")
        self.data["lead"] += " Fixture side-branch policy."
        self.write_source()
        self.require_success()
        side_revision = self.manifest()["sha256"]
        self.commit("fixture policy not on deployment lineage")
        self.git("switch", "--quiet", "main")
        self.require_success("--check")
        self.git(
            "merge", "--quiet", "--no-ff", "unrelated", "-m",
            "merge fixture policy\n\nCo-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>",
        )
        self.require_success("--check")
        self.data["lead"] += " Fixture later main policy."
        self.write_source()
        self.require_success()
        self.commit("publish fixture after merging side policy")
        archive = self.output / "versions" / side_revision
        for path in archive.iterdir():
            path.unlink()
        archive.rmdir()
        self.commit("fixture loss of archive introduced by first-parent merge")
        result = self.run_cli("--check")
        self.assertEqual(result.returncode, 1)
        self.assertIn(side_revision, result.stderr)

    def test_legacy_link_projection_archives_are_retained_during_format_migration(self):
        block = self.data["sections"][0]["blocks"][0]
        block["html"] = 'Read <a href="https://example.com/legacy">service policy</a>.'
        self.write_source()
        self.require_success()
        revision = self.manifest()["sha256"]
        current = {path.name: path.read_bytes() for path in (self.output / "versions" / revision).iterdir()}
        legacy = current["policy-zh-Hans.txt"].replace(b" (https://example.com/legacy)", b"")
        legacy_revision = sha256(legacy).hexdigest()
        manifest = self.manifest()
        manifest["sha256"] = legacy_revision
        manifest["policyUrl"] = f"https://orcasql-workbench.github.io/privacy/versions/{legacy_revision}/"
        files = {
            **current,
            "policy-zh-Hans.txt": legacy,
            "manifest.json": (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        }
        old = self.output / "versions" / legacy_revision
        old.mkdir()
        for name, content in files.items():
            (old / name).write_bytes(content)
            (self.output / name).write_bytes(content)
            (self.output / "versions" / revision / name).unlink()
        (self.output / "versions" / revision).rmdir()
        self.commit("fixture archive from original v1 text projection")
        self.require_success()
        self.assertEqual(self.manifest()["sha256"], revision)
        self.assertEqual({path.name: path.read_bytes() for path in old.iterdir()}, files)
        self.require_success("--check")

    def test_only_exact_self_describing_mailto_links_omit_a_destination_suffix(self):
        self.require_success()
        original_revision = self.manifest()["sha256"]
        contact = next(section for section in self.data["sections"] if section["id"] == "contact")["blocks"][0]
        original = contact["html"]
        self.assertNotIn(b"(mailto:", (self.output / "policy-zh-Hans.txt").read_bytes())
        for href in [
            "mailto:shawnxxy@me.com?subject=privacy", "mailto:shawnxxy@me.com#contact",
            "MAILTO:shawnxxy@me.com", "https://example.com/contact", "mailto:other@example.com",
        ]:
            with self.subTest(href=href):
                contact["html"] = original.replace("mailto:shawnxxy@me.com", href)
                self.write_source()
                self.require_success()
                self.assertNotEqual(self.manifest()["sha256"], original_revision)
                self.assertIn(f"shawnxxy@me.com ({href})", (self.output / "policy-zh-Hans.txt").read_text(encoding="utf-8"))
                self.require_success("--check")

    def test_txt_accepts_65536_utf8_bytes_and_rejects_one_over_without_writes(self):
        self.require_success()
        block = self.data["sections"][0]["blocks"][0]
        length = len((self.output / "policy-zh-Hans.txt").read_bytes())
        block["html"] += "x" * (65536 - length)
        self.write_source()
        self.require_success()
        self.require_success("--check")
        complete = (self.output / "policy-zh-Hans.txt").read_bytes()
        self.assertEqual(len(complete), 65536)
        self.assertEqual(self.manifest()["sha256"], sha256(complete).hexdigest())
        block["html"] += "x"
        self.write_source()
        self.assert_rejected_without_writes("65536")
        absent = self.root / "rejected-output"
        result = self.run_cli("--output", str(absent))
        self.assertEqual(result.returncode, 1)
        self.assertFalse(absent.exists())

    def test_heading_limit_counts_200_utf16_units_for_ascii_and_astral_unicode(self):
        for heading in ("T" * 200, "\U0001f30a" * 100):
            with self.subTest(heading_type="ASCII" if heading.startswith("T") else "astral"):
                self.data["title"] = heading
                self.write_source()
                self.require_success()
                self.require_success("--check")
                self.assertEqual(self.manifest()["headings"][0], heading)
                self.data["title"] += "X"
                self.write_source()
                self.assert_rejected_without_writes("200 UTF-16")

    def test_heading_count_accepts_2_and_64_but_rejects_65_without_writes(self):
        self.data["sections"] = [{
            "id": "scope", "title": "Scope", "navigationTitle": "Scope",
            "blocks": [{"type": "paragraph", "html": "Complete policy body."}],
        }]
        self.write_source()
        self.require_success()
        self.assertEqual(len(self.manifest()["headings"]), 2)
        headings = [{"type": "heading", "text": f"Heading {index}"} for index in range(62)]
        self.data["sections"][0]["blocks"][0:0] = headings
        self.write_source()
        self.require_success()
        self.require_success("--check")
        self.assertEqual(len(self.manifest()["headings"]), 64)
        self.data["sections"][0]["blocks"].insert(0, {"type": "heading", "text": "Heading one over"})
        self.write_source()
        self.assert_rejected_without_writes("2 to 64")

    def test_manifest_accepts_32768_utf8_bytes_and_rejects_one_over_without_writes(self):
        headings = [f"H{index:02d}" + "\u754c" * 160 for index in range(64)]
        example = {
            "schemaVersion": 1, "locale": "zh-Hans", "effectiveDate": "2026-10-11",
            "policyFile": "policy-zh-Hans.txt", "sha256": "0" * 64, "headings": headings,
            "policyUrl": "https://orcasql-workbench.github.io/privacy/versions/" + "0" * 64 + "/",
        }
        remaining = 32768 - len((json.dumps(example, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        self.assertGreaterEqual(remaining, 0)
        for index in range(len(headings)):
            extra = min(remaining, 35)
            headings[index] += "x" * extra
            remaining -= extra
        self.assertEqual(remaining, 0)
        self.data["title"] = headings[0]
        self.data["sections"] = [{
            "id": "scope", "title": headings[1], "navigationTitle": "Scope",
            "blocks": [
                *[{"type": "heading", "text": heading} for heading in headings[2:]],
                {"type": "paragraph", "html": "Complete policy body."},
            ],
        }]
        self.write_source()
        self.require_success()
        self.require_success("--check")
        self.assertEqual(len((self.output / "manifest.json").read_bytes()), 32768)
        self.assertLess(len((self.output / "policy-zh-Hans.txt").read_bytes()), 65536)
        self.data["sections"][0]["blocks"][-2]["text"] += "x"
        self.write_source()
        self.assert_rejected_without_writes("32768")

    def test_decoded_forbidden_characters_and_unpaired_surrogates_never_rewrite_exports(self):
        self.require_success()
        block = self.data["sections"][0]["blocks"][0]
        original = block["html"]
        for value in ["&#0;", "&#xfffd;", "\ufffd", "&#xfeff;", "\ufeff", "&#13;", "&#127;", "\ud800", "\udfff"]:
            with self.subTest(value=ascii(value)):
                block["html"] = value + original
                self.source.write_bytes((json.dumps(self.data, ensure_ascii=True, indent=2) + "\n").encode("ascii"))
                self.assert_rejected_without_writes("Policy")
        block["html"] = original + " C1 characters: \u0081\u009f."
        self.write_source()
        self.require_success()
        self.require_success("--check")
        self.assertIn("\u0081\u009f".encode("utf-8"), (self.output / "policy-zh-Hans.txt").read_bytes())

    def test_exports_require_a_complete_body_and_unambiguous_ordered_headings(self):
        self.require_success()
        blocks = self.data["sections"][-1]["blocks"]
        original = list(blocks)
        self.data["sections"][-1]["blocks"] = [{"type": "heading", "text": "Final heading without body"}]
        self.write_source()
        with self.subTest(case="missing final body"):
            self.assert_rejected_without_writes("body after")
        self.data["sections"][-1]["blocks"] = original
        for heading in (self.data["title"], self.data["sections"][-1]["title"]):
            with self.subTest(case="ambiguous heading", heading=heading):
                self.data["sections"][-1]["blocks"] = [{"type": "paragraph", "html": heading}]
                self.write_source()
                self.assert_rejected_without_writes("exactly once")


if __name__ == "__main__":
    unittest.main()
