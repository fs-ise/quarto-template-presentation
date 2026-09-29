from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from conftest import ROOT, run
from helpers import assert_manifest, assert_resources_exist


def verify_install(project: Path) -> None:
    extension = project / "_extensions/fs-ise-presentation"
    assert_manifest(extension / "_extension.yml")
    embedded = extension / "_extensions/simplemenu"
    for filename in ("_extension.yml", "simplemenu.js", "simplemenu.css", "LICENSE"):
        assert (embedded / filename).is_file(), f"installation omitted Simplemenu {filename}"
    assert not (project / "_extensions/simplemenu").exists(), "embedded dependency was incorrectly installed at project level"


@pytest.mark.integration
def test_clean_quarto_add_uses_checkout(artifact_root):
    project = artifact_root / "quarto-add"
    project.mkdir()
    run(["quarto", "add", str(ROOT), "--no-prompt"], cwd=project)
    verify_install(project)
    shutil.copy(ROOT / "template.qmd", project / "presentation.qmd")
    run(["quarto", "render", "presentation.qmd"], cwd=project)
    assert_resources_exist(project / "presentation.html")


@pytest.mark.integration
def test_clean_quarto_use_template_uses_checkout(artifact_root):
    project = artifact_root / "use-template"
    project.mkdir()
    run(["quarto", "use", "template", str(ROOT), "--no-prompt"], cwd=project)
    verify_install(project)
    # Running outside the source project's tree ensures Quarto resolves this
    # directory (not the checkout's parent _quarto.yml) as the destination.
    documents = list(project.glob("*.qmd"))
    assert len(documents) == 1, f"expected one generated presentation, found {documents}"
    document = documents[0]

    generated_entries = {path.name for path in project.iterdir()}
    assert generated_entries == {"_extensions", document.name}, (
        f"unexpected repository infrastructure in generated project: {sorted(generated_entries)}"
    )
    run(["quarto", "render", document.name], cwd=project)
    assert_resources_exist(document.with_suffix(".html"))


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("FS_ISE_TEST_PUBLIC_INSTALL"), reason="run explicitly with make test-public-install")
def test_public_github_install_command(artifact_root):
    project = artifact_root / "public-install"
    project.mkdir()
    run(["quarto", "add", "fs-ise/quarto-template-presentation", "--no-prompt"], cwd=project)
    verify_install(project)
