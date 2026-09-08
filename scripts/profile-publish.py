#!/usr/bin/env python3
"""Publish the checked, generated dist/ bundle through the fixed profile target."""

from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request


DOMAIN = "claudiuschuster.de"
ZONE_ID = "0fe141c79198e191adfa47d117817e3c"
TARGET = "claudiuschuster_de_target"
MAX_FILE = 4 * 1024 * 1024
MAX_TOTAL = 12 * 1024 * 1024
ALLOWED_SUFFIXES = {
    ".css",
    ".html",
    ".ico",
    ".js",
    ".json",
    ".png",
    ".svg",
    ".txt",
    ".webmanifest",
    ".webp",
    ".xml",
}
SSH_KEY_BEGIN = "-----BEGIN " + "OPENSSH PRIVATE KEY-----"
SSH_KEY_END = "-----END " + "OPENSSH PRIVATE KEY-----"
VERIFY_ATTEMPTS = 5
VERIFY_RETRY_DELAY_SECONDS = 2


class ReleaseError(Exception):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ReleaseError(code)


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("ascii")


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def hex_value(value: object, length: int, code: str) -> str:
    require(
        type(value) is str
        and len(value) == length
        and all(char in "0123456789abcdef" for char in value),
        code,
    )
    return value


def candidate_inventory(files: dict[str, bytes]) -> dict:
    entries = [
        {"path": name, "bytes": len(raw), "sha256": digest(raw)}
        for name, raw in sorted(files.items())
    ]
    return {
        "manifest_sha256": digest(canonical(entries)),
        "files": len(entries),
        "bytes": sum(item["bytes"] for item in entries),
        "entries": entries,
    }


def load_dist(dist: Path) -> tuple[dict[str, bytes], dict]:
    require(dist.is_dir() and not dist.is_symlink(), "missing_dist")
    files: dict[str, bytes] = {}
    total = 0
    for base, directories, names in os.walk(dist, followlinks=False):
        directories.sort()
        names.sort()
        for name in names:
            path = Path(base) / name
            require(not path.is_symlink(), "unsafe_dist")
            relative = path.relative_to(dist).as_posix()
            parts = relative.split("/")
            require(
                all(part not in {"", ".", ".."} for part in parts)
                and not relative.startswith(".well-known/"),
                "unsafe_dist",
            )
            if relative != ".htaccess":
                require(
                    not any(part.startswith(".") for part in parts)
                    and Path(name).suffix.lower() in ALLOWED_SUFFIXES,
                    "non_static_path",
                )
            raw = path.read_bytes()
            require(len(raw) <= MAX_FILE, "size_limit")
            total += len(raw)
            require(total <= MAX_TOTAL, "candidate_limit")
            files[relative] = raw
    require("index.html" in files and ".htaccess" in files, "invalid_dist")
    return files, candidate_inventory(files)


def parse_headers(raw: bytes) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in raw.decode("iso-8859-1", "replace").splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    return headers


def curl_get(url: str, origin_ip: str | None = None) -> tuple[int, dict[str, str], bytes]:
    with tempfile.TemporaryDirectory(prefix="profile-http-") as temporary:
        root = Path(temporary)
        headers_path = root / "headers"
        body_path = root / "body"
        command = [
            "curl",
            "--noproxy",
            "*",
            "--silent",
            "--show-error",
            "--connect-timeout",
            "15",
            "--max-time",
            "30",
            "--output",
            str(body_path),
            "--dump-header",
            str(headers_path),
            "--write-out",
            "%{http_code}",
        ]
        if origin_ip is not None:
            command += ["--resolve", f"{DOMAIN}:443:{origin_ip}"]
        command.append(url)
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        )
        require(result.returncode == 0 and result.stdout.strip().isdigit(), "http_failed")
        status = int(result.stdout.strip())
        return status, parse_headers(headers_path.read_bytes()), body_path.read_bytes()


def fetch_expected(
    url: str,
    expected: bytes,
    origin_ip: str | None,
    status_code: str,
    body_code: str,
) -> tuple[int, dict[str, str], bytes, str]:
    last_status = 0
    for attempt in range(VERIFY_ATTEMPTS):
        probe_url = url + "&probe=" + str(attempt)
        status, headers, body = curl_get(probe_url, origin_ip)
        last_status = status
        if status == 200 and body == expected:
            return status, headers, body, probe_url
        if attempt + 1 < VERIFY_ATTEMPTS:
            time.sleep(VERIFY_RETRY_DELAY_SECONDS)
    if last_status == 200:
        raise ReleaseError(body_code)
    raise ReleaseError(f"{status_code}_{last_status}")


def cache_transition(first_status: str, second_status: str) -> str:
    """Accept a fresh or already-warm unique key, but require a cached second hit."""
    require(first_status in {"MISS", "HIT"} and second_status == "HIT",
            "http_cache_mismatch")
    return f"{first_status}->{second_status}"


def verify_root_and_asset(
    files: dict[str, bytes],
    commit: str,
    origin_ip: str,
    require_cache: bool,
) -> dict:
    nonce = commit[:12] + "-" + str(time.time_ns())
    root_url = f"https://{DOMAIN}/?release={nonce}"
    status, headers, body, _ = fetch_expected(
        root_url, files["index.html"], None, "edge_root_status_mismatch", "edge_root_bytes_mismatch"
    )
    require("no-store" in headers.get("cache-control", "").lower(), "http_cache_mismatch")

    asset_name = next(
        (name for name in sorted(files) if name.endswith(".css")),
        next(name for name in sorted(files) if name.endswith(".js")),
    )
    asset_url = f"https://{DOMAIN}/{asset_name}?release={nonce}"
    asset_status, asset_headers, asset_body, asset_url = fetch_expected(
        asset_url, files[asset_name], None,
        "edge_asset_status_mismatch", "edge_asset_bytes_mismatch"
    )
    cache_status = asset_headers.get("cf-cache-status", "").upper()
    require("immutable" in asset_headers.get("cache-control", "").lower(), "http_cache_mismatch")
    cache_transition_value = None
    if require_cache:
        second_status, second_headers, second_body = curl_get(asset_url)
        require(second_status == 200, "edge_asset_cache_status_mismatch")
        require(second_body == files[asset_name], "edge_asset_cache_bytes_mismatch")
        cache_transition_value = cache_transition(
            cache_status, second_headers.get("cf-cache-status", "").upper()
        )

    www_status, www_headers, _ = curl_get(f"https://www.{DOMAIN}/?release={nonce}")
    require(www_status == 301, "redirect_mismatch")
    require(www_headers.get("location", "").startswith(f"https://{DOMAIN}/"), "redirect_mismatch")

    origin_status, _, origin_body, _ = fetch_expected(
        root_url, files["index.html"], origin_ip,
        "origin_root_status_mismatch", "origin_root_bytes_mismatch"
    )
    origin_asset_status, _, origin_asset_body, _ = fetch_expected(
        asset_url, files[asset_name], origin_ip,
        "origin_asset_status_mismatch", "origin_asset_bytes_mismatch"
    )
    return {
        "root": {"status": status, "bytes": len(body)},
        "asset": {"path": asset_name, "status": asset_status, "bytes": len(asset_body),
                  "cache": cache_status, "cache_transition": cache_transition_value},
        "origin": {"root_status": origin_status, "asset_status": origin_asset_status},
        "redirect": {"www_status": www_status},
    }


def capture_baseline(status: dict, origin_ip: str) -> dict:
    paths = status.get("paths", [])
    require(type(paths) is list and "index.html" in paths, "baseline_unavailable")
    asset_name = next((name for name in paths if name.endswith(".css")), None)
    if asset_name is None:
        asset_name = next((name for name in paths if name.endswith(".js")), None)
    require(asset_name is not None, "baseline_unavailable")
    root_status, _, root = curl_get(f"https://{DOMAIN}/?release=baseline-{time.time_ns()}")
    asset_status, _, asset = curl_get(
        f"https://{DOMAIN}/{asset_name}?release=baseline-{time.time_ns()}"
    )
    origin_status, _, origin_root = curl_get(
        f"https://{DOMAIN}/?release=baseline-origin-{time.time_ns()}", origin_ip
    )
    origin_asset_status, _, origin_asset = curl_get(
        f"https://{DOMAIN}/{asset_name}?release=baseline-origin-{time.time_ns()}",
        origin_ip,
    )
    require(
        root_status == 200
        and asset_status == 200
        and origin_status == 200
        and origin_asset_status == 200,
        "baseline_unavailable",
    )
    require(root == origin_root and asset == origin_asset, "baseline_unavailable")
    return {
        "asset_path": asset_name,
        "root": root,
        "asset": asset,
        "origin_root": origin_root,
        "origin_asset": origin_asset,
    }


def verify_baseline(baseline: dict, origin_ip: str) -> None:
    nonce = str(time.time_ns())
    root_status, _, root = curl_get(f"https://{DOMAIN}/?release=rollback-{nonce}")
    asset_status, _, asset = curl_get(
        f"https://{DOMAIN}/{baseline['asset_path']}?release=rollback-{nonce}"
    )
    origin_status, _, origin_root = curl_get(
        f"https://{DOMAIN}/?release=rollback-origin-{nonce}", origin_ip
    )
    origin_asset_status, _, origin_asset = curl_get(
        f"https://{DOMAIN}/{baseline['asset_path']}?release=rollback-origin-{nonce}",
        origin_ip,
    )
    require(
        root_status == 200
        and asset_status == 200
        and origin_status == 200
        and origin_asset_status == 200
        and root == baseline["root"]
        and asset == baseline["asset"]
        and origin_root == baseline["origin_root"]
        and origin_asset == baseline["origin_asset"],
        "rollback_http_mismatch",
    )


class Remote:
    def __init__(self, environ: dict[str, str], folder: Path):
        self.folder = folder
        origin = str(ipaddress.ip_address(environ["PROFILE_ORIGIN_IP"]))
        require(ipaddress.ip_address(origin).is_global, "invalid_ssh_binding")
        user = environ.get("PROFILE_SSH_USER", "")
        port = environ.get("PROFILE_SSH_PORT", "")
        require(re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", user) is not None, "invalid_ssh_binding")
        require(re.fullmatch(r"[1-9][0-9]{0,4}", port) is not None and 1 <= int(port) <= 65535,
                "invalid_ssh_binding")
        host_key = environ.get("PROFILE_SSH_HOST_KEY", "")
        require(re.fullmatch(r"ssh-ed25519 [A-Za-z0-9+/]+={0,2}", host_key) is not None,
                "invalid_ssh_binding")
        key = environ.get("PROFILE_SSH_KEY", "")
        require(
            type(key) is str
            and 128 < len(key) <= 8192
            and key.startswith(SSH_KEY_BEGIN)
            and key.rstrip().endswith(SSH_KEY_END),
            "invalid_ssh_binding",
        )
        identity = folder / "identity"
        known_hosts = folder / "known_hosts"
        identity.write_text(key.rstrip("\r\n") + "\n", encoding="utf-8")
        known_hosts.write_text("profile-origin " + host_key + "\n", encoding="ascii")
        os.chmod(identity, 0o600)
        os.chmod(known_hosts, 0o600)
        options = {
            "IdentitiesOnly": "yes",
            "IdentityAgent": "none",
            "ControlMaster": "no",
            "ControlPath": "none",
            "StrictHostKeyChecking": "yes",
            "UserKnownHostsFile": str(known_hosts),
            "GlobalKnownHostsFile": "/dev/null",
            "HostKeyAlias": "profile-origin",
            "HostKeyAlgorithms": "ssh-ed25519",
            "UpdateHostKeys": "no",
            "BatchMode": "yes",
            "PasswordAuthentication": "no",
            "KbdInteractiveAuthentication": "no",
            "ClearAllForwardings": "yes",
            "RequestTTY": "no",
            "ConnectTimeout": "15",
            "ServerAliveInterval": "10",
            "ServerAliveCountMax": "2",
            "LogLevel": "ERROR",
        }
        self.command = [
            "ssh",
            "-F",
            "/dev/null",
            "-T",
            "-i",
            str(identity),
            "-p",
            port,
            "-l",
            user,
        ]
        for name, value in options.items():
            self.command += ["-o", name + "=" + value]
        self.command += [origin, "claudiuschuster_de_release_v1"]
        self.runtime = environ.get("PROFILE_RUNTIME_SHA256", "")
        if self.runtime:
            hex_value(self.runtime, 64, "invalid_runtime_binding")

    def call(self, request: dict) -> dict:
        raw = canonical(request)
        require(len(raw) <= 16 * 1024 * 1024, "request_limit")
        try:
            result = subprocess.run(
                self.command,
                input=raw,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=90,
                check=False,
                env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
            )
        except (OSError, subprocess.TimeoutExpired):
            raise ReleaseError("remote_outcome_unconfirmed") from None
        if len(result.stdout) > 64 * 1024:
            raise ReleaseError("remote_response_invalid")
        try:
            value = json.loads(result.stdout.decode("utf-8"))
        except (UnicodeError, ValueError, RecursionError):
            raise ReleaseError("remote_outcome_unconfirmed") from None
        if result.returncode != 0:
            code = value.get("error") if isinstance(value, dict) else None
            raise ReleaseError(code if isinstance(code, str) else "remote_outcome_unconfirmed")
        require(
            type(value) is dict
            and value.get("schema") == 1
            and value.get("target") == TARGET,
            "remote_response_invalid",
        )
        if self.runtime:
            require(value.get("runtime_sha256") == self.runtime, "runtime_mismatch")
        return value


def purge_cloudflare(token: str) -> None:
    require(token, "missing_cloudflare_credential")
    request = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/purge_cache",
        data=b'{"purge_everything":true}',
        method="POST",
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "User-Agent": "claudiuschuster-profile-release/1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            value = json.load(response)
    except (OSError, urllib.error.HTTPError):
        raise ReleaseError("cloudflare_purge_failed") from None
    require(
        value.get("success") is True
        and isinstance(value.get("result"), dict)
        and value["result"].get("id") == ZONE_ID,
        "cloudflare_purge_failed",
    )


def run(mode: str, commit: str, root: Path, environ: dict[str, str]) -> dict:
    require(mode in {"plan", "publish"}, "invalid_arguments")
    commit = hex_value(commit, 40, "invalid_commit")
    files, candidate = load_dist(root / "dist")
    origin_ip = str(ipaddress.ip_address(environ.get("PROFILE_ORIGIN_IP", "")))
    folder = Path(tempfile.mkdtemp(prefix="profile-release-"))
    try:
        remote = Remote(environ, folder)
        baseline = remote.call({"schema": 1, "operation": "status"})
        require(baseline.get("phase") in {"clean", "published", "rolled_back"}, "unfinished_attempt")
        require(baseline.get("manifest_sha256"), "baseline_unavailable")
        baseline_public = capture_baseline(baseline, origin_ip)
        result = {
            "schema": 1,
            "target": TARGET,
            "mode": mode,
            "commit": commit,
            "candidate_manifest_sha256": candidate["manifest_sha256"],
            "candidate_files": candidate["files"],
            "candidate_bytes": candidate["bytes"],
            "baseline_manifest_sha256": baseline["manifest_sha256"],
            "baseline_files": baseline.get("files"),
            "source_rebuilt": True,
            "publication_verified": False,
        }
        if mode == "plan":
            result["baseline_http_verified"] = True
            return result

        identity = digest(canonical({"commit": commit, "manifest": candidate["manifest_sha256"],
                                     "nonce": time.time_ns()}))[:32]
        published = remote.call(
            {
                "schema": 1,
                "operation": "publish",
                "identity": identity,
                "commit": commit,
                "manifest_sha256": candidate["manifest_sha256"],
                "expected_manifest_sha256": baseline["manifest_sha256"],
                "files": {name: base64.b64encode(raw).decode("ascii") for name, raw in files.items()},
            }
        )
        try:
            purge_cloudflare(environ.get("CF_RELEASE_TOKEN", ""))
            live = verify_root_and_asset(files, commit, origin_ip, require_cache=True)
        except Exception as error:
            verification_error = (
                str(error)
                if isinstance(error, ReleaseError) and str(error)
                else "publication_verification_failed"
            )
            try:
                remote.call({"schema": 1, "operation": "rollback", "identity": identity})
                purge_cloudflare(environ.get("CF_RELEASE_TOKEN", ""))
                after_rollback = remote.call({"schema": 1, "operation": "status"})
                require(after_rollback.get("manifest_sha256") == baseline["manifest_sha256"],
                        "rollback_unconfirmed")
                verify_baseline(baseline_public, origin_ip)
            except Exception:
                raise ReleaseError("publication_requires_reconciliation") from None
            raise ReleaseError("publication_rolled_back_" + verification_error) from None
        result.update(
            {
                "deployment_identity": identity,
                "remote_phase": published.get("phase"),
                "live": live,
                "rollback_retained": published.get("rollback_available") is True,
                "publication_verified": True,
            }
        )
        require(result["rollback_retained"], "rollback_unconfirmed")
        return result
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def cli(argv: list[str]) -> int:
    try:
        require(
            len(argv) == 4
            and argv[0] == "--mode"
            and argv[2] == "--commit",
            "invalid_arguments",
        )
    except ReleaseError:
        print(json.dumps({"error": "invalid_arguments", "publication_verified": False}))
        return 2
    try:
        result = run(argv[1], argv[3], Path.cwd(), dict(os.environ))
    except ReleaseError as error:
        result = {
            "schema": 1,
            "target": TARGET,
            "error": str(error),
            "publication_verified": False,
        }
    except (OSError, ValueError, urllib.error.URLError):
        result = {
            "schema": 1,
            "target": TARGET,
            "error": "publication_failed",
            "publication_verified": False,
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if "error" in result else 0


if __name__ == "__main__":
    raise SystemExit(cli(__import__("sys").argv[1:]))
