#!/usr/bin/env python3
"""Test exact-commit check aggregation without contacting GitHub."""

from __future__ import annotations

import importlib.util
from pathlib import Path


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


def main() -> int:
    base = [check_run("Static site"), *(check_run(name) for name in ANALYSES)]

    push = summary(*base)
    assert push["all_success"]
    assert push["states"]["CodeQL"]["source"] == "analyze_jobs_fallback"

    pull_request = summary(*base, check_run("CodeQL"))
    assert pull_request["all_success"]
    assert pull_request["states"]["CodeQL"]["source"] == "check_run"

    failed_aggregate = summary(
        *base,
        check_run("CodeQL", conclusion="failure"),
    )
    assert not failed_aggregate["all_success"]

    incomplete_push = summary(
        check_run("Static site"),
        check_run(ANALYSES[0]),
        check_run(ANALYSES[1], status="in_progress", conclusion=None),
        check_run(ANALYSES[2]),
    )
    assert not incomplete_push["all_success"]
    assert incomplete_push["states"]["CodeQL"]["status"] == "in_progress"

    print("release check fixture: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
