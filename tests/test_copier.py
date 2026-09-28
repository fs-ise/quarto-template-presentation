from conftest import ROOT
from helpers import assert_manifest, load_yaml


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
