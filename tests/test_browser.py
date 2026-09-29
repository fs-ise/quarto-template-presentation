from __future__ import annotations

import contextlib
import functools
import http.server
import json
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
    result = page.locator("#fs-header").evaluate("""async logo => {
      const reveal = document.querySelector('.reveal').getBoundingClientRect();
      const canvas = document.querySelector('.reveal .slides').getBoundingClientRect();
      const box = logo.getBoundingClientRect();
      const image = logo.querySelector('img');
      const imageBox = image.getBoundingClientRect();
      const imageStyle = getComputedStyle(image);
      const source = await (await fetch(image.src)).text();
      const parsed = new DOMParser().parseFromString(source, 'image/svg+xml').documentElement;
      parsed.style.cssText = 'position:absolute;visibility:hidden';
      document.body.appendChild(parsed);
      const artwork = parsed.getBBox();
      const viewBox = parsed.viewBox.baseVal;
      parsed.remove();
      const imageScaleX = box.width / viewBox.width;
      const imageScaleY = box.height / viewBox.height;
      const visible = {
        left: imageBox.left + (artwork.x - viewBox.x) * imageScaleX,
        top: imageBox.top + (artwork.y - viewBox.y) * imageScaleY,
        right: imageBox.right - (viewBox.x + viewBox.width - artwork.x - artwork.width) * imageScaleX,
        bottom: imageBox.bottom - (viewBox.y + viewBox.height - artwork.y - artwork.height) * imageScaleY
      };
      return {
        right: reveal.right - visible.right,
        top: visible.top - reveal.top,
        reveal: {left: reveal.left, top: reveal.top, right: reveal.right, bottom: reveal.bottom, width: reveal.width, height: reveal.height},
        canvas: {left: canvas.left, top: canvas.top, right: canvas.right, bottom: canvas.bottom, width: canvas.width, height: canvas.height},
        configuredMargin: Reveal.getConfig().margin,
        revealScale: Reveal.getScale(),
        logoBox: {left: box.left, top: box.top, right: box.right, bottom: box.bottom, width: box.width, height: box.height},
        imageBox: {left: imageBox.left, top: imageBox.top, right: imageBox.right, bottom: imageBox.bottom, width: imageBox.width, height: imageBox.height},
        imageMargins: {
          top: imageStyle.marginTop,
          right: imageStyle.marginRight,
          bottom: imageStyle.marginBottom,
          left: imageStyle.marginLeft
        },
        artwork: {x: artwork.x, y: artwork.y, width: artwork.width, height: artwork.height},
        visibleArtwork: visible,
        visible: getComputedStyle(logo).display !== 'none',
        directChild: logo.parentElement === document.querySelector('.reveal')
      };
    }""")
    assert result["visible"], "shared content logo is not visible"
    assert result["directChild"], f"content logo is not a direct child of Reveal: {result}"
    assert all(value == "0px" for value in result["imageMargins"].values()), (
        f"content logo image retains a computed margin: {result}"
    )
    return result


def assert_logo_at_fixed_top_right(page):
    first = logo_position(page)
    page.evaluate("Reveal.slide(2, 0)")
    page.wait_for_timeout(150)
    vertical_start = logo_position(page)
    page.evaluate("Reveal.slide(2, 1)")
    page.wait_for_timeout(150)
    vertical_next = logo_position(page)
    for key, expected in (("right", 32), ("top", 24)):
        assert first[key] == pytest.approx(expected, abs=0.75), (
            f"visible logo artwork does not have the expected {key} inset: {first}"
        )
        assert abs(first[key] - vertical_start[key]) < 1.5, f"logo {key} moved between horizontal slides: {first} -> {vertical_start}"
        assert abs(vertical_start[key] - vertical_next[key]) < 1.5, f"logo {key} moved during vertical navigation: {vertical_start} -> {vertical_next}"
    heading = page.locator("section.present h1, section.present h2").first.bounding_box()
    logo = page.locator("#fs-header").bounding_box()
    if heading and logo:
        overlaps = not (heading["x"] + heading["width"] <= logo["x"] or logo["x"] + logo["width"] <= heading["x"] or heading["y"] + heading["height"] <= logo["y"] or logo["y"] + logo["height"] <= heading["y"])
        assert not overlaps, "content logo overlaps the active slide heading"
    return {"firstContent": first, "verticalStart": vertical_start, "verticalNext": vertical_next}


def save_content_artifact(page, deck, viewport, positions):
    target = DIAGNOSTICS / "content-slides"
    target.mkdir(parents=True, exist_ok=True)
    size = f"{viewport['width']}x{viewport['height']}"
    page.evaluate("Reveal.slide(1, 0)")
    page.wait_for_timeout(150)
    page.screenshot(path=target / f"{deck}-{size}.png", animations="disabled")
    (target / f"{deck}-{size}.json").write_text(json.dumps(positions, indent=2), encoding="utf-8")


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


def navigation_links_box(page):
    """Return the union of the clickable links, not the potentially stretched ul."""
    return page.locator(".menubar .menu a").evaluate_all("""links => {
      const boxes = links.map(link => link.getBoundingClientRect());
      return {
        left: Math.min(...boxes.map(box => box.left)),
        right: Math.max(...boxes.map(box => box.right))
      };
    }""")


def assert_simplemenu_layout(page):
    menu = page.locator(".menubar")
    reveal_font = page.locator(".reveal").evaluate("node => parseFloat(getComputedStyle(node).fontSize)")
    menu_font = menu.evaluate("node => parseFloat(getComputedStyle(node).fontSize)")
    assert menu_font == pytest.approx(reveal_font * 0.7, abs=0.15), "Simplemenu's effective scale is not 0.7"
    boxes = page.locator(".slide-menu-button, .menubar .menu a, .menubar .menu-slide-number").evaluate_all(
        """nodes => nodes.filter(node => node.getClientRects().length).map(node => {
          const {left, right, top, bottom} = node.getBoundingClientRect();
          return {name: node.textContent.trim() || 'hamburger', box: {left, right, top, bottom}};
        })"""
    )
    for index, item in enumerate(boxes):
        for other in boxes[index + 1:]:
            a, b = item["box"], other["box"]
            overlaps = not (a["right"] <= b["left"] or b["right"] <= a["left"] or a["bottom"] <= b["top"] or b["bottom"] <= a["top"])
            assert not overlaps, f"Simplemenu elements overlap: {item['name']} and {other['name']}"


@pytest.mark.browser
@pytest.mark.integration
@pytest.mark.parametrize("viewport", [{"width": 1600, "height": 900}, {"width": 800, "height": 600}], ids=["1600x900", "embedded"])
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
            assert runtime_config.get("scale") == pytest.approx(0.7), f"Simplemenu runtime scale is wrong: {runtime_config!r}"
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
            for selector, size in (("h1.title", 72), (".subtitle", 48), (".author", 38), (".date", 32)):
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
            assert footer
            links_box = navigation_links_box(page)
            progress = page.locator(".reveal .progress").bounding_box()
            assert progress and footer["y"] + footer["height"] <= progress["y"] + 1, "footer overlaps the progress bar"
            assert (links_box["left"] + links_box["right"]) / 2 == pytest.approx(
                footer["x"] + footer["width"] / 2, abs=1.5
            ), "Simplemenu groups are not horizontally centered"
            assert_simplemenu_layout(page)
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
            positions = assert_logo_at_fixed_top_right(page)
            assert page.evaluate("Reveal.getIndices()") != before, "navigation did not advance the presentation"
            assert numbers.first.inner_text() != number_before, "Simplemenu did not update the slide number during navigation"
            assert page.locator(".menubar .menu li.active").inner_text() == "Formatting", "Formatting is not the active section"
            save_content_artifact(page, "canonical", viewport, positions)
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


@pytest.mark.browser
@pytest.mark.integration
@pytest.mark.parametrize("viewport", [{"width": 1600, "height": 900}, {"width": 800, "height": 600}], ids=["1600x900", "embedded"])
def test_generated_project_layout_and_controls(generated_html, viewport):
    """Exercise installed template assets, rather than only the source deck."""
    with server(generated_html.parent) as origin, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport=viewport)
        exceptions = []
        page.on("pageerror", lambda error: exceptions.append(str(error)))
        page.goto(f"{origin}/{generated_html.name}", wait_until="networkidle")
        page.wait_for_function("window.Reveal && Reveal.isReady()")
        assert_simplemenu_initialized(page, exceptions)

        title_size = page.locator("section.present.fs-cover h1.title").evaluate(
            "node => parseFloat(getComputedStyle(node).fontSize)"
        )
        assert title_size == pytest.approx(72, abs=0.1)
        assert page.locator("section.present.fs-cover .fs-cover-details").evaluate(
            "node => node.scrollHeight <= node.clientHeight"
        ), "generated cover copy overflows vertically"

        page.keyboard.press("ArrowRight")
        page.wait_for_timeout(150)
        footer = page.locator(".menubar").bounding_box()
        links_box = navigation_links_box(page)
        assert footer
        assert (links_box["left"] + links_box["right"]) / 2 == pytest.approx(
            footer["x"] + footer["width"] / 2, abs=1.5
        ), "generated Simplemenu links are not centered against the full slide"
        assert_simplemenu_layout(page)
        positions = assert_logo_at_fixed_top_right(page)
        save_content_artifact(page, "copier", viewport, positions)

        menu_button = page.locator(".slide-menu-button")
        menu_button.click()
        assert page.locator(".slide-menu").is_visible()
        page.keyboard.press("Escape")
        conclusion = page.locator(".menubar .menu li", has_text="Conclusion")
        conclusion.locator("a").click()
        page.wait_for_timeout(150)
        assert "active" in (conclusion.get_attribute("class") or "").split()
        assert "/" in page.locator(".menu-slide-number:visible").inner_text()
        assert not exceptions, f"generated presentation raised browser exceptions: {exceptions}"
        browser.close()
