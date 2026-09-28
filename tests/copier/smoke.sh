#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
output_dir=$(mktemp -d)
trap 'rm -rf "$output_dir"' EXIT

copier copy --trust --defaults \
  --data project_name="CI presentation" \
  --data presentation_title="Copier smoke test" \
  --data author="CI" \
  --data subtitle="Generated noninteractively" \
  "$repo_root" "$output_dir/project"

project="$output_dir/project"
for path in presentation.qmd _quarto.yml README.md Makefile figures .gitignore .copier-answers.yml; do
  test -e "$project/$path"
done

test -f "$project/_extensions/fs-ise-presentation/_extension.yml"
test -f "$project/_extensions/fs-ise-presentation/title-slide.html"
test -f "$project/_extensions/fs-ise-presentation/images/title_background.png"
for extension in simplemenu qrcode iconify; do
  test -f "$project/_extensions/$extension/_extension.yml"
done
test ! -e "$project/copier.yml"
test ! -e "$project/copier-template"
test ! -e "$project/tests/copier"

(cd "$project" && quarto render)
test -f "$project/_site/presentation.html"
grep -q 'class="quarto-title-block fs-cover"' "$project/_site/presentation.html"
grep -q 'src="images/title_background.png"' "$project/_site/presentation.html"
grep -q 'class="menubar"' "$project/_site/presentation.html"
test -f "$project/_site/images/title_background.png"

# A document-level image replaces the extension default without changing the
# generated extension or adding a second copy of its assets.
cp "$project/_extensions/fs-ise-presentation/images/title_background.png" "$project/override.png"
python - "$project/presentation.qmd" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
source = path.read_text()
path.write_text(source.replace("date: today\n", "date: today\ncover-image: override.png\n", 1))
PY
(cd "$project" && quarto render)
grep -q 'src="override.png"' "$project/_site/presentation.html"
test -f "$project/_site/override.png"
