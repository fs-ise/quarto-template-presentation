from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS = ROOT / ".test-artifacts"


def run(command, cwd=ROOT, env=None):
    result = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True)
    assert result.returncode == 0, (
        f"command failed ({result.returncode}): {' '.join(map(str, command))}\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    return result


@pytest.fixture(scope="session")
def artifact_root(tmp_path_factory):
    # Keeping generated Quarto projects below this repository makes Quarto walk
    # up to the checkout's _quarto.yml and silently use the wrong project root.
    # Always work in pytest's external temporary directory instead.
    return tmp_path_factory.mktemp("presentation-tests")


def pytest_sessionstart(session):
    shutil.rmtree(DIAGNOSTICS, ignore_errors=True)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "teardown" or not report.failed or not os.environ.get("KEEP_TEST_PROJECTS"):
        return
    # Preserve only failed integration projects; successful runs stay concise.
    destination = DIAGNOSTICS / "projects"
    destination.mkdir(parents=True, exist_ok=True)
    sources = []
    temporary_root = item.funcargs.get("artifact_root")
    if temporary_root:
        sources.extend(path for path in Path(temporary_root).iterdir() if path.is_dir())
    for source in sources:
        target = destination / source.name
        if source.exists() and not target.exists():
            shutil.copytree(source, target, ignore=shutil.ignore_patterns(".git", ".venv"))


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
    result = run(["quarto", "render", "presentation.qmd"], cwd=copier_project)
    html = copier_project / "_site" / "presentation.html"
    assert html.is_file(), (
        f"Quarto did not create its configured output {html}\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}\n"
        f"Generated files: {[str(path.relative_to(copier_project)) for path in copier_project.rglob('*') if path.is_file()]}"
    )
    return html
