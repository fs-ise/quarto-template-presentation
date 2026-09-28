from __future__ import annotations

import contextlib
import functools
import http.server
import threading

import pytest
from playwright.sync_api import sync_playwright


@contextlib.contextmanager
def server(directory):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    instance = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{instance.server_port}"
    finally:
        instance.shutdown()
        thread.join()


def logo_position(page):
    result = page.locator("#fs-header").evaluate("""logo => {
      const canvas = document.querySelector('.reveal .slides').getBoundingClientRect();
      const box = logo.getBoundingClientRect();
      return {right: canvas.right - box.right, top: box.top - canvas.top,
              visible: getComputedStyle(logo).display !== 'none'};
    }""")
    assert result["visible"], "shared content logo is not visible"
    return result


def assert_logo_at_fixed_top_right(page):
    first = logo_position(page)
    page.evaluate("Reveal.slide(2, 0)")
    page.wait_for_timeout(150)
    centered = logo_position(page)
    for key in ("right", "top"):
        assert abs(first[key] - centered[key]) < 1.5, f"logo {key} moved on vertically centred section slide: {first} -> {centered}"
        assert first[key] >= -1, f"logo is outside slide canvas: {first}"
        assert first[key] <= 30, f"logo is not anchored at the canvas top-right edge: {first}"
    heading = page.locator("section.present h1, section.present h2").first.bounding_box()
    logo = page.locator("#fs-header").bounding_box()
    if heading and logo:
        overlaps = not (heading["x"] + heading["width"] <= logo["x"] or logo["x"] + logo["width"] <= heading["x"] or heading["y"] + heading["height"] <= logo["y"] or logo["y"] + logo["height"] <= heading["y"])
        assert not overlaps, "content logo overlaps the active slide heading"


@pytest.mark.browser
@pytest.mark.integration
@pytest.mark.parametrize("viewport", [{"width": 1920, "height": 1080}, {"width": 800, "height": 600}], ids=["fullscreen", "embedded"])
def test_presentation_observable_behaviour(canonical_html, viewport):
    with server(canonical_html.parent) as origin, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport=viewport)
        failed = []
        page.on("requestfailed", lambda request: failed.append(request.url))
        page.goto(f"{origin}/{canonical_html.name}", wait_until="networkidle")
        page.wait_for_function("window.Reveal && Reveal.isReady()")

        # Cover has its own top-left mark and suppresses the shared mark.
        cover_logo = page.locator("section.present.fs-cover .fs-cover-logo")
        assert cover_logo.is_visible()
        cover_box = cover_logo.bounding_box()
        canvas_box = page.locator(".reveal .slides").bounding_box()
        assert cover_box and canvas_box
        assert 0 <= cover_box["x"] - canvas_box["x"] <= 30, "cover logo is not at the upper-left edge"
        assert 0 <= cover_box["y"] - canvas_box["y"] <= 30, "cover logo is not at the upper-left edge"
        assert not page.locator("#fs-header").is_visible()
        page.keyboard.press("ArrowRight")
        page.wait_for_timeout(150)
        assert_logo_at_fixed_top_right(page)

        groups = page.locator(".menubar .menu li").all_inner_texts()
        assert {"Introduction", "Formatting", "Examples"}.issubset(set(groups)), f"Simplemenu groups are wrong: {groups}"
        assert page.locator(".menubar").is_visible(), "Simplemenu did not initialize"
        numbers = page.locator(".slide-number:visible")
        assert numbers.count(), "slide number is not visible on content slides"
        assert "/" in numbers.first.inner_text(), "Simplemenu did not update the slide number"
        before = page.evaluate("Reveal.getIndices()")
        page.keyboard.press("ArrowRight")
        page.wait_for_timeout(100)
        assert page.evaluate("Reveal.getIndices()") != before, "keyboard navigation did not advance the presentation"
        assert not failed, f"browser failed to load resources: {failed}"
        browser.close()


@pytest.mark.browser
@pytest.mark.integration
def test_negative_incorrect_logo_position_is_detected(canonical_html):
    with server(canonical_html.parent) as origin, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 800})
        page.goto(f"{origin}/{canonical_html.name}", wait_until="networkidle")
        page.wait_for_function("window.Reveal && Reveal.isReady()")
        page.keyboard.press("ArrowRight")
        page.evaluate("document.querySelector('#fs-header').style.transform = 'translateX(-120px)'")
        try:
            assert_logo_at_fixed_top_right(page)
        except AssertionError as error:
            assert "moved" in str(error) or "outside" in str(error) or "overlaps" in str(error)
        else:
            raise AssertionError("browser check accepted an incorrectly positioned logo")
        browser.close()
