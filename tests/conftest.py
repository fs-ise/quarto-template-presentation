from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run(command, cwd=ROOT, env=None):
    result = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True)
    assert result.returncode == 0, (
        f"command failed ({result.returncode}): {' '.join(map(str, command))}\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    return result


@pytest.fixture(scope="session")
def artifact_root(tmp_path_factory):
    if os.environ.get("KEEP_TEST_PROJECTS"):
        root = ROOT / ".test-artifacts"
        shutil.rmtree(root, ignore_errors=True)
        root.mkdir()
        return root
    return tmp_path_factory.mktemp("presentation-tests")


@pytest.fixture(scope="session")
def canonical_html(artifact_root):
    project = artifact_root / "canonical"
    shutil.copytree(ROOT, project, ignore=shutil.ignore_patterns(".git", ".venv", ".tools", ".test-artifacts"))
    run(["quarto", "render", "template.qmd"], cwd=project)
    return project / "template.html"


@pytest.fixture(scope="session")
def copier_project(artifact_root):
    project = artifact_root / "copier-project"
    run([
        "copier", "copy", "--trust", "--defaults",
        "--data", "project_name=CI presentation",
        "--data", "presentation_title=A deliberately long presentation title used to verify wrapping",
        "--data", "author=CI", "--data", "subtitle=Generated noninteractively",
        "--data", f"extension_source={ROOT}", str(ROOT), str(project),
    ], cwd=artifact_root)
    return project


@pytest.fixture(scope="session")
def generated_html(copier_project):
    run(["quarto", "render"], cwd=copier_project)
    return copier_project / "_site" / "presentation.html"
