import os

import pytest

from conftest import ROOT, run
from helpers import assert_manifest, load_yaml


pytestmark = pytest.mark.integration


def find_fs_extension(project):
    matches = [path for path in (project / "_extensions").rglob("_extension.yml") if load_yaml(path).get("title") == "fs-ise-presentation"]
    assert len(matches) == 1, f"expected one installed FS extension, found {matches}"
    return matches[0].parent


def copy_with_defaults(destination, cwd, answers=()):
    command = ["copier", "copy", "--trust", "--defaults", "--skip-tasks"]
    for answer in (*answers, f"extension_source={ROOT}"):
        command.extend(("--data", answer))
    command.extend((str(ROOT), str(destination)))
    run(command, cwd=cwd)


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
    assert '## Welcome {data-name="Introduction"}' in presentation
    assert '## Your main idea {data-name="Main idea"}' in presentation
    assert '## Let’s discuss {data-name="Conclusion"}' in presentation
    assert presentation.count('data-fragment-index="0"') == 2
    assert ".closing-thanks" in presentation
    assert presentation.count(":::: {.columns}") == 2
    assert presentation.count('::: {.column .presenter-card width="33%"}') == 3
    assert '::: {.column .center-column width="35%"}' in presentation
    assert ":::: {.fragment data-fragment-index=\"0\"}" in presentation
    assert ".research-card" not in presentation
    assert "**Presenter One**" in presentation
    assert "**Thank you — we look forward to the discussion.**" in presentation
    assert "> Research creates impact when credible evidence leads to a clear next step." in presentation
    assert "### Explore the research" in presentation
    assert "### [Explore the research](https://example.com)" not in presentation
    assert "[name@institution.edu](mailto:name@institution.edu)" in presentation
    assert "[github.com/presenter-one](https://github.com/presenter-one)" in presentation
    assert "LinkedIn" not in presentation
    assert "[Paper]" not in presentation
    assert "[Slides]" not in presentation
    assert "fs-qr-slide" not in presentation
    assert "fs-discussion-prompts" not in presentation
    assert "data-stack-name" not in presentation


def test_copier_uses_paper_qmd_front_matter_defaults(artifact_root):
    paper_repo = artifact_root / "paper-repository"
    paper_repo.mkdir()
    (paper_repo / "paper.qmd").write_text(
        "\n".join([
            "---",
            'title: "Paper title for the conference talk"',
            "author:",
            '  - name: "Ada Lovelace"',
            "  - name:",
            '      given: "Grace"',
            '      family: "Hopper"',
            "---",
            "",
            "Paper content.",
            "",
        ]),
        encoding="utf-8",
    )

    project = paper_repo / "conference-presentation"
    copy_with_defaults(project, cwd=paper_repo)

    answers = load_yaml(project / ".copier-answers.yml")
    assert answers["project_name"] == "Paper title for the conference talk"
    assert answers["presentation_title"] == "Paper title for the conference talk"
    assert answers["author"] == "Ada Lovelace, Grace Hopper"
    presentation = (project / "presentation.qmd").read_text(encoding="utf-8")
    assert 'title: "Paper title for the conference talk"' in presentation
    assert 'author: "Ada Lovelace, Grace Hopper"' in presentation


def test_copier_uses_paper_md_front_matter_defaults(artifact_root):
    paper_repo = artifact_root / "markdown-paper-repository"
    paper_repo.mkdir()
    (paper_repo / "paper.md").write_text(
        "\n".join([
            "---",
            'author: "Geßler, Anna and Schnickmann, Karl and Wagner, Gerit"',
            "title: 'Advancing Literature Review Automation through API-Based Searches: Design of an Independent Emulator'",
            "---",
            "",
            "Paper content.",
            "",
        ]),
        encoding="utf-8",
    )

    project = paper_repo / "conference-presentation"
    copy_with_defaults(project, cwd=paper_repo)

    answers = load_yaml(project / ".copier-answers.yml")
    assert answers["project_name"] == "Advancing Literature Review Automation through API-Based Searches: Design of an Independent Emulator"
    assert answers["presentation_title"] == answers["project_name"]
    assert answers["author"] == "Geßler, Anna and Schnickmann, Karl and Wagner, Gerit"


def test_paper_qmd_takes_precedence_over_paper_md(artifact_root):
    paper_repo = artifact_root / "paper-with-both-formats"
    paper_repo.mkdir()
    (paper_repo / "paper.qmd").write_text(
        "\n".join(["---", 'title: "QMD title"', 'author: "QMD author"', "---", ""]),
        encoding="utf-8",
    )
    (paper_repo / "paper.md").write_text(
        "\n".join(["---", 'title: "Markdown title"', 'author: "Markdown author"', "---", ""]),
        encoding="utf-8",
    )

    project = paper_repo / "conference-presentation"
    copy_with_defaults(project, cwd=paper_repo)

    answers = load_yaml(project / ".copier-answers.yml")
    assert answers["project_name"] == "QMD title"
    assert answers["author"] == "QMD author"


def test_copier_paper_defaults_fall_back_and_remain_overridable(artifact_root):
    plain_repo = artifact_root / "plain-repository"
    plain_repo.mkdir()
    fallback_project = plain_repo / "conference-presentation"
    copy_with_defaults(fallback_project, cwd=plain_repo)
    fallback_answers = load_yaml(fallback_project / ".copier-answers.yml")
    assert fallback_answers["project_name"] == "Presentation title"
    assert fallback_answers["presentation_title"] == "Presentation title"
    assert fallback_answers["author"] == "Presenter Name"

    partial_repo = artifact_root / "partial-paper-repository"
    partial_repo.mkdir()
    (partial_repo / "paper.qmd").write_text(
        "\n".join(["---", 'title: "Title without author"', "---", ""]),
        encoding="utf-8",
    )
    partial_project = partial_repo / "conference-presentation"
    copy_with_defaults(partial_project, cwd=partial_repo)
    partial_answers = load_yaml(partial_project / ".copier-answers.yml")
    assert partial_answers["project_name"] == "Title without author"
    assert partial_answers["author"] == "Presenter Name"

    paper_repo = artifact_root / "paper-with-overrides"
    paper_repo.mkdir()
    (paper_repo / "paper.qmd").write_text(
        "\n".join(["---", 'title: "Paper title"', 'author: "Paper author"', "---", ""]),
        encoding="utf-8",
    )
    overridden_project = paper_repo / "conference-presentation"
    copy_with_defaults(
        overridden_project,
        cwd=paper_repo,
        answers=(
            "project_name=Conference project",
            "presentation_title=Conference talk title",
            "author=Conference presenter",
        ),
    )
    overridden_answers = load_yaml(overridden_project / ".copier-answers.yml")
    assert overridden_answers["project_name"] == "Conference project"
    assert overridden_answers["presentation_title"] == "Conference talk title"
    assert overridden_answers["author"] == "Conference presenter"


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
    rendered_assets = {
        "?? figures/fs_logo_blue.svg",
        "?? figures/fs_logo_blue_content.svg",
        "?? figures/title_background.png",
    }
    assert set(status.stdout.splitlines()) <= rendered_assets, (
        "only Quarto-copied extension assets may appear after rendering the generated project"
    )


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
