import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def pr_label(number):
    if not isinstance(number, int) or isinstance(number, bool) or number < 1:
        raise ValueError("The GitHub event or API response has an invalid PR number.")
    return f"PR #{number}"


def source_label(event_name, event, sha, repository, token):
    if not isinstance(event, dict):
        raise ValueError("The GitHub event must be a JSON object.")
    if event_name == "pull_request":
        return pr_label(event.get("number"))
    if event_name == "workflow_dispatch":
        return "Manual"
    if event_name != "push":
        raise ValueError(f"Unsupported GitHub event: {event_name}.")
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", sha):
        raise ValueError("A push requires a complete Git commit SHA.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("A push requires a GitHub repository in owner/name form.")
    ref = event.get("ref", "")
    if not isinstance(ref, str) or not ref.startswith("refs/heads/") or not ref.removeprefix("refs/heads/"):
        raise ValueError("A push requires a branch ref.")
    if not token:
        raise ValueError("GITHUB_TOKEN is required to associate a push with its merged PR.")

    matches = set()
    page = 1
    while True:
        request = Request(
            f"https://api.github.com/repos/{repository}/commits/{sha}/pulls?per_page=100&page={page}",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urlopen(request, timeout=20) as response:
                pulls = json.load(response)
        except HTTPError as error:
            raise RuntimeError(f"GitHub PR lookup failed (HTTP {error.code}).") from error
        except (URLError, TimeoutError) as error:
            raise RuntimeError("GitHub PR lookup failed: unable to contact the API.") from error
        if not isinstance(pulls, list):
            raise ValueError("GitHub PR lookup must return a JSON array.")
        for pull in pulls:
            if not isinstance(pull, dict) or not isinstance(pull.get("base"), dict):
                raise ValueError("GitHub PR lookup returned an invalid pull request.")
            if (pull.get("merged_at") and pull.get("merge_commit_sha") == sha
                    and pull["base"].get("ref") == ref.removeprefix("refs/heads/")):
                matches.add(pr_label(pull.get("number")))
        if len(pulls) < 100:
            break
        page += 1
    return next(iter(matches)) if len(matches) == 1 else f"Push {sha[:7]}"


def main():
    required = ("GITHUB_EVENT_NAME", "GITHUB_EVENT_PATH", "GITHUB_SHA", "GITHUB_REPOSITORY", "GITHUB_OUTPUT")
    for name in required:
        if not os.environ.get(name):
            raise ValueError(f"{name} is required.")
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    label = source_label(
        os.environ["GITHUB_EVENT_NAME"], event, os.environ["GITHUB_SHA"],
        os.environ["GITHUB_REPOSITORY"], os.environ.get("GITHUB_TOKEN", ""),
    )
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8", newline="\n") as output:
        output.write(f"label={label}\n")
    print(f"Workflow source: {label}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
