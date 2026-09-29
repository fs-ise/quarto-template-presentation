"""Semantic assertion helpers shared by static, render, and browser tests."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml


def load_yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), f"{path}: expected a YAML mapping"
    return value


class Document(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.elements: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def parse_html(path: Path) -> Document:
    document = Document()
    document.feed(path.read_text(encoding="utf-8"))
    return document


def elements(path: Path, tag: str | None = None, **attrs: str):
    return [
        values
        for element_tag, values in parse_html(path).elements
        if (tag is None or tag == element_tag)
        and all(values.get(name.replace("_", "-")) == value for name, value in attrs.items())
    ]


RESOURCE_ATTRIBUTES = ("src", "href", "data-src", "data-background-image", "poster")


def local_resources(path: Path) -> set[Path]:
    resources: set[Path] = set()
    for _tag, attrs in parse_html(path).elements:
        for name in RESOURCE_ATTRIBUTES:
            value = attrs.get(name) or ""
            parsed = urlsplit(value)
            if value and parsed.path and not parsed.scheme and not parsed.netloc and not value.startswith(("#", "//", "data:")):
                resources.add(path.parent / unquote(parsed.path))
    return resources


def assert_resources_exist(path: Path) -> None:
    missing = sorted(str(item.relative_to(path.parent)) for item in local_resources(path) if not item.is_file())
    assert not missing, f"{path}: missing local resources: {', '.join(missing)}"


def assert_manifest(path: Path, plugin_path: Path | None = None) -> None:
    manifest = load_yaml(path)
    reveal = manifest["contributes"]["formats"]["revealjs"]
    assert reveal.get("section-divs") is True, "section-divs must be enabled in revealjs format"
    assert reveal.get("slide-number") is True, "slide numbering must be enabled"
    assert reveal.get("revealjs-plugins") == ["simplemenu"], "Simplemenu must be the registered Reveal plugin"
    assert "simplemenu" not in reveal, "Simplemenu configuration belongs in the Reveal plugin declaration"

    plugin_path = plugin_path or path.parent / "_extensions/simplemenu/_extension.yml"
    plugin_manifest = load_yaml(plugin_path)
    plugins = plugin_manifest["contributes"]["revealjs-plugins"]
    plugin = next((item for item in plugins if item.get("name") == "Simplemenu"), None)
    assert plugin is not None, "embedded Simplemenu plugin declaration is missing"
    simplemenu = plugin.get("config", {}).get("simplemenu")
    assert isinstance(simplemenu, dict), "Simplemenu plugin configuration is missing"
    assert simplemenu.get("scale") == 0.67
    footer = simplemenu.get("barhtml", {}).get("footer", "")
    parser = Document()
    parser.feed(footer)
    assert any("menubar" in (a.get("class") or "").split() for _, a in parser.elements), "Simplemenu footer has no menubar"
    assert any("menu" in (a.get("class") or "").split() for _, a in parser.elements), "Simplemenu footer has no menu list"
    assert any("slide-number" in (a.get("class") or "").split() for _, a in parser.elements), "Simplemenu footer has no slide-number container"
