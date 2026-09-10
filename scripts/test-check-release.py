#!/usr/bin/env python3
"""Test exact-commit check aggregation without contacting GitHub."""

from __future__ import annotations

import contextlib
import io
import importlib.util
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "check-release.py"
SPEC = importlib.util.spec_from_file_location("check_release", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable_to_load_check_release")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


ANALYSES = (
    "Analyze (actions)",
    "Analyze (javascript-typescript)",
    "Analyze (python)",
)


def check_run(name: str, *, status: str = "completed", conclusion: str | None = "success") -> dict:
    return {
        "name": name,
        "status": status,
        "conclusion": conclusion,
        "started_at": "2026-09-08T20:00:00Z",
        "completed_at": "2026-09-08T20:01:00Z" if status == "completed" else None,
    }


def summary(*runs: dict) -> dict:
    return MODULE.summarize({"check_runs": list(runs)})


def run_main(
    runs: list[dict], *, wait_seconds: int, missing_grace_seconds: int
) -> tuple[int, dict, int, int]:
    original_api_get = MODULE.api_get
    original_monotonic = MODULE.time.monotonic
    original_sleep = MODULE.time.sleep
    original_argv = sys.argv
    original_token = os.environ.get("GH_TOKEN")
    elapsed = [0]
    calls = [0]

    def fake_api_get(repository: str, sha: str, token: str) -> dict:
        calls[0] += 1
        return {"check_runs": runs}

    def fake_monotonic() -> int:
        return elapsed[0]

    def fake_sleep(seconds: int) -> None:
        elapsed[0] += seconds

    MODULE.api_get = fake_api_get
    MODULE.time.monotonic = fake_monotonic
    MODULE.time.sleep = fake_sleep
    os.environ["GH_TOKEN"] = "fixture-token"
    sys.argv = [
        "check-release.py",
        "--sha",
        "a" * 40,
        "--repository",
        "fixture/repository",
        "--wait-seconds",
        str(wait_seconds),
        "--missing-grace-seconds",
        str(missing_grace_seconds),
    ]
    output = io.StringIO()
    try:
        with contextlib.redirect_stdout(output):
            result = MODULE.main()
    finally:
        MODULE.api_get = original_api_get
        MODULE.time.monotonic = original_monotonic
        MODULE.time.sleep = original_sleep
        sys.argv = original_argv
        if original_token is None:
            os.environ.pop("GH_TOKEN", None)
        else:
            os.environ["GH_TOKEN"] = original_token
    return result, json.loads(output.getvalue()), elapsed[0], calls[0]


def main() -> int:
    base = [check_run("Verify"), *(check_run(name) for name in ANALYSES)]

    push = summary(*base)
    assert push["all_success"]
    assert push["states"]["CodeQL"]["source"] == "analyze_jobs_fallback"
    assert MODULE.check_state(push) == ("success", [])

    pull_request = summary(*base, check_run("CodeQL"))
    assert pull_request["all_success"]
    assert pull_request["states"]["CodeQL"]["source"] == "check_run"

    failed_aggregate = summary(
        *base,
        check_run("CodeQL", conclusion="failure"),
    )
    assert not failed_aggregate["all_success"]
    assert MODULE.check_state(failed_aggregate) == ("failed", ["CodeQL"])

    incomplete_push = summary(
        check_run("Verify"),
        check_run(ANALYSES[0]),
        check_run(ANALYSES[1], status="in_progress", conclusion=None),
        check_run(ANALYSES[2]),
    )
    assert not incomplete_push["all_success"]
    assert incomplete_push["states"]["CodeQL"]["status"] == "in_progress"
    assert MODULE.check_state(incomplete_push) == ("waiting", [])

    missing = summary()
    assert MODULE.check_state(missing) == (
        "missing",
        ["Verify", *ANALYSES, "CodeQL"],
    )

    missing_result, missing_payload, missing_elapsed, missing_calls = run_main(
        [], wait_seconds=600, missing_grace_seconds=90
    )
    assert missing_result == 1
    assert missing_payload["error"] == "required_checks_missing"
    assert missing_elapsed == 90
    assert missing_calls == 7

    failed_result, failed_payload, failed_elapsed, failed_calls = run_main(
        [*base, check_run("CodeQL", conclusion="failure")],
        wait_seconds=600,
        missing_grace_seconds=90,
    )
    assert failed_result == 1
    assert failed_payload["error"] == "required_checks_failed"
    assert failed_elapsed == 0
    assert failed_calls == 1

    print("release check fixture: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
