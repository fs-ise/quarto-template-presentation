from __future__ import annotations

import contextlib
import functools
import http.server
import json
import re
import threading

import pytest
from playwright.sync_api import sync_playwright

from conftest import DIAGNOSTICS, run


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
    result = page.locator(".reveal .slides section.present:not(.stack):not(.fs-cover)").evaluate("""slide => {
      const style = getComputedStyle(slide, '::before');
      const box = slide.getBoundingClientRect();
      const scale = Reveal.getScale();
      return {
        content: style.content,
        background: style.backgroundImage,
        transform: style.transform,
        scale,
        logical: {
          width: parseFloat(style.width),
          height: parseFloat(style.height),
          top: parseFloat(style.top),
          right: parseFloat(style.right),
          slideWidth: box.width / scale,
          slideHeight: box.height / scale
        },
        viewport: {
          left: box.right - parseFloat(style.right) * scale - parseFloat(style.width) * scale,
          top: box.top + parseFloat(style.top) * scale,
          right: box.right - parseFloat(style.right) * scale,
          bottom: box.top + parseFloat(style.top) * scale + parseFloat(style.height) * scale
        },
        belongsToSlide: style.content !== 'none' && style.position === 'absolute'
      };
    }""")
    assert result["belongsToSlide"], f"content logo is not attached to the content slide: {result}"
    assert result["transform"] == "none", f"logo must not have an independent transform: {result}"
    assert "fs_logo_blue_content.svg" in result["background"], f"content logo background is missing: {result}"
    assert result["logical"]["width"] == pytest.approx(152.6, abs=0.2)
    return result


def assert_logo_on_content_slides(page):
    page.evaluate("Reveal.slide(1)")
    page.wait_for_timeout(150)
    first = logo_position(page)
    page.evaluate("Reveal.slide(2)")
    page.wait_for_timeout(150)
    another_content_slide = logo_position(page)
    for key, expected in (("right", 0), ("top", 0), ("height", 55.45)):
        assert first["logical"][key] == pytest.approx(expected, abs=0.75), f"unexpected logical logo {key}: {first}"
        assert first["logical"][key] == pytest.approx(another_content_slide["logical"][key], abs=0.2)
    heading = page.locator("section.present h1, section.present h2").first.bounding_box()
    logo = first["viewport"]
    if heading and logo:
        overlaps = not (heading["x"] + heading["width"] <= logo["left"] or logo["right"] <= heading["x"] or heading["y"] + heading["height"] <= logo["top"] or logo["bottom"] <= heading["y"])
        assert not overlaps, "content logo overlaps the active slide heading"
        wrapped_heading = page.locator("section.present h1, section.present h2").first.evaluate("""node => {
          const original = node.innerHTML;
          node.textContent = 'A deliberately long content heading that wraps over several lines to verify the reserved upper-right logo area';
          const rect = node.getBoundingClientRect().toJSON();
          node.innerHTML = original;
          return rect;
        }""")
        overlaps = not (
            wrapped_heading["right"] <= logo["left"] or logo["right"] <= wrapped_heading["left"]
            or wrapped_heading["bottom"] <= logo["top"] or logo["bottom"] <= wrapped_heading["top"]
        )
        assert not overlaps, "a wrapped content heading overlaps the content logo"
    return {"firstContent": first, "anotherContentSlide": another_content_slide}


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
      sections: [...document.querySelectorAll('section[data-name], section[data-stack-name]')].map(x => ({
        name: x.dataset.name || x.dataset.stackName, id: x.id,
        parent: x.parentElement && x.parentElement.tagName,
        parentId: x.parentElement && x.parentElement.id,
        parentClasses: x.parentElement && x.parentElement.className
      })),
      slides: [...document.querySelectorAll('.reveal .slides > section')].map(x => ({
        id: x.id, classes: x.className, heading: x.querySelector(':scope > h1, :scope > h2, :scope > h3')?.textContent.trim() || ''
      }))
    })""")


def assert_simplemenu_initialized(page, exceptions):
    """Fail immediately with the rendered slide labels instead of polling for 30s."""
    state = browser_state(page)
    assert not exceptions, f"Simplemenu raised a browser exception: {exceptions}; state={state}"
    items = page.locator(".menubar .menu li")
    assert items.count() >= 3, (
        "Simplemenu did not initialize a menu from the detected named slides "
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
    dimensions = menu.evaluate("""node => {
      const style = getComputedStyle(node);
      const mainSize = parseFloat(style.getPropertyValue('--r-main-font-size'));
      const scale = parseFloat(style.getPropertyValue('--simplemenu-scale'));
      return {fontSize: parseFloat(style.fontSize), mainSize, scale};
    }""")
    expected_font = min(80, max(16, dimensions["mainSize"] * dimensions["scale"]))
    assert dimensions["fontSize"] == pytest.approx(expected_font, abs=0.15), (
        f"Simplemenu's native responsive scale is wrong: {dimensions}"
    )
    menu_rows = page.locator(".menubar .menu").evaluate("""menu => {
      const style = getComputedStyle(menu);
      const links = [...menu.querySelectorAll('a')].map(link => link.getBoundingClientRect());
      return {
        direction: style.flexDirection,
        wrap: style.flexWrap,
        tops: links.map(box => box.top)
      };
    }""")
    assert menu_rows["direction"] == "row" and menu_rows["wrap"] == "nowrap", (
        f"Simplemenu menu must remain a single horizontal row: {menu_rows}"
    )
    assert max(menu_rows["tops"]) - min(menu_rows["tops"]) <= 1, (
        f"Simplemenu entries are vertically stacked instead of sharing one row: {menu_rows}"
    )
    footer_box = menu.bounding_box()
    button_box = page.locator(".slide-menu-button").bounding_box()
    number_box = page.locator(".menubar .slide-number").bounding_box()
    assert footer_box and button_box and number_box
    assert footer_box["height"] == pytest.approx(dimensions["fontSize"] * 2.4, abs=1), (
        f"Simplemenu footer band is not at the compact 2.4em height: {footer_box}, {dimensions}"
    )
    hamburger_gaps = {
        "top": button_box["y"] - footer_box["y"],
        "bottom": footer_box["y"] + footer_box["height"] - button_box["y"] - button_box["height"],
        "left": button_box["x"] - footer_box["x"],
    }
    assert min(hamburger_gaps.values()) >= 0, f"burger control extends outside the menu band: {hamburger_gaps}"
    assert max(hamburger_gaps.values()) - min(hamburger_gaps.values()) <= 1.5, (
        f"burger control should have equal top, bottom, and left spacing: {hamburger_gaps}"
    )
    number_inset = footer_box["x"] + footer_box["width"] - number_box["x"] - number_box["width"]
    assert number_inset == pytest.approx(dimensions["fontSize"] * 0.75, abs=2), (
        f"native slide number is not shifted toward the footer's right edge: {number_inset}px inset"
    )
    boxes = page.locator(".slide-menu-button, .menubar .menu a, .menubar .slide-number").evaluate_all(
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
@pytest.mark.parametrize("viewport", [{"width": 1894, "height": 950}, {"width": 1600, "height": 900}, {"width": 1280, "height": 720}, {"width": 800, "height": 450}, {"width": 800, "height": 600}], ids=["1894x950", "1600x900", "1280x720", "800x450", "800x600"])
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
            assert runtime_config.get("flat") is True, f"Simplemenu flat navigation is not enabled: {runtime_config!r}"
            assert runtime_config.get("csspath") is False
            assert page.evaluate("Reveal.getConfig().slideNumber") == "c/t", "Reveal's native current/total numbering is not configured"
            expected_footer = "<nav class='menubar' aria-label='Presentation sections'><ul class='menu'></ul><div class='slide-number'></div></nav>"
            assert runtime_config.get("barhtml", {}).get("footer") == expected_footer, (
                f"Simplemenu runtime footer is wrong: {runtime_config!r}; state={browser_state(page)}"
            )
            assert_simplemenu_initialized(page, exceptions)
            state = browser_state(page)
            assert not any("stack" in slide["classes"].split() for slide in state["slides"]), (
                f"flat navigation rendered vertical stacks or empty section dividers: {state['slides']}"
            )
            content_slides = [slide for slide in state["slides"] if "fs-cover" not in slide["classes"]]
            assert all(slide["heading"] for slide in content_slides), f"found an empty content/divider slide: {state['slides']}"

        # Cover has its own top-left mark and suppresses the shared mark.
            cover_logo = page.locator("section.present.fs-cover .fs-cover-logo")
            assert cover_logo.is_visible()
            cover_box = cover_logo.bounding_box()
            canvas_box = page.locator(".reveal .slides").bounding_box()
            assert cover_box and canvas_box
            assert 0 <= cover_box["x"] - canvas_box["x"] <= 30, "cover logo is not at the upper-left edge"
            assert 0 <= cover_box["y"] - canvas_box["y"] <= 30, "cover logo is not at the upper-left edge"
            assert page.locator("section.present.fs-cover").evaluate("node => getComputedStyle(node, '::before').content") == "none"
            assert not page.locator(".menubar").is_visible()
            cover_details = page.locator("section.present.fs-cover .fs-cover-details")
            assert cover_details.evaluate("node => node.scrollHeight <= node.clientHeight"), "cover copy overflows vertically"
            title = page.locator("section.present.fs-cover h1.title")
            assert 42 <= title.evaluate("node => parseFloat(getComputedStyle(node).fontSize)") <= 72
            assert title.bounding_box()["width"] > 0
            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(150)

            groups = page.locator(".menubar .menu li").all_inner_texts()
            assert groups == ["Introduction", "Formatting", "Examples"], f"Simplemenu groups are wrong: {groups}; state={browser_state(page)}"
            links = page.locator(".menubar .menu a").evaluate_all(
                "items => Object.fromEntries(items.map(item => [item.textContent, item.getAttribute('href')]))"
            )
            assert set(links) == set(groups) and all(href.startswith("#/") for href in links.values()), (
                f"Simplemenu links do not target the named content slides: {links}"
            )
            resolved_links = page.evaluate("""links => Object.fromEntries(Object.entries(links).map(([name, href]) => {
              const id = href.slice(2);
              return [name, Boolean(document.getElementById(id))];
            }))""", links)
            assert all(resolved_links.values()), f"Simplemenu contains broken navigation links: {links}"
            assert page.locator(".menubar").is_visible(), "Simplemenu did not initialize"
            footer = page.locator(".menubar").bounding_box()
            assert footer
            links_box = navigation_links_box(page)
            progress = page.locator(".reveal .progress").bounding_box()
            assert progress and footer["y"] + footer["height"] <= progress["y"] + 1, "footer overlaps the progress bar"
            assert (links_box["left"] + links_box["right"]) / 2 == pytest.approx(
                canvas_box["x"] + canvas_box["width"] / 2, abs=1.5
            ), "Simplemenu groups are not horizontally centered over the slide canvas"
            assert_simplemenu_layout(page)
            menubar = page.locator(".menubar")
            assert menubar.evaluate("node => getComputedStyle(node).backgroundColor") == "rgb(255, 255, 255)"
            menu_line_color = menubar.evaluate("node => getComputedStyle(node).borderTopColor")
            progress_line_color = page.locator(".reveal .progress span").evaluate(
                "node => getComputedStyle(node).backgroundColor"
            )
            assert menu_line_color == "rgb(0, 46, 255)"
            assert progress_line_color == menu_line_color, (
                f"menu separator and bottom progress line use different colors: {menu_line_color}, {progress_line_color}"
            )
            assert menubar.evaluate("node => getComputedStyle(node).borderTopWidth") == "2px"
            menu_button = page.locator(".slide-menu-button")
            assert menu_button.is_visible(), "Reveal menu button is hidden behind the footer"
            assert menu_button.evaluate("node => getComputedStyle(node).pointerEvents !== 'none'")
            menu_button.click()
            assert page.locator(".slide-menu").is_visible(), "Reveal menu did not open"
            page.keyboard.press("Escape")
            introduction = page.locator(".menubar .menu li", has_text="Introduction")
            assert "active" in (introduction.get_attribute("class") or "").split(), "Introduction is not the active section"
            numbers = page.locator(".menubar .slide-number:visible")
            assert numbers.count() == 1, "Reveal's native slide number was not moved into the menubar"
            assert not page.locator(".menu-slide-number").count(), "custom JavaScript slide-number output remains"
            assert "/" in numbers.first.inner_text(), "Simplemenu did not update the slide number"
            number_before = numbers.first.inner_text()
            number_state = page.evaluate("({current: Reveal.getSlidePastCount() + 1, total: Reveal.getTotalSlides()})")
            normalized_number = re.sub(r"\s+", " ", number_before).strip()
            assert normalized_number == f"{number_state['current']} / {number_state['total']}", (
                f"native slide number does not match Reveal's current/total position: {number_before!r}, {number_state}"
            )
            number_style = numbers.first.evaluate("node => ({color: getComputedStyle(node).color, align: getComputedStyle(node).textAlign})")
            assert number_style == {"color": "rgb(0, 51, 102)", "align": "right"}, (
                f"slide counter lost its FS-ISE color or right alignment: {number_style}"
            )
            introduction_link = introduction.locator("a")
            assert introduction_link.get_attribute("href") == links["Introduction"]

            # Flat content slides inherit their section until the next named
            # slide, while Reveal's native number advances on each slide.
            page.evaluate("Reveal.slide(2)")
            formatting = page.locator(".menubar .menu li", has_text="Formatting")
            assert "active" in (formatting.get_attribute("class") or "").split()
            formatting_number = numbers.first.inner_text()
            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(150)
            assert page.evaluate("({h: Reveal.getIndices().h, v: Reveal.getIndices().v})") == {"h": 3, "v": 0}
            assert "active" in (formatting.get_attribute("class") or "").split()
            assert numbers.first.inner_text() != formatting_number
            active_link = formatting.locator("a")
            active_style = active_link.evaluate("node => ({color: getComputedStyle(node).color, shadow: getComputedStyle(node).boxShadow})")
            assert active_style["color"] == "rgb(0, 46, 255)" and "0, 46, 255" in active_style["shadow"], (
                f"active section is missing FS-ISE blue emphasis and underline: {active_style}"
            )

            # Menu links navigate to the first content slide in a section.
            introduction_link.click()
            page.wait_for_timeout(150)
            assert page.evaluate("({h: Reveal.getIndices().h, v: Reveal.getIndices().v})") == {"h": 1, "v": 0}
            assert "active" in (introduction.get_attribute("class") or "").split()
            assert numbers.first.inner_text() == number_before

            before = page.evaluate("Reveal.getIndices()")
            positions = assert_logo_on_content_slides(page)
            assert page.evaluate("Reveal.getIndices()") != before, "navigation did not advance the presentation"
            assert numbers.first.inner_text() != number_before, "Simplemenu did not update the slide number during navigation"
            assert page.locator(".menubar .menu li.active").inner_text() == "Formatting", "Formatting is not the active section"
            save_content_artifact(page, "canonical", viewport, positions)
            content_padding = page.locator("section.present:not(.stack)").evaluate("""node => {
              const style = getComputedStyle(node);
              return {
                top: parseFloat(style.paddingTop),
                left: parseFloat(style.paddingLeft),
                right: parseFloat(style.paddingRight)
              };
            }""")
            assert content_padding == {"top": 0, "left": 0, "right": 64}, (
                f"content title/body inset did not move up and left together: {content_padding}"
            )

            # The final slide contains a real, centered QR code for the
            # documented destination rather than a commented-out example.
            page.evaluate("Reveal.slide(Reveal.getHorizontalSlides().length - 1)")
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
                "node => parseFloat(getComputedStyle(node).width)"
            ) < final_slide.evaluate("node => node.getBoundingClientRect().width / Reveal.getScale()"), "final-slide heading must retain content-logo clearance"
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
        page.add_style_tag(content=".reveal .slides section.present:not(.stack)::before { transform: translateX(-120px) }")
        with pytest.raises(AssertionError):
            assert_logo_on_content_slides(page)
        browser.close()


@pytest.mark.browser
@pytest.mark.integration
def test_presentation_scales_inside_an_iframe(canonical_html):
    with server(canonical_html.parent) as origin, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 800})
        page.set_content(
            f'<iframe title="presentation" src="{origin}/{canonical_html.name}" '
            'style="display:block;width:800px;height:450px;border:0"></iframe>'
        )
        frame = page.frame_locator('iframe[title="presentation"]')
        frame.locator(".reveal").wait_for()
        frame.locator(".reveal").evaluate("node => node.ownerDocument.defaultView.Reveal.slide(1, 0)")
        frame.locator(".reveal .slides section.present:not(.stack):not(.fs-cover)").wait_for()
        frame.locator(".menubar").wait_for()
        frame.locator(".reveal .slides section.present:not(.stack):not(.fs-cover)").evaluate(
            "slide => slide.ownerDocument.defaultView.Reveal.isReady()"
        )
        content_logo = frame.locator(".reveal .slides section.present:not(.stack):not(.fs-cover)")
        dimensions = content_logo.evaluate("""slide => {
          const mark = getComputedStyle(slide, '::before');
          const reveal = slide.ownerDocument.defaultView.Reveal;
          const scale = reveal.getScale();
          const rect = slide.ownerDocument.querySelector('.reveal .slides').getBoundingClientRect();
          return {
            scale,
            slideWidth: rect.width / scale,
            slideHeight: rect.height / scale,
            logoWidth: parseFloat(mark.width),
            logoTop: parseFloat(mark.top),
            logoRight: parseFloat(mark.right),
            slideRight: rect.right
          };
        }""")
        assert dimensions["slideWidth"] == pytest.approx(1600, abs=1)
        assert dimensions["slideHeight"] == pytest.approx(900, abs=1)
        assert dimensions["logoWidth"] == pytest.approx(152.6, abs=0.2)
        assert dimensions["logoTop"] == pytest.approx(0, abs=0.1)
        assert dimensions["logoRight"] == pytest.approx(0, abs=0.1)
        frame.locator(".reveal").press("ArrowRight")
        frame.locator(".reveal").evaluate("node => node.ownerDocument.defaultView.Reveal.slide(3)")
        assert frame.locator("section.present").count() > 0
        assert frame.locator(".menubar").is_visible()
        frame_menu = frame.locator(".menubar")
        frame_links = frame.locator(".menubar .menu a")
        frame_link_boxes = frame_links.evaluate_all("nodes => nodes.map(node => node.getBoundingClientRect().toJSON())")
        frame_width = frame.locator(".reveal").evaluate("node => node.ownerDocument.defaultView.innerWidth")
        assert frame_link_boxes
        assert max(box["top"] for box in frame_link_boxes) - min(box["top"] for box in frame_link_boxes) <= 1, (
            f"iframe Simplemenu entries are not in one row: {frame_link_boxes}"
        )
        assert (min(box["left"] for box in frame_link_boxes) + max(box["right"] for box in frame_link_boxes)) / 2 == pytest.approx(
            frame_width / 2, abs=1.5
        ), "iframe Simplemenu links are not centered within its presentation viewport"
        assert frame.locator(".menubar .slide-number").count() == 1
        assert_simplemenu_layout(frame)
        frame.locator(".slide-menu-button").click()
        assert frame.locator(".slide-menu").is_visible()
        browser.close()


@pytest.mark.browser
@pytest.mark.integration
def test_vertical_stacks_remain_available_when_opted_in(canonical_html):
    """The default is flat, but the official plugin's stack mode remains usable."""
    source = canonical_html.parent / "vertical.qmd"
    source.write_text('''---
title: "Vertical navigation compatibility"
format:
  fs-ise-presentation-revealjs:
    section-divs: true
    simplemenu:
      flat: false
---

# Introduction {data-stack-name="Introduction"}

## First content slide

This is the first slide in a vertical stack.

## Second content slide

This remains in the Introduction stack.

# Next {data-stack-name="Next"}

## Next content slide

This starts another stack.
''', encoding="utf-8")
    run(["quarto", "render", source.name], cwd=source.parent)
    html = source.with_suffix(".html")
    with server(html.parent) as origin, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        exceptions = []
        page.on("pageerror", lambda error: exceptions.append(str(error)))
        page.goto(f"{origin}/{html.name}", wait_until="networkidle")
        page.wait_for_function("window.Reveal && Reveal.isReady()")
        assert page.evaluate("Reveal.getConfig().simplemenu.flat") is False
        assert page.locator(".reveal .slides > section.stack").count() == 2
        assert page.locator(".menubar .menu li").all_inner_texts() == ["Introduction", "Next"]
        page.keyboard.press("ArrowRight")
        page.wait_for_timeout(150)
        introduction = page.locator(".menubar .menu li", has_text="Introduction")
        assert "active" in (introduction.get_attribute("class") or "").split()
        number = page.locator(".menubar .slide-number")
        first_number = number.inner_text()
        page.keyboard.press("ArrowDown")
        page.wait_for_timeout(150)
        assert page.evaluate("({h: Reveal.getIndices().h, v: Reveal.getIndices().v})") == {"h": 1, "v": 1}
        assert "active" in (introduction.get_attribute("class") or "").split()
        assert number.inner_text() != first_number
        page.locator(".menubar .menu li", has_text="Next").locator("a").click()
        page.wait_for_timeout(150)
        assert page.evaluate("({h: Reveal.getIndices().h, v: Reveal.getIndices().v})") == {"h": 2, "v": 0}
        assert "active" in (page.locator(".menubar .menu li", has_text="Next").get_attribute("class") or "").split()
        assert not exceptions, f"vertical-stack presentation raised browser exceptions: {exceptions}"
        browser.close()


@pytest.mark.browser
@pytest.mark.integration
@pytest.mark.parametrize("viewport", [{"width": 1894, "height": 950}, {"width": 1600, "height": 900}, {"width": 1280, "height": 720}, {"width": 800, "height": 450}, {"width": 800, "height": 600}], ids=["1894x950", "1600x900", "1280x720", "800x450", "800x600"])
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

        title = page.locator("section.present.fs-cover h1.title")
        title_size = title.evaluate(
            "node => parseFloat(getComputedStyle(node).fontSize)"
        )
        assert 42 <= title_size <= 72
        slide_box = page.locator("section.present.fs-cover").bounding_box()
        title_box = title.bounding_box()
        assert slide_box and title_box
        assert title_box["x"] >= slide_box["x"] and title_box["x"] + title_box["width"] <= slide_box["x"] + slide_box["width"]
        assert page.locator("section.present.fs-cover .fs-cover-details").evaluate(
            "node => node.scrollHeight <= node.clientHeight"
        ), "generated cover copy overflows vertically"

        page.keyboard.press("ArrowRight")
        page.wait_for_timeout(150)
        footer = page.locator(".menubar").bounding_box()
        links_box = navigation_links_box(page)
        assert footer
        slide_canvas = page.locator(".reveal .slides").bounding_box()
        assert slide_canvas
        assert (links_box["left"] + links_box["right"]) / 2 == pytest.approx(
            slide_canvas["x"] + slide_canvas["width"] / 2,
            abs=1.5,
        ), "generated Simplemenu links are not centered against the full slide"
        assert_simplemenu_layout(page)
        positions = assert_logo_on_content_slides(page)
        save_content_artifact(page, "copier", viewport, positions)

        menu_button = page.locator(".slide-menu-button")
        menu_button.click()
        assert page.locator(".slide-menu").is_visible()
        page.keyboard.press("Escape")
        conclusion = page.locator(".menubar .menu li", has_text="Conclusion")
        conclusion.locator("a").click()
        page.wait_for_timeout(150)
        assert "active" in (conclusion.get_attribute("class") or "").split()
        assert "/" in page.locator(".menubar .slide-number:visible").inner_text()
        assert not exceptions, f"generated presentation raised browser exceptions: {exceptions}"
        browser.close()


@pytest.mark.browser
@pytest.mark.integration
@pytest.mark.parametrize(
    "viewport",
    [
        {"width": 1600, "height": 900},
        {"width": 1280, "height": 720},
        {"width": 800, "height": 450},
    ],
    ids=["1600x900", "1280x720", "800x450"],
)
def test_adaptive_cover_content(canonical_html, viewport):
    variants = [
        ("A short title", "A concise subtitle", ["Ada Lovelace"], "12 October 2026"),
        (
            "Understanding heterogeneous treatment effects in longitudinal observational studies: evidence from a multi-country comparative analysis",
            "", ["Ada Lovelace"], "12 October 2026",
        ),
        (
            "A comprehensive assessment of institutional resilience and its implications for sustainable economic development",
            "Evidence from emerging markets, with a particular focus on measurement, identification, and policy implementation",
            ["Ada Lovelace"], "12 October 2026",
        ),
        (
            "Evaluating long-term institutional resilience through comparative analysis " * 4,
            "A study of evidence, methods, and implications", ["Ada Lovelace"], "12 October 2026",
        ),
        (
            "Collaborative research findings", "A subtitle", ["Ada Lovelace", "Grace Hopper", "Katherine Johnson", "Mary Jackson"],
            "12 October 2026",
        ),
        ("Title without optional metadata", None, ["Ada Lovelace"], None),
    ]
    with server(canonical_html.parent) as origin, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport=viewport)
        page.goto(f"{origin}/{canonical_html.name}", wait_until="networkidle")
        page.wait_for_function("window.Reveal && Reveal.isReady()")
        page.evaluate("Reveal.slide(0)")
        slide = page.locator("section.present.fs-cover")
        canvas = page.locator(".reveal .slides")
        composition = None
        for title_text, subtitle_text, authors, date_text in variants:
            page.evaluate("""({title, subtitle, authors, date}) => {
              const cover = document.querySelector('.fs-cover');
              const set = (selector, text, tag = 'p') => {
                let node = cover.querySelector(selector);
                if (text == null || text === '') { node?.remove(); return; }
                if (!node) { node = document.createElement(tag); node.className = selector.replace('.', ''); cover.querySelector('.fs-cover-details').append(node); }
                node.textContent = text;
              };
              set('h1.title', title, 'h1');
              set('.subtitle', subtitle);
              let group = cover.querySelector('.authors');
              if (!authors.length) group?.remove();
              else {
                if (!group) { group = document.createElement('div'); group.className = 'authors'; cover.querySelector('.fs-cover-details').append(group); }
                group.replaceChildren(...authors.map(name => { const author = document.createElement('p'); author.className = 'author'; author.textContent = name; return author; }));
              }
              set('.date', date);
            }""", {"title": title_text, "subtitle": subtitle_text, "authors": authors, "date": date_text})
            page.evaluate("window.dispatchEvent(new Event('resize'))")
            page.wait_for_timeout(80)
            slide_box = slide.bounding_box()
            canvas_box = canvas.bounding_box()
            logo_box = slide.locator(".fs-cover-logo").bounding_box()
            details = slide.locator(".fs-cover-details")
            details_box = details.bounding_box()
            assert slide_box and canvas_box and logo_box and details_box
            for element in [slide.locator(".title"), *slide.locator(".subtitle, .author, .date").all()]:
                if not element.count():
                    continue
                box = element.bounding_box()
                if box:
                    assert box["x"] >= slide_box["x"] - 1 and box["x"] + box["width"] <= slide_box["x"] + slide_box["width"] + 1
                    assert box["y"] >= slide_box["y"] - 1 and box["y"] + box["height"] <= slide_box["y"] + slide_box["height"] + 1, f"{element.inner_text()[:60]!r}: text box {box}, slide {slide_box}, details {details.evaluate('node => [node.scrollHeight, node.clientHeight]')}, font {element.evaluate('node => getComputedStyle(node).fontSize')}"
            assert details_box["y"] >= slide_box["y"] and details_box["y"] + details_box["height"] <= slide_box["y"] + slide_box["height"]
            assert details.evaluate("node => node.scrollHeight <= node.clientHeight + 1"), "cover details overflow vertically"
            title = slide.locator("h1.title")
            title_size = title.evaluate("node => parseFloat(getComputedStyle(node).fontSize)")
            assert 42 <= title_size <= 72, f"title size outside configured bounds: {title_size}"
            if title_text.startswith("Evaluating long-term institutional resilience"):
                assert title_size < 72, "an exceptionally long title did not shrink within the configured range"
            elements = slide.locator(".title, .subtitle, .author, .date").evaluate_all("nodes => nodes.map(node => ({text: node.textContent, rect: node.getBoundingClientRect().toJSON()}))")
            for index, current in enumerate(elements):
                for other in elements[index + 1:]:
                    a, b = current["rect"], other["rect"]
                    overlap = not (a["right"] <= b["left"] or b["right"] <= a["left"] or a["bottom"] <= b["top"] or b["bottom"] <= a["top"])
                    assert not overlap, f"cover metadata overlaps: {current['text']} / {other['text']}"
            authors_group = slide.locator(".authors")
            if authors_group.count():
                author_box = authors_group.bounding_box()
                first_author = slide.locator(".author").first.bounding_box()
                assert author_box and first_author
                line_top = author_box["y"]
                assert line_top + 2 < first_author["y"], "author separator intersects author text"
                assert author_box["x"] <= first_author["x"]
            assert 0 <= logo_box["x"] - canvas_box["x"] <= 30 and 0 <= logo_box["y"] - canvas_box["y"] <= 30
            normalized = (details_box["x"] / canvas_box["width"], details_box["width"] / canvas_box["width"])
            if composition is None:
                composition = normalized
            else:
                assert normalized == pytest.approx(composition, abs=0.015), "cover composition changed with metadata content"
            assert canvas_box["width"] / 1600 == pytest.approx(canvas_box["height"] / 900, abs=0.002), "Reveal scaling changed the 16:9 canvas"
        browser.close()
