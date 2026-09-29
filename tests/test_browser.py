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
        name: x.dataset.stackName, id: x.id,
        parent: x.parentElement && x.parentElement.tagName,
        parentId: x.parentElement && x.parentElement.id,
        parentClasses: x.parentElement && x.parentElement.className
      }))
    })""")


def assert_simplemenu_initialized(page, exceptions):
    """Fail immediately with the rendered stack layout instead of polling for 30s."""
    state = browser_state(page)
    assert not exceptions, f"Simplemenu raised a browser exception: {exceptions}; state={state}"
    items = page.locator(".menubar .menu li")
    assert items.count() >= 3, (
        "Simplemenu did not initialize a menu from the detected stack "
        f"attributes: {state['sections']}; plugins={state['plugins']}; menu={state['menu']}"
    )


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
            assert_simplemenu_initialized(page, exceptions)

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
            cover_details = page.locator("section.present.fs-cover .fs-cover-details")
            assert cover_details.evaluate("node => node.scrollHeight <= node.clientHeight"), "cover copy overflows vertically"
            for selector, size in (("h1.title", 80), (".subtitle", 48), (".author", 38), (".date", 32)):
                element = page.locator(f"section.present.fs-cover {selector}")
                assert element.evaluate("node => parseFloat(getComputedStyle(node).fontSize)") == pytest.approx(size, abs=0.1)
            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(150)

            groups = page.locator(".menubar .menu li").all_inner_texts()
            assert {"Introduction", "Formatting", "Examples"}.issubset(set(groups)), f"Simplemenu groups are wrong: {groups}; state={browser_state(page)}"
            links = page.locator(".menubar .menu a").evaluate_all(
                "items => Object.fromEntries(items.map(item => [item.textContent, item.getAttribute('href')]))"
            )
            assert links == {"Introduction": "#/1", "Formatting": "#/2", "Examples": "#/3"}
            assert page.locator(".menubar").is_visible(), "Simplemenu did not initialize"
            footer = page.locator(".menubar").bounding_box()
            menu = page.locator(".menubar .menu").bounding_box()
            assert footer and menu
            progress = page.locator(".reveal .progress").bounding_box()
            assert progress and footer["y"] + footer["height"] <= progress["y"] + 1, "footer overlaps the progress bar"
            assert menu["x"] + menu["width"] / 2 == pytest.approx(
                footer["x"] + footer["width"] / 2, abs=1.5
            ), "Simplemenu groups are not horizontally centered"
            menu_button = page.locator(".slide-menu-button")
            assert menu_button.is_visible(), "Reveal menu button is hidden behind the footer"
            assert menu_button.evaluate("node => getComputedStyle(node).pointerEvents !== 'none'")
            menu_button.click()
            assert page.locator(".slide-menu").is_visible(), "Reveal menu did not open"
            page.keyboard.press("Escape")
            introduction = page.locator(".menubar .menu li", has_text="Introduction")
            assert "active" in (introduction.get_attribute("class") or "").split(), "Introduction is not the active section"
            numbers = page.locator(".menu-slide-number:visible")
            assert numbers.count(), "slide number is not visible on content slides"
            assert "/" in numbers.first.inner_text(), "Simplemenu did not update the slide number"
            number_before = numbers.first.inner_text()
            introduction_link = introduction.locator("a")
            assert introduction_link.get_attribute("href") == "#/1"

            # A vertical move keeps the same menu item active while advancing
            # both Reveal's vertical index and Simplemenu's slide number.
            page.evaluate("Reveal.slide(2, 0)")
            formatting = page.locator(".menubar .menu li", has_text="Formatting")
            assert "active" in (formatting.get_attribute("class") or "").split()
            vertical_number = numbers.first.inner_text()
            page.keyboard.press("ArrowDown")
            page.wait_for_timeout(150)
            assert page.evaluate("({h: Reveal.getIndices().h, v: Reveal.getIndices().v})") == {"h": 2, "v": 1}
            assert "active" in (formatting.get_attribute("class") or "").split()
            assert numbers.first.inner_text() != vertical_number

            # Menu links navigate back to the first vertical slide in their
            # horizontal stack and update active state and numbering.
            introduction_link.click()
            page.wait_for_timeout(150)
            assert page.evaluate("({h: Reveal.getIndices().h, v: Reveal.getIndices().v})") == {"h": 1, "v": 0}
            assert "active" in (introduction.get_attribute("class") or "").split()
            assert numbers.first.inner_text() == number_before

            before = page.evaluate("Reveal.getIndices()")
            assert_logo_at_fixed_top_right(page)
            assert page.evaluate("Reveal.getIndices()") != before, "navigation did not advance the presentation"
            assert numbers.first.inner_text() != number_before, "Simplemenu did not update the slide number during navigation"
            assert page.locator(".menubar .menu li.active").inner_text() == "Formatting", "Formatting is not the active section"
            assert page.locator("section.present:not(.stack)").evaluate(
                "node => parseFloat(getComputedStyle(node).paddingRight)"
            ) == pytest.approx(210, abs=0.1), "regular slides must retain content-logo clearance"

            # The final slide contains a real, centered QR code for the
            # documented destination rather than a commented-out example.
            page.evaluate("Reveal.slide(Reveal.getHorizontalSlides().length - 1, 99)")
            page.wait_for_timeout(150)
            final_slide = page.locator(".reveal .slides section.present:not(.stack)")
            assert "fs-qr-slide" in (final_slide.get_attribute("class") or "").split(), (
                "Quarto did not attach fs-qr-slide to the rendered section"
            )
            assert "fs-qr-slide" not in (final_slide.locator("h2").get_attribute("class") or "").split(), (
                "Quarto attached fs-qr-slide to the heading instead of the rendered section"
            )
            assert final_slide.evaluate(
                "node => parseFloat(getComputedStyle(node).paddingRight)"
            ) == pytest.approx(0, abs=0.1), "final QR slide must have zero right padding"
            assert final_slide.locator(":scope > h2").evaluate(
                "node => parseFloat(getComputedStyle(node).paddingRight)"
            ) == pytest.approx(210, abs=0.1), "final-slide heading must retain content-logo clearance"
            qr_content = final_slide.locator(":scope > .fs-qr-content")
            assert qr_content.evaluate(
                "node => node.getBoundingClientRect().width"
            ) == pytest.approx(final_slide.evaluate(
                "node => node.getBoundingClientRect().width"
            ), abs=0.1), "QR-code container does not occupy the full slide width"
            qr = page.locator('section.present svg[data-qrcode-value="https://example.com"]')
            assert qr.is_visible(), "final QR code is not visible"
            qr_box = qr.bounding_box()
            slide_box = page.locator(
                ".reveal .slides section.present:not(.stack)"
            ).bounding_box()
            assert qr_box and slide_box
            assert qr_box["x"] + qr_box["width"] / 2 == pytest.approx(
                slide_box["x"] + slide_box["width"] / 2, abs=2
            ), "QR code is not centered"
            assert qr_box["width"] >= 100 * canvas_box["width"] / 1600, "QR code is too small to scan"
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
