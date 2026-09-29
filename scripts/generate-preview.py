#!/usr/bin/env python3
"""Generate a deterministic preview of the first Reveal.js slide."""

from __future__ import annotations

import argparse
import contextlib
import functools
import http.server
import struct
import sys
import threading
import zlib
from pathlib import Path
from urllib.parse import quote

WIDTH = 1600
HEIGHT = 900
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, _format, *_args):
        pass


@contextlib.contextmanager
def local_server(directory: Path):
    handler = functools.partial(QuietHandler, directory=str(directory))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def validate_png(path: Path) -> None:
    if not path.is_file():
        raise RuntimeError(f"preview was not created: {path}")
    contents = path.read_bytes()
    if len(contents) < 33 or contents[:8] != PNG_SIGNATURE:
        raise RuntimeError(f"preview is not a valid PNG: {path}")
    offset = len(PNG_SIGNATURE)
    chunks = []
    while offset < len(contents):
        if offset + 12 > len(contents):
            raise RuntimeError(f"preview contains a truncated PNG chunk: {path}")
        length = struct.unpack(">I", contents[offset : offset + 4])[0]
        end = offset + 12 + length
        if end > len(contents):
            raise RuntimeError(f"preview contains a truncated PNG chunk: {path}")
        kind = contents[offset + 4 : offset + 8]
        data = contents[offset + 8 : offset + 8 + length]
        checksum = struct.unpack(">I", contents[offset + 8 + length : end])[0]
        if zlib.crc32(kind + data) & 0xFFFFFFFF != checksum:
            raise RuntimeError(f"preview contains an invalid PNG checksum: {path}")
        chunks.append((kind, data))
        offset = end
        if kind == b"IEND":
            break
    if not chunks or chunks[0][0] != b"IHDR" or len(chunks[0][1]) != 13 or chunks[-1][0] != b"IEND" or offset != len(contents):
        raise RuntimeError(f"preview is not a complete PNG: {path}")
    dimensions = struct.unpack(">II", chunks[0][1][:8])
    if dimensions != (WIDTH, HEIGHT):
        raise RuntimeError(
            f"preview has dimensions {dimensions[0]}x{dimensions[1]}; "
            f"expected {WIDTH}x{HEIGHT}: {path}"
        )


def generate_preview(source: Path, output: Path) -> None:
    from playwright.sync_api import sync_playwright

    if not source.is_file():
        raise RuntimeError(f"rendered presentation does not exist: {source}")

    failed_requests: list[str] = []
    with local_server(source.parent) as origin, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=1)
        page.on("requestfailed", lambda request: failed_requests.append(request.url))
        page.on("response", lambda response: failed_requests.append(f"{response.status} {response.url}") if response.status >= 400 else None)
        try:
            url = f"{origin}/{quote(source.name)}"
            page.goto(url, wait_until="networkidle", timeout=60_000)
            page.wait_for_function("window.Reveal && Reveal.isReady()", timeout=30_000)
            page.evaluate("Reveal.slide(0, 0); Reveal.layout()")

            # Fonts, ordinary images, and CSS background images can finish after
            # Reveal's ready event. Decode all of them before taking the shot.
            page.evaluate("""async () => {
              await document.fonts.ready;
              const urls = new Set();
              for (const element of document.querySelectorAll('*')) {
                for (const pseudo of [null, '::before', '::after']) {
                  const value = getComputedStyle(element, pseudo).backgroundImage;
                  for (const match of value.matchAll(/url\\(["']?(.*?)["']?\\)/g)) {
                    if (match[1]) urls.add(match[1]);
                  }
                }
              }
              const images = [...document.images].map(image => image.complete
                ? image.decode()
                : new Promise((resolve, reject) => {
                    image.addEventListener('load', resolve, {once: true});
                    image.addEventListener('error', reject, {once: true});
                  }));
              const backgrounds = [...urls].map(url => new Promise((resolve, reject) => {
                const image = new Image();
                image.onload = resolve;
                image.onerror = reject;
                image.src = url;
              }));
              await Promise.all([...images, ...backgrounds]);
              await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
            }""")

            slide = page.locator(".reveal .slides > section.present").first
            slide.wait_for(state="visible", timeout=10_000)
            box = slide.bounding_box()
            if not box or box["x"] < -1 or box["y"] < -1 or box["x"] + box["width"] > WIDTH + 1 or box["y"] + box["height"] > HEIGHT + 1:
                raise RuntimeError(f"title slide is not fully visible in the viewport: {box}")
            if failed_requests:
                raise RuntimeError("assets failed to load: " + ", ".join(sorted(set(failed_requests))))

            output.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=output, type="png", animations="disabled")
        finally:
            browser.close()

    validate_png(output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", type=Path, default=Path("template.html"))
    parser.add_argument("output", nargs="?", type=Path, default=Path("preview.png"))
    parser.add_argument("--validate-only", action="store_true", help="only validate the output PNG")
    args = parser.parse_args()
    try:
        if args.validate_only:
            validate_png(args.output)
        else:
            generate_preview(args.source.resolve(), args.output.resolve())
        print(f"Preview PNG is valid ({WIDTH}x{HEIGHT}): {args.output}")
        return 0
    except Exception as error:
        print(f"Preview generation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
