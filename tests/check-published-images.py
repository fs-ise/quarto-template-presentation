#!/usr/bin/env python3
"""Check that local images referenced by a rendered presentation are present."""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urljoin, urlsplit
from urllib.request import Request, urlopen


IMAGE_ATTRIBUTES = ("src", "data-src", "data-background-image", "poster")
IMAGE_SUFFIXES = {".avif", ".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"}
CSS_URL = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE)


def is_local_image(value: str) -> bool:
    parsed = urlsplit(value)
    return (
        bool(parsed.path)
        and not parsed.scheme
        and not parsed.netloc
        and not value.startswith(("#", "//", "data:"))
        and Path(parsed.path).suffix.lower() in IMAGE_SUFFIXES
    )


class Images(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.paths: set[str] = set()

    def handle_starttag(self, _tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        for name in IMAGE_ATTRIBUTES:
            value = values.get(name) or ""
            if is_local_image(value):
                self.paths.add(unquote(urlsplit(value).path))

        for _quote, value in CSS_URL.findall(values.get("style") or ""):
            if is_local_image(value):
                self.paths.add(unquote(urlsplit(value).path))

        # A srcset entry consists of a URL followed by an optional descriptor.
        for item in (values.get("srcset") or "").split(","):
            value = item.strip().split(maxsplit=1)[0] if item.strip() else ""
            if is_local_image(value):
                self.paths.add(unquote(urlsplit(value).path))


def fetch(url: str, attempts: int = 1) -> bytes:
    request = Request(url, headers={"User-Agent": "presentation-image-check/1.0"})
    for attempt in range(attempts):
        try:
            with urlopen(request, timeout=30) as response:
                if response.status != 200:
                    raise RuntimeError(f"HTTP {response.status}: {url}")
                return response.read()
        except (HTTPError, URLError, TimeoutError) as error:
            if attempt == attempts - 1:
                raise RuntimeError(f"could not fetch {url}: {error}") from error
            time.sleep(5 * (attempt + 1))
    raise AssertionError("unreachable")


def referenced_images(html: str) -> list[str]:
    parser = Images()
    parser.feed(html)
    return sorted(parser.paths)


def check_directory(root: Path, document: str) -> list[str]:
    html_path = root / document
    if not html_path.is_file():
        raise RuntimeError(f"rendered document does not exist: {html_path}")
    paths = referenced_images(html_path.read_text(encoding="utf-8"))
    missing = [path for path in paths if not (html_path.parent / path).is_file()]
    if missing:
        raise RuntimeError("missing published images: " + ", ".join(missing))
    return paths


def check_url(base_url: str, document: str) -> list[str]:
    document_url = urljoin(base_url.rstrip("/") + "/", document)
    paths = referenced_images(fetch(document_url, attempts=6).decode("utf-8"))
    errors = []
    for path in paths:
        image_url = urljoin(document_url, path)
        try:
            fetch(image_url, attempts=3)
        except RuntimeError as error:
            errors.append(str(error))
    if errors:
        raise RuntimeError("missing images on GitHub Pages:\n" + "\n".join(errors))
    return paths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("location", help="published directory or base URL")
    parser.add_argument("--document", default="index.html")
    args = parser.parse_args()

    try:
        if urlsplit(args.location).scheme in {"http", "https"}:
            paths = check_url(args.location, args.document)
        else:
            paths = check_directory(Path(args.location), args.document)
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1

    if not paths:
        print("No local images found in the rendered presentation.", file=sys.stderr)
        return 1
    print(f"Verified {len(paths)} published image(s): {', '.join(paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
