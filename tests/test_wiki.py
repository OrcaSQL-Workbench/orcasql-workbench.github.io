import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import ANY, patch


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from build_docs import MANUALS, REPOSITORY_URL
from sync_wiki import git, sync


class WikiSyncTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {
            "WIKI_SYNC_TOKEN": "fixture-token",
            "GITHUB_REPOSITORY": REPOSITORY_URL.removeprefix("https://github.com/"),
            "GITHUB_SHA": "0123456789abcdef",
        }, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_each_manual_syncs_only_its_configured_repository(self):
        for name, manual in MANUALS.items():
            with self.subTest(manual=name), \
                    patch("sync_wiki.git", return_value="Home.md") as run_git, \
                    patch("sync_wiki.export_wiki", return_value=["Home.md"]) as export:
                sync(name)
                arguments = run_git.call_args_list[0].args[0]
                self.assertEqual(arguments[:4], [
                    "clone", "--depth", "1", manual.repository_url + ".wiki.git",
                ])
                export.assert_called_once_with(manual.source, ANY, manual=manual)
                run_git.assert_any_call(["push", "origin", "HEAD"], ANY, ANY)
                self.assertNotIn("fixture-token", repr(arguments))

    def test_arkdb_missing_token_names_initialization_target(self):
        os.environ.pop("WIKI_SYNC_TOKEN")
        with patch("sync_wiki.git") as run_git:
            with self.assertRaisesRegex(ValueError, "ArkDB/wiki/Home"):
                sync("arkdb")
        run_git.assert_not_called()

    def test_workflow_cannot_run_from_another_source_repository(self):
        os.environ["GITHUB_REPOSITORY"] = "OrcaSQL-Workbench/ArkDB"
        with patch("sync_wiki.git") as run_git:
            with self.assertRaisesRegex(ValueError, "documentation source repository"):
                sync("arkdb")
        run_git.assert_not_called()

    def test_unchanged_wiki_is_not_committed_or_pushed(self):
        with patch("sync_wiki.git", return_value="") as run_git, \
                patch("sync_wiki.export_wiki", return_value=["Home.md"]):
            sync("arkdb")
        verbs = [call.args[0][0] for call in run_git.call_args_list]
        self.assertNotIn("commit", verbs)
        self.assertNotIn("push", verbs)

    def test_git_failure_is_explicit_without_raw_credential_output(self):
        failed = subprocess.CompletedProcess(["git", "clone"], 128, "", "fixture-sensitive-output")
        with patch("sync_wiki.subprocess.run", return_value=failed):
            with self.assertRaisesRegex(RuntimeError, "Wiki Git clone failed") as error:
                git(["clone", "https://github.com/example/wiki.git"], None, {})
        self.assertNotIn("fixture-sensitive-output", str(error.exception))


if __name__ == "__main__":
    unittest.main()
