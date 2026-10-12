import os

import pytest

from conftest import ROOT, run
from helpers import assert_manifest, load_yaml


pytestmark = pytest.mark.integration


def find_fs_extension(project):
    matches = [path for path in (project / "_extensions").rglob("_extension.yml") if load_yaml(path).get("title") == "fs-ise-presentation"]
    assert len(matches) == 1, f"expected one installed FS extension, found {matches}"
    return matches[0].parent


def test_copier_project_and_answers(copier_project):
    for filename in ("presentation.qmd", "_quarto.yml", "README.md", "Makefile", ".gitignore", ".copier-answers.yml"):
        assert (copier_project / filename).is_file(), f"Copier omitted {filename}"
    assert (copier_project / "figures/README.md").is_file()
    answers = load_yaml(copier_project / ".copier-answers.yml")
    assert answers["project_name"] == "CI presentation"
    assert answers["author"] == "CI"
    assert answers["subtitle"] == "Generated noninteractively"
    assert answers.get("_src_path"), "answers must retain Copier source path"
    assert answers.get("_commit"), "answers must retain Copier source revision"

    extension = find_fs_extension(copier_project)
    assert_manifest(extension / "_extension.yml")
    checkout = ROOT / "_extensions/fs-ise-presentation"
    installed_files = {path.relative_to(extension) for path in extension.rglob("*") if path.is_file()}
    checkout_files = {path.relative_to(checkout) for path in checkout.rglob("*") if path.is_file()}
    assert installed_files == checkout_files, "installed FS extension does not have the checkout's exact file set"
    for filename in checkout_files:
        assert (extension / filename).read_bytes() == (checkout / filename).read_bytes(), (
            f"Copier installed a different source revision of {filename}"
        )
    assert (extension / "_extensions/simplemenu/simplemenu.js").is_file()
    assert not (copier_project / "_extensions/simplemenu").exists()
    assert not (copier_project / "copier.yml").exists()
    assert not (copier_project / "copier-template").exists()
    presentation = (copier_project / "presentation.qmd").read_text(encoding="utf-8")
    assert "{{< qrcode https://example.com >}}" in presentation
    assert "data-stack-name" in presentation


def test_copier_post_generation_installs_extensions(copier_project):
    extensions = copier_project / "_extensions"
    for extension in (
        "fs-ise-presentation",
        "jmbuhr/qrcode",
        "mcanouil/iconify",
    ):
        installed = extensions / extension
        assert installed.is_dir(), f"Copier post-generation task did not install {extension}"
        assert list(installed.rglob("_extension.yml")), f"{extension} has no extension manifest"
    assert not (copier_project / copier_project.name).exists(), "Copier created a duplicated project directory"


def test_copier_initializes_and_commits_git_repository(copier_project):
    repository = run(["git", "rev-parse", "--is-inside-work-tree"], cwd=copier_project)
    assert repository.stdout.strip() == "true"

    commit = run(["git", "log", "-1", "--format=%s"], cwd=copier_project)
    assert commit.stdout.strip() == "Initial commit"

    tracked_files = run(["git", "ls-tree", "-r", "--name-only", "HEAD"], cwd=copier_project)
    assert ".copier-answers.yml" in tracked_files.stdout.splitlines()
    assert "presentation.qmd" in tracked_files.stdout.splitlines()

    status = run(["git", "status", "--porcelain"], cwd=copier_project)
    assert not status.stdout.strip(), "generated project should be clean after its initial commit"


def test_copier_skips_git_setup_inside_existing_repository(artifact_root):
    parent = artifact_root / "parent-repository"
    parent.mkdir()
    (parent / "README.md").write_text("Existing repository\n", encoding="utf-8")
    env = os.environ.copy()
    env.update({
        "GIT_AUTHOR_NAME": "Copier Test",
        "GIT_AUTHOR_EMAIL": "copier-test@example.invalid",
        "GIT_COMMITTER_NAME": "Copier Test",
        "GIT_COMMITTER_EMAIL": "copier-test@example.invalid",
    })
    run(["git", "init"], cwd=parent, env=env)
    run(["git", "add", "README.md"], cwd=parent, env=env)
    run(["git", "commit", "-m", "Parent commit"], cwd=parent, env=env)
    original_commit = run(["git", "rev-parse", "HEAD"], cwd=parent).stdout.strip()

    project = parent / "generated-project"
    run([
        "copier", "copy", "--trust", "--defaults",
        "--data", "project_name=CI presentation",
        "--data", "presentation_title=Generated inside an existing repository",
        "--data", "author=CI", "--data", "subtitle=",
        "--data", f"extension_source={ROOT}", str(ROOT), str(project),
    ], cwd=artifact_root, env=env)

    assert not (project / ".git").exists(), "Copier created a nested Git repository"
    root = run(["git", "rev-parse", "--show-toplevel"], cwd=project)
    assert root.stdout.strip() == str(parent)
    commit = run(["git", "rev-parse", "HEAD"], cwd=parent)
    assert commit.stdout.strip() == original_commit, "Copier committed changes to the enclosing repository"
    status = run(["git", "status", "--porcelain"], cwd=parent)
    assert status.stdout.strip() == "?? generated-project/"
