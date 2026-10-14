import hashlib
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
    assert dependency.get("title") == "Simplemenu"
    assert dependency.get("version") == "2.0.0"  # upstream v2.0.1 manifest value
    for filename in ("simplemenu.js", "simplemenu.css", "LICENSE"):
        assert (embedded / filename).is_file(), f"embedded Simplemenu is missing {filename}"
    expected_hashes = {
        "simplemenu.js": "a45a6694c73f81e42cef479cf1ba24819df164ceed9e0d030691015b6076f4d9",
        "simplemenu.css": "f39e993a55605bf965964b678a940d6fd178e8d390fad0ecd3f2ca329c6a4672",
    }
    for filename, expected in expected_hashes.items():
        actual = hashlib.sha256((embedded / filename).read_bytes()).hexdigest()
        assert actual == expected, f"{filename} is not the unmodified upstream v2.0.1 asset"
    provenance = (embedded / "README.md").read_text(encoding="utf-8")
    assert "v2.0.1" in provenance and "6fa39e6aca0ec8762d463c50ebf4fda92ad997da" in provenance


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


def test_negative_missing_native_reveal_slide_numbering(tmp_path):
    manifest = load_yaml(EXTENSION / "_extension.yml")
    manifest["contributes"]["formats"]["revealjs"]["slide-number"] = False
    broken = tmp_path / "_extension.yml"
    broken.write_text(__import__("yaml").safe_dump(manifest))
    try:
        assert_manifest(broken, EXTENSION / "_extensions/simplemenu/_extension.yml")
    except AssertionError as error:
        assert "native current/total slide number" in str(error)
    else:
        raise AssertionError("manifest check accepted missing Reveal slide numbering")


def test_negative_simplemenu_config_in_format_is_detected(tmp_path):
    manifest = load_yaml(EXTENSION / "_extension.yml")
    manifest["contributes"]["formats"]["revealjs"]["simplemenu"]["flat"] = False
    broken = tmp_path / "_extension.yml"
    broken.write_text(__import__("yaml").safe_dump(manifest))
    with pytest.raises(AssertionError, match="flat navigation must be the default"):
        assert_manifest(broken, EXTENSION / "_extensions/simplemenu/_extension.yml")
