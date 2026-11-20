#!/usr/bin/env python3
"""Report bot pull requests that may be preventing newer dependency updates."""

from datetime import datetime, timedelta, timezone
import json
import os
import subprocess


def gh(endpoint):
    response = subprocess.check_output(["gh", "api", endpoint, "--paginate", "--slurp"])
    return [item for page in json.loads(response) for item in page]


def main():
    repository = os.environ["GITHUB_REPOSITORY"]
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    stale = []
    for pull in gh(f"repos/{repository}/pulls?state=open"):
        if pull["user"]["login"] != "dependabot[bot]":
            continue
        timestamp = datetime.fromisoformat(pull["created_at"])
        comments = gh(f"repos/{repository}/issues/{pull['number']}/comments")
        rebases = sum(
            comment["user"]["login"] == "dependabot[bot]" and "dependabot is rebasing" in comment["body"].lower()
            for comment in comments
        )
        if timestamp < cutoff or rebases > 2:
            stale.append(f"{pull['html_url']} is open since {timestamp.date()} with {rebases} rebase notices")
    if stale:
        for item in stale:
            print(f"::error::{item}")
        return 1
    print("No open Dependabot pull requests exceed the age or rebase limit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
