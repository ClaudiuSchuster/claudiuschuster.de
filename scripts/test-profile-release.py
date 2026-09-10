#!/usr/bin/env python3
"""Exercise the fixed profile publisher entirely inside temporary directories."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
REMOTE = ROOT / "scripts/profile-release-remote.py"
COMMAND = "claudiuschuster_de_release_v1"


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def inventory(files: dict[str, bytes]) -> str:
    entries = [
        {"path": name, "bytes": len(raw), "sha256": digest(raw)}
        for name, raw in sorted(files.items())
    ]
    return digest(canonical(entries))


def run(args: list[str], *, env: dict[str, str] | None = None, data: bytes = b"") -> dict:
    result = subprocess.run(
        [sys.executable, "-I", "-S", str(REMOTE), *args],
        input=data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env=env,
        text=False,
    )
    if not result.stdout:
        raise AssertionError(result.stderr.decode("utf-8", "replace"))
    value = json.loads(result.stdout)
    return value


def request(config: Path, value: dict) -> dict:
    environment = {"PATH": "/usr/bin:/bin", "SSH_ORIGINAL_COMMAND": COMMAND}
    return run(
        ["--config", str(config)],
        env=environment,
        data=canonical(value),
    )


def encoded(files: dict[str, bytes]) -> dict[str, str]:
    return {name: base64.b64encode(raw).decode("ascii") for name, raw in files.items()}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="profile-release-test-") as temporary:
        folder = Path(temporary)
        root = folder / "live"
        control = folder / "control"
        root.mkdir()
        (root / ".well-known" / "ssl-manager").mkdir(parents=True)
        (root / ".well-known" / "ssl-manager" / "installed.txt").write_text(
            "provider-state\n", encoding="utf-8"
        )
        (root / "assets").mkdir()
        (root / "assets" / "style.css").write_text("body{}\n", encoding="utf-8")
        (root / "index.html").write_text("old\n", encoding="utf-8")
        (root / ".htaccess").write_text("DirectoryIndex index.html\n", encoding="utf-8")
        public_directory_mode = stat.S_IMODE(root.stat().st_mode)
        public_file_mode = stat.S_IMODE((root / ".htaccess").stat().st_mode)
        legacy = folder / "live.__previous_legacy"
        legacy.mkdir()
        (legacy / "leftover.txt").write_text("untouched\n", encoding="utf-8")
        htaccess_sha = digest((root / ".htaccess").read_bytes())
        config = control / "config.json"

        boot = run(
            [
                "--bootstrap",
                "--config",
                str(config),
                "--root",
                str(root),
                "--control",
                str(control),
                "--preserve",
                ".well-known",
                "--htaccess-sha256",
                htaccess_sha,
            ],
            env={"PATH": "/usr/bin:/bin"},
        )
        assert boot["phase"] == "clean"
        baseline = request(config, {"schema": 1, "operation": "status"})
        assert baseline["phase"] == "clean"

        first = {
            ".htaccess": b"DirectoryIndex index.html\n",
            "assets/style.css": b"body{color:red}\n",
            "index.html": b"first\n",
            "legal.html": b"legal\n",
            "robots.txt": b"User-agent: *\nAllow: /\n",
            "site.webmanifest": b'{"name":"Claudiu Schuster"}\n',
            "sitemap.xml": b"<urlset></urlset>\n",
        }
        first_manifest = inventory(first)
        first_result = request(
            config,
            {
                "schema": 1,
                "operation": "publish",
                "identity": "1" * 32,
                "commit": "2" * 40,
                "manifest_sha256": first_manifest,
                "expected_manifest_sha256": baseline["manifest_sha256"],
                "files": encoded(first),
            },
        )
        assert first_result["phase"] == "published"
        assert (root / "index.html").read_bytes() == b"first\n"
        assert stat.S_IMODE(root.stat().st_mode) == public_directory_mode
        assert stat.S_IMODE((root / "index.html").stat().st_mode) == public_file_mode
        assert (root / ".well-known" / "ssl-manager" / "installed.txt").exists()
        assert (legacy / "leftover.txt").read_text(encoding="utf-8") == "untouched\n"

        second = dict(first)
        second["index.html"] = b"second\n"
        second_manifest = inventory(second)
        second_result = request(
            config,
            {
                "schema": 1,
                "operation": "publish",
                "identity": "3" * 32,
                "commit": "4" * 40,
                "manifest_sha256": second_manifest,
                "expected_manifest_sha256": first_manifest,
                "files": encoded(second),
            },
        )
        assert second_result["phase"] == "published"
        assert (root / "index.html").read_bytes() == b"second\n"
        rollback = request(
            config,
            {"schema": 1, "operation": "rollback", "identity": "3" * 32},
        )
        assert rollback["phase"] == "rolled_back"
        assert (root / "index.html").read_bytes() == b"first\n"
        assert request(config, {"schema": 1, "operation": "status"})["rollback_available"]

        rejected = request(
            config,
            {
                "schema": 1,
                "operation": "publish",
                "identity": "5" * 32,
                "commit": "6" * 40,
                "manifest_sha256": first_manifest,
                "expected_manifest_sha256": first_manifest,
                "files": encoded({**first, "../escape.html": b"no"}),
            },
        )
        assert rejected["error"] == "invalid_request"
    print("profile release fixture: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
