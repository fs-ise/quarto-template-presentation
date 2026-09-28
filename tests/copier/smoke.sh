#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
output_dir=$(mktemp -d)
trap 'rm -rf "$output_dir"' EXIT

copier copy --trust --defaults \
  --data project_name="CI presentation" \
  --data presentation_title="A deliberately long presentation title that demonstrates clean wrapping on the cover page" \
  --data author="CI" \
  --data subtitle="Generated noninteractively" \
  "$repo_root" "$output_dir/project"

project="$output_dir/project"
for path in presentation.qmd _quarto.yml README.md Makefile figures .gitignore .copier-answers.yml; do
  test -e "$project/$path"
done

test -f "$project/_extensions/fs-ise-presentation/_extension.yml"
test -f "$project/_extensions/fs-ise-presentation/title-slide.html"
test -f "$project/_extensions/fs-ise-presentation/figures/title_background.png"
test -f "$project/_extensions/fs-ise-presentation/figures/fs_logo_blue.svg"
for extension in simplemenu qrcode iconify; do
  test -f "$project/_extensions/$extension/_extension.yml"
done
test ! -e "$project/copier.yml"
test ! -e "$project/copier-template"
test ! -e "$project/tests/copier"

(cd "$project" && quarto render)
test -f "$project/_site/presentation.html"
grep -q 'class="quarto-title-block fs-cover"' "$project/_site/presentation.html"
grep -q 'src="figures/title_background.png"' "$project/_site/presentation.html"
grep -q 'class="menubar"' "$project/_site/presentation.html"
test -f "$project/_site/figures/title_background.png"

# A document-level image replaces the extension default without changing the
# generated extension or adding a second copy of its assets.
cp "$project/_extensions/fs-ise-presentation/figures/title_background.png" "$project/override.png"
python - "$project/presentation.qmd" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
source = path.read_text()
source = source.replace('author: "CI"\n', 'author:\n  - "Ada Lovelace"\n  - "Grace Hopper"\n', 1)
path.write_text(source.replace("date: today\n", "date: today\ncover-image: override.png\n", 1))
PY
(cd "$project" && quarto render)
grep -q 'src="override.png"' "$project/_site/presentation.html"
grep -q '>Ada Lovelace</p>' "$project/_site/presentation.html"
grep -q '>Grace Hopper</p>' "$project/_site/presentation.html"
test -f "$project/_site/override.png"
