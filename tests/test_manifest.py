from pathlib import Path

import pytest

from helpers import assert_manifest, load_yaml

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "_extensions/fs-ise-presentation"

pytestmark = pytest.mark.static


def test_extension_manifest_and_embedded_dependency():
    embedded = EXTENSION / "_extensions/simplemenu"
    assert_manifest(EXTENSION / "_extension.yml", embedded / "_extension.yml")
    dependency = load_yaml(embedded / "_extension.yml")
    assert dependency.get("title")
    for filename in ("simplemenu.js", "simplemenu.css", "LICENSE"):
        assert (embedded / filename).is_file(), f"embedded Simplemenu is missing {filename}"


def test_negative_missing_simplemenu_dependency(tmp_path):
    manifest = load_yaml(EXTENSION / "_extension.yml")
    manifest["contributes"]["formats"]["revealjs"]["revealjs-plugins"] = []
    broken = tmp_path / "_extension.yml"
    broken.write_text(__import__("yaml").safe_dump(manifest))
    try:
        assert_manifest(broken, EXTENSION / "_extensions/simplemenu/_extension.yml")
    except AssertionError as error:
        assert "Simplemenu" in str(error)
    else:
        raise AssertionError("manifest check accepted a missing Simplemenu dependency")


def test_negative_disabled_slide_numbering(tmp_path):
    manifest = load_yaml(EXTENSION / "_extension.yml")
    manifest["contributes"]["formats"]["revealjs"]["slide-number"] = False
    broken = tmp_path / "_extension.yml"
    broken.write_text(__import__("yaml").safe_dump(manifest))
    try:
        assert_manifest(broken, EXTENSION / "_extensions/simplemenu/_extension.yml")
    except AssertionError as error:
        assert "number" in str(error)
    else:
        raise AssertionError("manifest check accepted disabled slide numbering")


def test_negative_simplemenu_config_in_format_is_detected(tmp_path):
    manifest = load_yaml(EXTENSION / "_extension.yml")
    manifest["contributes"]["formats"]["revealjs"]["simplemenu"] = {"scale": 0.67}
    broken = tmp_path / "_extension.yml"
    broken.write_text(__import__("yaml").safe_dump(manifest))
    with pytest.raises(AssertionError, match="plugin declaration"):
        assert_manifest(broken, EXTENSION / "_extensions/simplemenu/_extension.yml")
