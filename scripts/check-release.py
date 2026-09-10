#!/usr/bin/env python3
"""Wait for the required protected-main checks of one exact commit.

GitHub's CodeQL default setup exposes a PR-level ``CodeQL`` aggregate check,
but a push to ``main`` can expose only its three language-analysis check runs.
The latter are accepted as the exact-commit CodeQL proof only when all three
are complete and successful; a present aggregate failure is never bypassed.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request


REQUIRED = (
    "Verify",
    "Analyze (actions)",
    "Analyze (javascript-typescript)",
    "Analyze (python)",
    "CodeQL",
)
CODEQL_ANALYSES = REQUIRED[1:4]


def api_get(repository: str, sha: str, token: str) -> dict:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/commits/{sha}/check-runs?per_page=100",
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "claudiuschuster-release-check/1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            value = json.load(response)
    except (OSError, urllib.error.HTTPError):
        raise RuntimeError("github_checks_unavailable") from None
    if not isinstance(value, dict) or not isinstance(value.get("check_runs"), list):
        raise RuntimeError("github_checks_invalid")
    return value


def summarize(value: dict) -> dict:
    latest: dict[str, dict] = {}
    for item in value["check_runs"]:
        name = item.get("name")
        if name not in REQUIRED:
            continue
        current = latest.get(name)
        if current is None or str(item.get("completed_at") or item.get("started_at") or "") > str(
            current.get("completed_at") or current.get("started_at") or ""
        ):
            latest[name] = item
    states: dict[str, dict] = {}
    for name in REQUIRED:
        item = latest.get(name)
        states[name] = (
            {
                "status": item.get("status"),
                "conclusion": item.get("conclusion"),
                "source": "check_run",
            }
            if item
            else {"status": "missing", "conclusion": None, "source": "check_run"}
        )

    if "CodeQL" not in latest:
        analyses = [states[name] for name in CODEQL_ANALYSES]
        if all(
            state["status"] == "completed" and state["conclusion"] == "success"
            for state in analyses
        ):
            states["CodeQL"] = {
                "status": "completed",
                "conclusion": "success",
                "source": "analyze_jobs_fallback",
            }
        elif any(state["status"] in {"queued", "in_progress"} for state in analyses):
            states["CodeQL"] = {
                "status": "in_progress",
                "conclusion": None,
                "source": "analyze_jobs_fallback",
            }
        elif any(state["status"] == "missing" for state in analyses):
            states["CodeQL"] = {
                "status": "missing",
                "conclusion": None,
                "source": "analyze_jobs_fallback",
            }
        else:
            states["CodeQL"] = {
                "status": "completed",
                "conclusion": "failure",
                "source": "analyze_jobs_fallback",
            }
    return {
        "schema": 1,
        "required": list(REQUIRED),
        "states": states,
        "all_success": all(
            states[name]["status"] == "completed"
            and states[name]["conclusion"] == "success"
            for name in REQUIRED
        ),
    }


def check_state(value: dict) -> tuple[str, list[str]]:
    """Classify an exact-SHA result without waiting on terminal failures."""
    if value["all_success"]:
        return "success", []
    failed = [
        name
        for name, state in value["states"].items()
        if state["status"] == "completed" and state["conclusion"] != "success"
    ]
    if failed:
        return "failed", failed
    missing = [
        name for name, state in value["states"].items() if state["status"] == "missing"
    ]
    if missing:
        return "missing", missing
    return "waiting", []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sha", required=True)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--wait-seconds", type=int, default=600)
    parser.add_argument("--missing-grace-seconds", type=int, default=90)
    args = parser.parse_args()
    if (
        len(args.sha) != 40
        or any(char not in "0123456789abcdef" for char in args.sha)
        or not args.repository
        or args.wait_seconds < 0
        or args.missing_grace_seconds < 0
    ):
        print(json.dumps({"error": "invalid_arguments", "all_success": False}))
        return 2
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print(json.dumps({"error": "missing_github_credential", "all_success": False}))
        return 1
    deadline = time.monotonic() + args.wait_seconds
    missing_deadline = time.monotonic() + min(args.wait_seconds, args.missing_grace_seconds)
    latest = {"schema": 1, "required": list(REQUIRED), "states": {}, "all_success": False}
    while True:
        try:
            latest = summarize(api_get(args.repository, args.sha, token))
        except RuntimeError as error:
            print(json.dumps({"error": str(error), "all_success": False}))
            return 1
        state, names = check_state(latest)
        if state == "success":
            print(json.dumps(latest, indent=2, sort_keys=True))
            return 0
        if state == "failed":
            latest["error"] = "required_checks_failed"
            latest["failed_checks"] = names
            print(json.dumps(latest, indent=2, sort_keys=True))
            return 1
        if state == "missing" and time.monotonic() >= missing_deadline:
            latest["error"] = "required_checks_missing"
            latest["missing_checks"] = names
            print(json.dumps(latest, indent=2, sort_keys=True))
            return 1
        if time.monotonic() >= deadline:
            latest["error"] = "required_checks_not_green"
            print(json.dumps(latest, indent=2, sort_keys=True))
            return 1
        time.sleep(min(15, max(1, int(deadline - time.monotonic()))))


if __name__ == "__main__":
    raise SystemExit(main())
