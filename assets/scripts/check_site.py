#!/usr/bin/env python3
"""Small dependency-free structural checks for the static site."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[2]
HTML_FILES = sorted(ROOT.glob("*.html"))
CSS_FILES = sorted(ROOT.glob("assets/*.css"))
SOCIAL_PREVIEW = ROOT / "assets/social-preview.png"
FAVICON = ROOT / "assets/favicon.svg"
FAVICON_ICO = ROOT / "favicon.ico"
HTACCESS = ROOT / ".htaccess"
ROBOTS = ROOT / "robots.txt"
SITEMAP = ROOT / "sitemap.xml"
TELEGRAM_URL = "https://t.me/ClaudiuSchuster"
SITEMAP_NAMESPACE = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
SITEMAP_URLS = {
    "https://claudiuschuster.de/",
    "https://claudiuschuster.de/legal.html",
}


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
    favicons = [
        attrs for tag, attrs in tags if tag == "link" and attrs.get("rel") == "icon"
    ]
    if not favicons:
        errors.append("missing favicon link")
    else:
        if not any(attrs.get("href") == "favicon.ico" for attrs in favicons):
            errors.append("missing stable root favicon fallback link")
        if not any(
            attrs.get("href") == "assets/favicon.svg"
            and attrs.get("type") == "image/svg+xml"
            for attrs in favicons
        ):
            errors.append("missing SVG favicon link")
        for favicon in favicons:
            href = favicon.get("href", "")
            if href and not (path.parent / href).resolve().is_file():
                errors.append(f"missing favicon asset: {href}")
        ico_favicon = next(
            (attrs for attrs in favicons if attrs.get("href") == "favicon.ico"),
            {},
        )
        if ico_favicon and ico_favicon.get("sizes") != "any":
            errors.append("root favicon fallback must declare sizes=any")

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
        errors.append("avoid !important in the theme styles")
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


def check_contact_links(path: Path) -> list[str]:
    parser = PageParser()
    parser.feed(path.read_text(encoding="utf-8"))
    telegram_links = [
        attrs
        for tag, attrs in parser.tags
        if tag == "a" and attrs.get("href") == TELEGRAM_URL
    ]
    telegram_icons = [
        attrs
        for tag, attrs in parser.tags
        if tag == "svg" and attrs.get("class") == "telegram-icon"
    ]
    errors: list[str] = []
    if len(telegram_links) != 1:
        errors.append(f"expected one Telegram contact link to {TELEGRAM_URL}")
    if len(telegram_icons) != 1:
        errors.append("expected one Telegram icon")
    elif telegram_icons[0].get("aria-hidden") != "true":
        errors.append("Telegram icon must be decorative")
    elif telegram_icons[0].get("viewbox") != "0 0 16 16":
        errors.append("Telegram icon must use the verified 16x16 viewBox")
    return errors


def check_bilingual_home(path: Path) -> list[str]:
    parser = PageParser()
    parser.feed(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    html = next((attrs for tag, attrs in parser.tags if tag == "html"), {})
    if "data-bilingual" not in html:
        errors.append("homepage must declare data-bilingual")

    language_counts = {"lang-de": 0, "lang-en": 0}
    for _, attrs in parser.tags:
        classes = attrs.get("class", "").split()
        for language_class in language_counts:
            if language_class in classes:
                language_counts[language_class] += 1
    if not language_counts["lang-de"]:
        errors.append("homepage must contain inline German content")
    if language_counts["lang-de"] != language_counts["lang-en"]:
        errors.append(
            "inline language variants must stay paired: "
            f"de={language_counts['lang-de']} en={language_counts['lang-en']}"
        )

    toggles = [
        attrs
        for tag, attrs in parser.tags
        if tag == "button" and "data-language-toggle" in attrs
    ]
    if len(toggles) != 1:
        errors.append(f"expected one in-document language toggle, found {len(toggles)}")

    canonical_urls = [
        attrs.get("href", "")
        for tag, attrs in parser.tags
        if tag == "link" and attrs.get("rel") == "canonical"
    ]
    if canonical_urls != ["https://claudiuschuster.de/"]:
        errors.append("homepage canonical must be the single root URL")
    if any(
        tag == "link" and attrs.get("rel") == "alternate" and attrs.get("hreflang")
        for tag, attrs in parser.tags
    ):
        errors.append("single-URL language switching must not advertise alternate URLs")
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


def check_favicon() -> list[str]:
    text = FAVICON.read_text(encoding="utf-8")
    errors: list[str] = []
    if '<svg xmlns="http://www.w3.org/2000/svg"' not in text:
        errors.append("assets/favicon.svg is not a standalone SVG")
    if 'viewBox="0 0 64 64"' not in text:
        errors.append("assets/favicon.svg must use a square 64x64 viewBox")
    if "<title" not in text:
        errors.append("assets/favicon.svg must have an accessible title")
    if not FAVICON_ICO.is_file():
        errors.append("missing stable root favicon.ico")
    else:
        ico = FAVICON_ICO.read_bytes()
        if len(ico) < 6 or ico[:4] != b"\x00\x00\x01\x00":
            errors.append("favicon.ico is not a valid ICO file")
        else:
            count = int.from_bytes(ico[4:6], "little")
            directory_end = 6 + count * 16
            if count < 4 or len(ico) < directory_end:
                errors.append("favicon.ico must contain at least four complete images")
            else:
                sizes = {
                    (ico[offset] or 256, ico[offset + 1] or 256)
                    for offset in range(6, directory_end, 16)
                }
                required_sizes = {(16, 16), (32, 32), (48, 48), (64, 64)}
                if not required_sizes.issubset(sizes):
                    errors.append(
                        "favicon.ico must contain 16x16, 32x32, 48x48 and 64x64 images"
                    )
    htaccess = HTACCESS.read_text(encoding="utf-8")
    if "(?:css|js|png|svg)" not in htaccess:
        errors.append("fingerprinted SVG assets must receive immutable caching")
    if "AddType image/svg+xml .svg" not in htaccess:
        errors.append(".htaccess must declare the SVG MIME type")
    if "AddType image/x-icon .ico" not in htaccess:
        errors.append(".htaccess must declare the ICO MIME type")
    if 'FilesMatch "^favicon\\.ico$"' not in htaccess:
        errors.append(".htaccess must cache the stable root favicon")
    return errors


def check_htaccess() -> list[str]:
    text = HTACCESS.read_text(encoding="utf-8")
    errors: list[str] = []
    required = (
        "DirectoryIndex index.html",
        "RewriteCond %{THE_REQUEST} \\s/+index\\.html(?:[?\\s]) [NC]",
        "RewriteRule ^index\\.html$ / [R=301,L]",
        "RewriteCond %{THE_REQUEST} \\s/+de\\.html(?:[?\\s]) [NC]",
        "RewriteRule ^de\\.html$ / [R=301,L]",
        "RewriteCond %{THE_REQUEST} \\s/+en\\.html(?:[?\\s]) [NC]",
        "RewriteRule ^en\\.html$ /?lang=en [R=301,L,NE]",
    )
    for directive in required:
        if directive not in text:
            errors.append(f".htaccess is missing: {directive}")
    return errors


def check_robots() -> list[str]:
    if not ROBOTS.is_file():
        return ["missing robots.txt"]
    lines = {line.strip() for line in ROBOTS.read_text(encoding="utf-8").splitlines()}
    errors: list[str] = []
    for required in (
        "User-agent: *",
        "Allow: /",
        "Sitemap: https://claudiuschuster.de/sitemap.xml",
    ):
        if required not in lines:
            errors.append(f"robots.txt is missing: {required}")
    return errors


def check_sitemap() -> list[str]:
    if not SITEMAP.is_file():
        return ["missing sitemap.xml"]
    try:
        root = ElementTree.fromstring(SITEMAP.read_text(encoding="utf-8"))
    except (OSError, ElementTree.ParseError) as error:
        return [f"sitemap.xml is not valid XML: {error}"]
    if root.tag != f"{SITEMAP_NAMESPACE}urlset":
        return ["sitemap.xml must use the sitemap urlset root"]
    urls = [
        (element.text or "").strip()
        for element in root.findall(f"{SITEMAP_NAMESPACE}url/{SITEMAP_NAMESPACE}loc")
    ]
    errors: list[str] = []
    if len(urls) != len(set(urls)):
        errors.append("sitemap.xml must not contain duplicate URLs")
    if set(urls) != SITEMAP_URLS:
        errors.append(
            "sitemap.xml URLs must be exactly the canonical homepage and legal notice"
        )
    return errors


def main() -> int:
    failures: list[str] = []
    if len(HTML_FILES) != 2:
        failures.append(f"expected 2 HTML files, found {len(HTML_FILES)}")
    for path in HTML_FILES:
        failures.extend(f"{path.relative_to(ROOT)}: {error}" for error in check_html(path))
    homepage = ROOT / "index.html"
    failures.extend(f"{homepage.relative_to(ROOT)}: {error}" for error in check_social_metadata(homepage))
    failures.extend(f"{homepage.relative_to(ROOT)}: {error}" for error in check_contact_links(homepage))
    failures.extend(f"{homepage.relative_to(ROOT)}: {error}" for error in check_bilingual_home(homepage))
    for path in CSS_FILES:
        failures.extend(f"{path.relative_to(ROOT)}: {error}" for error in check_css(path))
    failures.extend(check_social_preview())
    failures.extend(check_favicon())
    failures.extend(check_htaccess())
    failures.extend(check_robots())
    failures.extend(check_sitemap())

    if failures:
        print("Static site checks failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(f"Static site checks passed: {len(HTML_FILES)} HTML and {len(CSS_FILES)} CSS files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
