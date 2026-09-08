#!/usr/bin/env python3
"""Exercise publication HTTP convergence checks without network access."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/profile-publish.py"
SPEC = importlib.util.spec_from_file_location("profile_publish", SOURCE)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def main() -> int:
    calls = []
    responses = [
        (503, {"cache-control": "no-store"}, b"temporary"),
        (200, {"cache-control": "no-store"}, b"expected"),
    ]

    def fake_curl(url, origin_ip=None):
        calls.append((url, origin_ip))
        return responses.pop(0)

    MODULE.curl_get = fake_curl
    MODULE.time.sleep = lambda _seconds: None
    status, headers, body, url = MODULE.fetch_expected(
        "https://claudiuschuster.de/?release=test",
        b"expected",
        None,
        "edge_root_status_mismatch",
        "edge_root_bytes_mismatch",
    )
    assert status == 200 and headers["cache-control"] == "no-store" and body == b"expected"
    assert url.endswith("&probe=1") and len(calls) == 2

    responses[:] = [(200, {}, b"wrong")] * MODULE.VERIFY_ATTEMPTS
    try:
        MODULE.fetch_expected(
            "https://claudiuschuster.de/?release=test",
            b"expected",
            None,
            "edge_root_status_mismatch",
            "edge_root_bytes_mismatch",
        )
    except MODULE.ReleaseError as error:
        assert str(error) == "edge_root_bytes_mismatch"
    else:
        raise AssertionError("persistent byte mismatch was accepted")

    print("profile publish fixture: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
