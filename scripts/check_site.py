#!/usr/bin/env python3
"""Small dependency-free structural checks for the static site and concept pages."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
HTML_FILES = sorted(ROOT.glob("*.html")) + sorted(ROOT.glob("concepts/**/*.html"))
CSS_FILES = sorted(ROOT.glob("assets/*.css")) + sorted(ROOT.glob("concepts/**/*.css"))
SOCIAL_PREVIEW = ROOT / "assets/social-preview.png"


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict[str, str]]] = []
        self.title_depth = 0
        self.title_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        self.tags.append((tag, values))
        if tag == "title":
            self.title_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "title" and self.title_depth:
            self.title_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.title_depth:
            self.title_text.append(data)


def check_html(path: Path) -> list[str]:
    parser = PageParser()
    parser.feed(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    tags = parser.tags

    html = next((attrs for tag, attrs in tags if tag == "html"), {})
    if html.get("lang") not in {"de", "en"}:
        errors.append("html[lang] must be de or en")
    if not "".join(parser.title_text).strip():
        errors.append("missing non-empty title")
    for required in ("main", "h1", "nav"):
        if not any(tag == required for tag, _ in tags):
            errors.append(f"missing <{required}>")
    if not any(tag == "meta" and attrs.get("name") == "viewport" for tag, attrs in tags):
        errors.append("missing viewport meta")
    if not any(tag == "meta" and attrs.get("name") == "description" and attrs.get("content") for tag, attrs in tags):
        errors.append("missing meta description")

    ids = {attrs.get("id") for _, attrs in tags if attrs.get("id")}
    for tag, attrs in tags:
        if tag == "svg" and attrs.get("aria-hidden") != "true" and not attrs.get("aria-label"):
            errors.append("decorative SVG needs aria-hidden or an aria-label")
        if tag == "a":
            href = attrs.get("href", "")
            if href.startswith("#") and href[1:] not in ids:
                errors.append(f"broken fragment link: {href}")
            parsed = urlparse(href)
            if href and not parsed.scheme and not href.startswith(("#", "mailto:", "tel:")):
                target = (path.parent / parsed.path).resolve()
                if parsed.path.endswith("/"):
                    target /= "index.html"
                if not target.exists():
                    errors.append(f"missing local link target: {href}")
        if tag == "link" and attrs.get("rel") == "stylesheet":
            href = attrs.get("href", "")
            parsed = urlparse(href)
            if parsed.scheme:
                errors.append(f"remote stylesheet is not allowed: {href}")
            elif not (path.parent / parsed.path).resolve().exists():
                errors.append(f"missing stylesheet: {href}")
        if tag == "script" and attrs.get("src"):
            src = attrs["src"]
            parsed = urlparse(src)
            if parsed.scheme:
                errors.append(f"remote script is not allowed: {src}")
            elif not (path.parent / parsed.path).resolve().exists():
                errors.append(f"missing script: {src}")

    return errors


def check_css(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    if text.count("{") != text.count("}"):
        errors.append("unbalanced CSS braces")
    if "outline: none" in text or "outline:none" in text:
        errors.append("focus outlines must not be removed")
    if "!important" in text:
        errors.append("avoid !important in the concept styles")
    return errors


def check_social_metadata(path: Path) -> list[str]:
    parser = PageParser()
    parser.feed(path.read_text(encoding="utf-8"))
    meta = {
        attrs.get("property") or attrs.get("name"): attrs.get("content", "")
        for tag, attrs in parser.tags
        if tag == "meta"
    }
    errors: list[str] = []
    expected = {
        "og:type": "website",
        "og:image": "https://claudiuschuster.de/assets/social-preview.png",
        "og:image:secure_url": "https://claudiuschuster.de/assets/social-preview.png",
        "og:image:type": "image/png",
        "og:image:width": "1200",
        "og:image:height": "630",
        "twitter:card": "summary_large_image",
        "twitter:image": "https://claudiuschuster.de/assets/social-preview.png",
    }
    for key, value in expected.items():
        if meta.get(key) != value:
            errors.append(f"{key} must be {value}")
    for key in ("og:title", "og:description", "og:image:alt", "twitter:title", "twitter:description", "twitter:image:alt"):
        if not meta.get(key):
            errors.append(f"missing {key}")
    return errors


def check_social_preview() -> list[str]:
    data = SOCIAL_PREVIEW.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return ["assets/social-preview.png is not a valid PNG"]
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    if (width, height) != (1200, 630):
        return [f"assets/social-preview.png must be 1200x630, found {width}x{height}"]
    return []


def main() -> int:
    failures: list[str] = []
    if len(HTML_FILES) != 6:
        failures.append(f"expected 6 HTML files, found {len(HTML_FILES)}")
    for path in HTML_FILES:
        failures.extend(f"{path.relative_to(ROOT)}: {error}" for error in check_html(path))
    for path in (ROOT / "index.html", ROOT / "en.html"):
        failures.extend(f"{path.relative_to(ROOT)}: {error}" for error in check_social_metadata(path))
    for path in CSS_FILES:
        failures.extend(f"{path.relative_to(ROOT)}: {error}" for error in check_css(path))
    failures.extend(check_social_preview())

    if failures:
        print("Static site checks failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(f"Static site checks passed: {len(HTML_FILES)} HTML and {len(CSS_FILES)} CSS files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
