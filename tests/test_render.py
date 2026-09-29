import pytest

from helpers import assert_resources_exist, elements


def assert_rendered_presentation(html):
    assert html.is_file(), f"render did not create {html}"
    assert elements(html, "section", data_state="fs-cover-active"), "rendered cover state is missing"
    assert elements(html, "section", data_background_image="figures/title_background.png"), "cover background is missing"
    assert elements(html, "img", src="figures/fs_logo_blue.svg"), "rendered logos are missing"
    assert elements(html, "script", src="presentation_files/libs/revealjs/plugin/simplemenu/simplemenu.js") or any(
        "simplemenu" in (item.get("src") or "") for item in elements(html, "script")
    ), "rendered presentation does not load Simplemenu"
    assert_resources_exist(html)


@pytest.mark.integration
def test_canonical_example_rendering(canonical_html):
    assert_rendered_presentation(canonical_html)
    for group in ("Introduction", "Formatting", "Examples"):
        assert len(elements(canonical_html, "section", data_stack_name=group)) == 1, f"expected one {group} section"


@pytest.mark.integration
def test_generated_project_rendering(generated_html):
    assert_rendered_presentation(generated_html)
    project = generated_html.parents[1]
    for asset in ("fs_logo_blue.svg", "title_background.png"):
        assert (project / "figures" / asset).is_file()
        assert (project / "_site/figures" / asset).is_file()
        assert not (project / asset).exists(), f"Quarto flattened {asset} into project root"


@pytest.mark.static
def test_negative_broken_image_reference(tmp_path):
    html = tmp_path / "index.html"
    html.write_text('<html><img src="figures/missing.png"></html>')
    try:
        assert_resources_exist(html)
    except AssertionError as error:
        assert "missing.png" in str(error)
    else:
        raise AssertionError("resource check accepted a broken image reference")
