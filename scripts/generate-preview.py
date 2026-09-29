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
    browser_messages: list[str] = []
    with local_server(source.parent) as origin, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=1)
        page.on(
            "requestfailed",
            lambda request: failed_requests.append(
                f"{request.url} ({request.failure or 'unknown request failure'})"
            ),
        )
        page.on("response", lambda response: failed_requests.append(f"{response.status} {response.url}") if response.status >= 400 else None)
        page.on("console", lambda message: browser_messages.append(f"{message.type}: {message.text}"))
        page.on("pageerror", lambda error: browser_messages.append(f"page error: {error}"))
        try:
            url = f"{origin}/{quote(source.name)}"
            page.goto(url, wait_until="networkidle", timeout=60_000)
            page.wait_for_function("window.Reveal && Reveal.isReady()", timeout=30_000)
            page.evaluate("Reveal.slide(0, 0); Reveal.layout()")

            # Reveal creates background elements lazily. Only validate assets
            # needed by the cover; later slides may intentionally refer to
            # resources that are not relevant to the preview.
            page.evaluate("""async () => {
              await document.fonts.ready;

              const fail = (kind, url, detail) => {
                throw new Error(`${kind} failed to load: ${url || '<missing URL>'}` +
                  (detail ? ` (${detail})` : ''));
              };
              const waitForImage = async (image, kind) => {
                const url = image.currentSrc || image.src;
                if (!image.complete) {
                  await new Promise((resolve, reject) => {
                    image.addEventListener('load', resolve, {once: true});
                    image.addEventListener('error', () => reject(
                      new Error(`${kind} failed to load: ${url || '<missing URL>'}`)
                    ), {once: true});
                  });
                }
                if (!image.naturalWidth) fail(kind, url, 'image is complete but empty');
                try {
                  await image.decode();
                } catch (error) {
                  fail(kind, url, error instanceof Error ? error.message : String(error));
                }
              };
              const loadUrl = (url, kind) => new Promise((resolve, reject) => {
                const image = new Image();
                image.onload = resolve;
                image.onerror = () => reject(new Error(`${kind} failed to load: ${url}`));
                image.src = url;
              });

              const cover = document.querySelector('.reveal .slides > section.present.fs-cover');
              if (!cover) throw new Error('title slide did not become the active Reveal slide');
              const logo = cover.querySelector('img.fs-cover-logo');
              if (!logo) throw new Error('cover logo element is missing');

              const background = document.querySelector('.reveal .backgrounds .slide-background.present');
              if (!background) throw new Error('title-slide background element is missing');
              const backgroundLayers = [background, ...background.querySelectorAll('*')];
              const backgroundImage = backgroundLayers
                .map(element => getComputedStyle(element).backgroundImage)
                .find(value => value && value !== 'none');
              if (!backgroundImage) throw new Error('title-slide background image URL is missing');
              const match = backgroundImage.match(/url\\(["']?(.*?)["']?\\)/);
              const backgroundUrl = match && match[1];
              if (!backgroundUrl) {
                throw new Error('title-slide background image URL is missing');
              }

              await Promise.all([
                waitForImage(logo, 'cover logo'),
                loadUrl(backgroundUrl, 'title-slide background'),
              ]);
              await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
            }""")

            slide = page.locator(".reveal .slides > section.present").first
            slide.wait_for(state="visible", timeout=10_000)
            box = slide.bounding_box()
            if not box or box["x"] < -1 or box["y"] < -1 or box["x"] + box["width"] > WIDTH + 1 or box["y"] + box["height"] > HEIGHT + 1:
                raise RuntimeError(f"title slide is not fully visible in the viewport: {box}")
            output.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=output, type="png", animations="disabled")
        except Exception as error:
            diagnostics = []
            if failed_requests:
                diagnostics.append("Failed requests:\n  " + "\n  ".join(sorted(set(failed_requests))))
            if browser_messages:
                diagnostics.append("Browser diagnostics:\n  " + "\n  ".join(browser_messages))
            if diagnostics:
                raise RuntimeError(f"{error}\n" + "\n".join(diagnostics)) from error
            raise
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
