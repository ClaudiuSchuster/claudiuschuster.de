#!/usr/bin/env python3
"""Build a deterministic, cache-safe production bundle."""

from __future__ import annotations

import hashlib
import shutil
import struct
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "dist"
DIST_ASSETS = DIST / "assets"
HASH_LENGTH = 12
PREVIEW_MAX_BYTES = 5_000_000

PROJECT_PREVIEW_SOURCES = {
    "https://raw.githubusercontent.com/oss-singularity/proton-drive-linux/main/.github/social-preview.png": "project-preview-1",
    "https://raw.githubusercontent.com/oss-singularity/cinnamon-chatgpt-usage/main/.github/social-preview.png": "project-preview-2",
    "https://repository-images.githubusercontent.com/1343030536/d2d77c58-d01d-4e59-8258-5c954080e904": "project-preview-3",
    "https://oss-singularity.io/assets/social/oss-singularity-social-preview.png": "project-preview-4",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:HASH_LENGTH]


def write_asset(label: str, suffix: str, data: bytes) -> str:
    name = f"{label}.{digest(data)}.{suffix}"
    (DIST_ASSETS / name).write_bytes(data)
    return name


def source_bytes(relative: str) -> bytes:
    return (ROOT / relative).read_bytes()


def remote_bytes(url: str) -> bytes:
    request = Request(
        url,
        headers={
            "Accept": "image/png",
            "User-Agent": "claudiuschuster.de-build/1",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            data = response.read(PREVIEW_MAX_BYTES + 1)
    except OSError as error:
        raise RuntimeError(f"could not download project preview: {url}: {error}") from error
    if len(data) > PREVIEW_MAX_BYTES:
        raise ValueError(f"project preview is too large: {url}")
    if png_dimensions(data)[0] < 1 or png_dimensions(data)[1] < 1:
        raise ValueError(f"project preview has invalid dimensions: {url}")
    return data


def png_dimensions(data: bytes) -> tuple[int, int]:
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError("social preview is not a valid PNG")
    return struct.unpack(">II", data[16:24])


def require_replacement(text: str, old: str, new: str, source: str) -> str:
    if old not in text:
        raise ValueError(f"missing build token in {source}: {old}")
    return text.replace(old, new)


def verify_fingerprint(path: Path) -> None:
    parts = path.name.split(".")
    if len(parts) < 3:
        raise ValueError(f"asset is not fingerprinted: {path.name}")
    expected = parts[-2]
    actual = digest(path.read_bytes())
    if expected != actual:
        raise ValueError(f"fingerprint mismatch for {path.name}: {expected} != {actual}")


def main() -> int:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST_ASSETS.mkdir(parents=True)

    base_name = write_asset("base", "css", source_bytes("assets/base.css"))
    switch_name = write_asset("world-switch", "css", source_bytes("assets/world-switch.css"))
    atelier_name = write_asset("atelier", "css", source_bytes("assets/atelier.css"))
    prismatic_name = write_asset("prismatic", "css", source_bytes("assets/prismatic.css"))

    social_data = source_bytes("assets/social-preview.png")
    if png_dimensions(social_data) != (1200, 630):
        raise ValueError("social preview must be exactly 1200x630")
    social_name = write_asset("social-preview", "png", social_data)

    project_preview_names = {
        url: write_asset(label, "png", remote_bytes(url))
        for url, label in PROJECT_PREVIEW_SOURCES.items()
    }

    profile_data = source_bytes("assets/profile.png")
    if png_dimensions(profile_data) != (640, 640):
        raise ValueError("profile image must be exactly 640x640")
    profile_name = write_asset("profile", "png", profile_data)
    favicon_name = write_asset("favicon", "svg", source_bytes("assets/favicon.svg"))

    boot_text = source_bytes("assets/theme-boot.js").decode("utf-8")
    boot_text = require_replacement(
        boot_text,
        "assets/prismatic.css",
        f"assets/{prismatic_name}",
        "assets/theme-boot.js",
    )
    boot_name = write_asset("theme-boot", "js", boot_text.encode("utf-8"))

    switcher_text = source_bytes("assets/theme-switcher.js").decode("utf-8")
    switcher_text = require_replacement(
        switcher_text,
        "assets/atelier.css",
        f"assets/{atelier_name}",
        "assets/theme-switcher.js",
    )
    switcher_text = require_replacement(
        switcher_text,
        "assets/prismatic.css",
        f"assets/{prismatic_name}",
        "assets/theme-switcher.js",
    )
    switcher_name = write_asset("theme-switcher", "js", switcher_text.encode("utf-8"))

    edge_transition_text = source_bytes("assets/profile-edge-transition.js")
    edge_transition_name = write_asset("profile-edge-transition", "js", edge_transition_text)

    replacements = {
        "assets/base.css": f"assets/{base_name}",
        "assets/world-switch.css": f"assets/{switch_name}",
        "assets/atelier.css": f"assets/{atelier_name}",
        "assets/theme-boot.js": f"assets/{boot_name}",
        "assets/theme-switcher.js": f"assets/{switcher_name}",
        "assets/social-preview.png": f"assets/{social_name}",
        "assets/profile.png": f"assets/{profile_name}",
        "assets/favicon.svg": f"assets/{favicon_name}",
    }
    preview_replacements = {
        url: name for url, name in project_preview_names.items()
    }

    for page_name in ("de.html", "en.html", "legal.html"):
        page = (ROOT / page_name).read_text(encoding="utf-8")
        for old, new in replacements.items():
            page = require_replacement(page, old, new, page_name)
        if page_name in {"de.html", "en.html"}:
            page = require_replacement(
                page,
                "assets/profile-edge-transition.js",
                f"assets/{edge_transition_name}",
                page_name,
            )
        for old, new in preview_replacements.items():
            if old in page:
                page = page.replace(old, new)
        if page_name in {"de.html", "en.html"}:
            for source_url in preview_replacements:
                if source_url in page:
                    raise ValueError(f"remote project preview survived in {page_name}: {source_url}")
        if "?v=" in page:
            raise ValueError(f"query-string cachebuster survived in {page_name}")
        (DIST / page_name).write_text(page, encoding="utf-8")

    shutil.copy2(ROOT / ".htaccess", DIST / ".htaccess")

    for asset in sorted(DIST_ASSETS.iterdir()):
        verify_fingerprint(asset)

    expected_assets = {
        base_name,
        switch_name,
        atelier_name,
        prismatic_name,
        social_name,
        profile_name,
        favicon_name,
        boot_name,
        switcher_name,
        edge_transition_name,
        *project_preview_names.values(),
    }
    actual_assets = {path.name for path in DIST_ASSETS.iterdir()}
    if actual_assets != expected_assets:
        raise ValueError(f"unexpected production assets: {actual_assets ^ expected_assets}")

    print("Production bundle built with content fingerprints:")
    for asset in sorted(actual_assets):
        print(f"- assets/{asset}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
