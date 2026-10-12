import base64
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from build_docs import PROJECT, REPOSITORY_URL, export_wiki


def git(arguments, directory, environment):
    result = subprocess.run(
        ["git", *arguments],
        cwd=directory,
        env=environment,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"Wiki Git {arguments[0]} failed (exit {result.returncode}). "
            "Confirm the Wiki has an initial page and WIKI_SYNC_TOKEN can write it."
        )
    return result.stdout.strip()


def sync():
    token = os.environ.get("WIKI_SYNC_TOKEN", "")
    if not token:
        raise ValueError(
            "WIKI_SYNC_TOKEN is not configured. Initialize the Wiki Home page and add "
            "a dedicated Wiki-write token in this repository's Actions secrets; never paste it into chat."
        )
    repository = os.environ.get("GITHUB_REPOSITORY", "OrcaSQL-Workbench/orcasql-workbench.github.io")
    if REPOSITORY_URL != f"https://github.com/{repository}":
        raise ValueError("The Wiki sync target must be the configured documentation repository.")
    environment = os.environ.copy()
    for name in tuple(environment):
        if name.startswith("GIT_TRACE") or name in ("GIT_CURL_VERBOSE", "GIT_CONFIG_COUNT"):
            environment.pop(name)
    credential = base64.b64encode(f"x-access-token:{token}".encode("utf-8")).decode("ascii")
    environment.update({
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
        "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {credential}",
    })
    with tempfile.TemporaryDirectory(prefix="orcasql-wiki-") as temporary:
        root = Path(temporary)
        directory = root / "wiki"
        git(["clone", "--depth", "1", f"{REPOSITORY_URL}.wiki.git", str(directory)], root, environment)
        changed = export_wiki(PROJECT / "docs", directory)
        git(["add", "--", *changed], directory, environment)
        if not git(["diff", "--cached", "--name-only"], directory, environment):
            print("Wiki already matches the documentation source.")
            return
        git(["config", "user.name", "github-actions[bot]"], directory, environment)
        git(["config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], directory, environment)
        revision = os.environ.get("GITHUB_SHA", "")[:12]
        message = "docs: sync user guides" + (f" from {revision}" if revision else "")
        git([
            "commit", "-m", message, "-m",
            "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>",
        ], directory, environment)
        git(["push", "origin", "HEAD"], directory, environment)
        print("Published the managed documentation pages to GitHub Wiki.")


if __name__ == "__main__":
    try:
        sync()
    except (ValueError, RuntimeError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
