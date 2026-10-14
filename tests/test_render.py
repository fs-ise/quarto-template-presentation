from html.parser import HTMLParser

import pytest
import yaml

from conftest import run
from helpers import assert_resources_exist, elements


class TitleAuthorParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.lines = []
        self.current = None
        self.target = None

    def handle_starttag(self, tag, attrs):
        classes = set(dict(attrs).get("class", "").split())
        if tag == "p" and "author" in classes:
            self.current = {"name": "", "affiliation": "", "text": ""}
            self.target = "text"
        elif self.current is not None and tag == "strong" and "author-name" in classes:
            self.target = "name"
        elif self.current is not None and tag == "span" and "affiliation" in classes:
            self.target = "affiliation"

    def handle_data(self, data):
        if self.current is None:
            return
        self.current["text"] += data
        if self.target in ("name", "affiliation"):
            self.current[self.target] += data

    def handle_endtag(self, tag):
        if self.current is None:
            return
        if tag == "p":
            self.lines.append(self.current)
            self.current = None
            self.target = None
        elif tag in ("strong", "span"):
            self.target = "text"


def title_author_lines(html):
    parser = TitleAuthorParser()
    parser.feed(html.read_text(encoding="utf-8"))
    return [
        tuple(" ".join(line[key].split()) for key in ("name", "affiliation", "text"))
        for line in parser.lines
    ]


def assert_rendered_presentation(html):
    assert html.is_file(), f"render did not create {html}"
    assert elements(html, "section", data_state="fs-cover-active"), "rendered cover state is missing"
    assert elements(html, "section", data_background_image="figures/title_background.png"), "cover background is missing"
    assert elements(html, "img", src="figures/fs_logo_blue.svg"), "rendered cover logo is missing"
    assert elements(html, "script", src="presentation_files/libs/revealjs/plugin/simplemenu/simplemenu.js") or any(
        "simplemenu" in (item.get("src") or "") for item in elements(html, "script")
    ), "rendered presentation does not load Simplemenu"
    assert_resources_exist(html)


@pytest.mark.integration
def test_canonical_example_rendering(canonical_html):
    assert_rendered_presentation(canonical_html)
    rendered = canonical_html.read_text(encoding="utf-8")
    assert 'data-qrcode-value="https://example.com"' in rendered
    assert not elements(canonical_html, "a", href="https://example.com")
    assert len(elements(canonical_html, "section", data_name="Conclusion")) == 1
    assert rendered.count('data-fragment-index="0"') == 2
    assert len(elements(canonical_html, "h3", id="explore-the-research")) == 1
    assert len(elements(canonical_html, "blockquote")) in (1, 2)
    assert "Which assumption would you revisit" in rendered
    assert "Presenter 1 Name" in rendered
    assert "Presenter 2 Name" in rendered
    assert "Presenter 3 Name" in rendered
    assert "Thank you — we look forward to the discussion." in rendered
    assert 'href="mailto:presenter1@institution.edu">presenter1@institution.edu</a>' in rendered
    assert (canonical_html.parent / "_extensions/qrcode/_extension.yml").is_file()
    for group in ("Introduction", "Formatting", "Examples"):
        assert len(elements(canonical_html, "section", data_name=group)) == 1, f"expected one first slide named {group}"
    assert not elements(canonical_html, "section", data_stack_name="Introduction"), "flat navigation must not create vertical section stacks"


@pytest.mark.integration
def test_generated_project_rendering(generated_html):
    assert_rendered_presentation(generated_html)
    rendered = generated_html.read_text(encoding="utf-8")
    assert 'data-qrcode-value="https://example.com"' in rendered
    assert not elements(generated_html, "a", href="https://example.com")
    assert "Let’s discuss" in rendered
    assert rendered.count('data-fragment-index="0"') == 2
    assert len(elements(generated_html, "h3", id="explore-the-research")) == 1
    assert len(elements(generated_html, "blockquote")) == 2
    assert "Presenter One" in rendered
    assert "Presenter 2 Name" in rendered
    assert "Presenter 3 Name" in rendered
    assert "Thank you — we look forward to the discussion." in rendered
    assert 'href="mailto:name@institution.edu">name@institution.edu</a>' in rendered
    assert 'href="https://github.com/presenter-one">github.com/presenter-one</a>' in rendered
    assert title_author_lines(generated_html) == [("CI", "", "CI")]
    project = generated_html.parents[1]
    for asset in ("fs_logo_blue.svg", "fs_logo_blue_content.svg", "title_background.png"):
        assert (project / "figures" / asset).is_file()
        assert (project / "_site/figures" / asset).is_file()
        assert not (project / asset).exists(), f"Quarto flattened {asset} into project root"


@pytest.mark.integration
def test_title_slide_author_metadata_rendering(canonical_html):
    project = canonical_html.parent
    affiliation = "Frankfurt School of Finance & Management"
    cases = [
        ("simple-string", "Gerit Wagner", [("Gerit Wagner", "", "Gerit Wagner")]),
        (
            "structured-with-affiliation",
            [{"name": {"literal": "Gerit Wagner"}, "affiliations": [{"name": affiliation}]}],
            [("Gerit Wagner", affiliation, f"Gerit Wagner, {affiliation}")],
        ),
        (
            "structured-without-affiliation",
            [{"name": {"literal": "Gerit Wagner"}}],
            [("Gerit Wagner", "", "Gerit Wagner")],
        ),
        (
            "multiple-authors",
            [
                {"name": {"literal": "Gerit Wagner"}, "affiliations": [{"name": affiliation}]},
                {"name": {"literal": "Ada Lovelace"}, "affiliations": [{"name": "Analytical Engines Lab"}]},
            ],
            [
                ("Gerit Wagner", affiliation, f"Gerit Wagner, {affiliation}"),
                ("Ada Lovelace", "Analytical Engines Lab", "Ada Lovelace, Analytical Engines Lab"),
            ],
        ),
        (
            "mixed-authors-and-affiliations",
            [
                "Grace Hopper",
                {
                    "name": {"literal": "Gerit Wagner"},
                    "affiliations": [
                        {"name": affiliation},
                        {"name": "Center for Data Science"},
                    ],
                },
            ],
            [
                ("Grace Hopper", "", "Grace Hopper"),
                (
                    "Gerit Wagner",
                    f"{affiliation}, Center for Data Science",
                    f"Gerit Wagner, {affiliation}, Center for Data Science",
                ),
            ],
        ),
    ]

    for case_name, author, expected in cases:
        source = project / f"author-{case_name}.qmd"
        metadata = {
            "title": "Author metadata rendering",
            "author": author,
            "format": {"fs-ise-presentation-revealjs": "default"},
        }
        source.write_text(
            "---\n"
            + yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True)
            + "---\n\n## Content\n\nRendering test.\n",
            encoding="utf-8",
        )
        run(["quarto", "render", source.name], cwd=project)
        actual = title_author_lines(source.with_suffix(".html"))
        assert actual == expected, f"unexpected title-slide authors for {case_name}: {actual}"


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
