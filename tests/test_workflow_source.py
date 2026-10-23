from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from workflow_source import main, source_label


class WorkflowSourceTests(unittest.TestCase):
    sha = "0123456789abcdef0123456789abcdef01234567"
    repository = "OrcaSQL-Workbench/orcasql-workbench.github.io"
    token = "fixture-token"

    def pull(self, number=100, **overrides):
        return {
            "number": number,
            "merged_at": "2026-10-23T03:47:00Z",
            "merge_commit_sha": self.sha,
            "base": {"ref": "main"},
            **overrides,
        }

    def response(self, payload):
        return BytesIO(json.dumps(payload).encode("utf-8"))

    def resolve(self, event_name="push", event=None):
        return source_label(
            event_name, {"ref": "refs/heads/main"} if event is None else event,
            self.sha, self.repository, self.token,
        )

    def test_pr_uses_its_number_without_querying_the_api(self):
        with patch("workflow_source.urlopen") as lookup:
            self.assertEqual(self.resolve("pull_request", {"number": 100}), "PR #100")
        lookup.assert_not_called()

    def test_manual_run_does_not_claim_a_pr(self):
        with patch("workflow_source.urlopen") as lookup:
            self.assertEqual(self.resolve("workflow_dispatch", {}), "Manual")
        lookup.assert_not_called()

    def test_push_matches_the_merge_commit_and_target_branch(self):
        with patch("workflow_source.urlopen", return_value=self.response([self.pull()])) as lookup:
            self.assertEqual(self.resolve(), "PR #100")
        request = lookup.call_args.args[0]
        self.assertEqual(
            request.full_url,
            f"https://api.github.com/repos/{self.repository}/commits/{self.sha}/pulls?per_page=100&page=1",
        )
        self.assertEqual(request.get_header("Authorization"), f"Bearer {self.token}")
        self.assertEqual(lookup.call_args.kwargs["timeout"], 20)

    def test_open_pr_other_branch_and_other_merge_commit_are_not_used(self):
        pulls = [
            self.pull(101, merged_at=None),
            self.pull(102, base={"ref": "release"}),
            self.pull(103, merge_commit_sha="a" * 40),
            self.pull(),
        ]
        with patch("workflow_source.urlopen", return_value=self.response(pulls)):
            self.assertEqual(self.resolve(), "PR #100")

    def test_missing_or_ambiguous_pr_uses_the_commit_without_guessing(self):
        for pulls in ([], [self.pull(100), self.pull(101)]):
            with self.subTest(pulls=pulls), \
                    patch("workflow_source.urlopen", return_value=self.response(pulls)):
                self.assertEqual(self.resolve(), f"Push {self.sha[:7]}")

    def test_other_branches_match_only_their_own_merged_pr(self):
        pulls = [self.pull(), self.pull(101, base={"ref": "release"})]
        with patch("workflow_source.urlopen", return_value=self.response(pulls)):
            self.assertEqual(self.resolve(event={"ref": "refs/heads/release"}), "PR #101")

    def test_all_pages_are_checked_before_selecting_a_pr(self):
        first = [self.pull(number, merged_at=None) for number in range(1, 101)]
        with patch("workflow_source.urlopen", side_effect=[
            self.response(first), self.response([self.pull()]),
        ]) as lookup:
            self.assertEqual(self.resolve(), "PR #100")
        self.assertEqual(lookup.call_count, 2)
        self.assertTrue(lookup.call_args.args[0].full_url.endswith("page=2"))

    def test_a_later_page_can_make_the_pr_association_ambiguous(self):
        first = [self.pull(), *[self.pull(number, merged_at=None) for number in range(1, 100)]]
        with patch("workflow_source.urlopen", side_effect=[
            self.response(first), self.response([self.pull(101)]),
        ]):
            self.assertEqual(self.resolve(), f"Push {self.sha[:7]}")

    def test_invalid_pr_numbers_fail_before_they_can_become_job_names(self):
        for number in (None, True, 0, -1, "100\nlabel=other"):
            with self.subTest(number=number):
                with self.assertRaisesRegex(ValueError, "invalid PR number"):
                    self.resolve("pull_request", {"number": number})
                with patch("workflow_source.urlopen", return_value=self.response([self.pull(number)])):
                    with self.assertRaisesRegex(ValueError, "invalid PR number"):
                        self.resolve()

    def test_invalid_events_and_push_inputs_fail_explicitly(self):
        cases = [
            {"event_name": "schedule"},
            {"event": []},
            {"sha": "short"},
            {"repository": "invalid"},
            {"event": {"ref": "refs/tags/v1"}},
            {"event": {"ref": "refs/heads/"}},
            {"token": ""},
        ]
        for overrides in cases:
            arguments = {
                "event_name": "push", "event": {"ref": "refs/heads/main"}, "sha": self.sha,
                "repository": self.repository, "token": self.token, **overrides,
            }
            with self.subTest(overrides=overrides), patch("workflow_source.urlopen") as lookup:
                with self.assertRaises(ValueError):
                    source_label(**arguments)
                lookup.assert_not_called()

    def test_api_errors_are_not_reported_as_a_direct_push(self):
        errors = [
            HTTPError("https://api.github.com", 403, self.token, {}, BytesIO()),
            URLError(self.token),
            TimeoutError(self.token),
        ]
        for error in errors:
            with self.subTest(error=type(error).__name__), \
                    patch("workflow_source.urlopen", side_effect=error):
                with self.assertRaisesRegex(RuntimeError, "GitHub PR lookup failed") as failure:
                    self.resolve()
                self.assertNotIn(self.token, str(failure.exception))

    def test_invalid_api_responses_fail_explicitly(self):
        for payload in ({}, [None], [{"number": 100}]):
            with self.subTest(payload=payload), \
                    patch("workflow_source.urlopen", return_value=self.response(payload)):
                with self.assertRaises(ValueError):
                    self.resolve()
        with patch("workflow_source.urlopen", return_value=BytesIO(b"not-json")):
            with self.assertRaises(ValueError):
                self.resolve()

    def test_main_appends_a_single_safe_github_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            event_path = root / "event.json"
            output_path = root / "output"
            event_path.write_text('{"number": 100}', encoding="utf-8")
            output_path.write_bytes(b"existing=value\n")
            environment = {
                "GITHUB_EVENT_NAME": "pull_request", "GITHUB_EVENT_PATH": str(event_path),
                "GITHUB_SHA": self.sha, "GITHUB_REPOSITORY": self.repository,
                "GITHUB_OUTPUT": str(output_path),
            }
            with patch.dict(os.environ, environment, clear=True), \
                    patch("workflow_source.urlopen") as lookup, \
                    patch("sys.stdout", new_callable=StringIO) as output:
                main()
            lookup.assert_not_called()
            self.assertEqual(output_path.read_bytes(), b"existing=value\nlabel=PR #100\n")
            self.assertEqual(output.getvalue(), "Workflow source: PR #100\n")

    def test_main_requires_the_github_actions_environment(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "GITHUB_EVENT_NAME is required"):
                main()


if __name__ == "__main__":
    unittest.main()
