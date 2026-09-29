from __future__ import annotations

import contextlib
import functools
import http.server
import threading

import pytest
from playwright.sync_api import sync_playwright

from conftest import DIAGNOSTICS


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


def save_browser_diagnostics(page, name):
    target = DIAGNOSTICS / "browser" / name
    target.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=target / "page.png", full_page=True)
    (target / "dom.html").write_text(page.content(), encoding="utf-8")


def browser_state(page):
    return page.evaluate("""() => ({
      plugins: window.Reveal ? Object.keys(Reveal.getPlugins()) : [],
      simplemenu: window.Reveal ? Reveal.getConfig().simplemenu : null,
      menu: [...document.querySelectorAll('.menubar')].map(x => x.outerHTML),
      sections: [...document.querySelectorAll('section[data-stack-name]')].map(x => ({
        name: x.dataset.stackName, id: x.id, parent: x.parentElement && x.parentElement.tagName
      }))
    })""")


@pytest.mark.browser
@pytest.mark.integration
@pytest.mark.parametrize("viewport", [{"width": 1920, "height": 1080}, {"width": 800, "height": 600}], ids=["fullscreen", "embedded"])
def test_presentation_observable_behaviour(canonical_html, viewport):
    with server(canonical_html.parent) as origin, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport=viewport)
        failed = []
        console = []
        exceptions = []
        page.on("requestfailed", lambda request: failed.append(request.url))
        page.on("console", lambda message: console.append(f"{message.type}: {message.text}"))
        page.on("pageerror", lambda error: exceptions.append(str(error)))
        try:
            page.goto(f"{origin}/{canonical_html.name}", wait_until="networkidle")
            page.wait_for_function("window.Reveal && Reveal.isReady()")
            runtime_config = page.evaluate("Reveal.getConfig().simplemenu")
            assert isinstance(runtime_config, dict), f"Simplemenu runtime configuration is missing: {browser_state(page)}"
            expected_footer = "<nav class='menubar' aria-label='Presentation sections'><ul class='menu'></ul><span class='menu-slide-number' aria-label='Slide number'></span></nav>"
            assert runtime_config.get("barhtml", {}).get("footer") == expected_footer, (
                f"Simplemenu runtime footer is wrong: {runtime_config!r}; state={browser_state(page)}"
            )
            page.wait_for_function("document.querySelectorAll('.menubar .menu li').length >= 3")

        # Cover has its own top-left mark and suppresses the shared mark.
            cover_logo = page.locator("section.present.fs-cover .fs-cover-logo")
            assert cover_logo.is_visible()
            cover_box = cover_logo.bounding_box()
            canvas_box = page.locator(".reveal .slides").bounding_box()
            assert cover_box and canvas_box
            assert 0 <= cover_box["x"] - canvas_box["x"] <= 30, "cover logo is not at the upper-left edge"
            assert 0 <= cover_box["y"] - canvas_box["y"] <= 30, "cover logo is not at the upper-left edge"
            assert not page.locator("#fs-header").is_visible()
            assert not page.locator(".menubar").is_visible()
            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(150)

            groups = page.locator(".menubar .menu li").all_inner_texts()
            assert {"Introduction", "Formatting", "Examples"}.issubset(set(groups)), f"Simplemenu groups are wrong: {groups}; state={browser_state(page)}"
            assert page.locator(".menubar").is_visible(), "Simplemenu did not initialize"
            introduction = page.locator(".menubar .menu li", has_text="Introduction")
            assert "active" in (introduction.get_attribute("class") or "").split(), "Introduction is not the active section"
            numbers = page.locator(".menu-slide-number:visible")
            assert numbers.count(), "slide number is not visible on content slides"
            assert "/" in numbers.first.inner_text(), "Simplemenu did not update the slide number"
            number_before = numbers.first.inner_text()
            before = page.evaluate("Reveal.getIndices()")
            assert_logo_at_fixed_top_right(page)
            assert page.evaluate("Reveal.getIndices()") != before, "navigation did not advance the presentation"
            assert numbers.first.inner_text() != number_before, "Simplemenu did not update the slide number during navigation"
            assert page.locator(".menubar .menu li.active").inner_text() == "Formatting", "Formatting is not the active section"
            assert not exceptions, f"uncaught browser exceptions: {exceptions}; state={browser_state(page)}"
            assert not failed, f"browser failed to load resources: {failed}"
        except Exception:
            save_browser_diagnostics(page, viewport.get("width", "unknown").__str__())
            target = DIAGNOSTICS / "browser" / str(viewport.get("width", "unknown"))
            (target / "console.txt").write_text("\n".join(console + ["", "Exceptions:", *exceptions, "", repr(browser_state(page))]), encoding="utf-8")
            raise
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
        with pytest.raises(AssertionError):
            assert_logo_at_fixed_top_right(page)
        browser.close()
