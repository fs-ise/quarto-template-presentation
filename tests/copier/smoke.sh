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
html="$project/_site/presentation.html"
test -f "$html"
grep -q 'class="quarto-title-block fs-cover"' "$html"
grep -q 'data-state="fs-cover-active"' "$html"
grep -q 'data-background-image="figures/title_background.png"' "$html"
grep -q 'data-background-size="cover"' "$html"
grep -q 'data-background-position="center"' "$html"
grep -q 'src="figures/fs_logo_blue.svg"' "$html"
grep -q 'class="menubar"' "$html"

# Resources are copied as one directory. In particular, Quarto must not flatten
# individual format resources into the project or rendered-site roots.
for asset in fs_logo_blue.svg title_background.png; do
  test -f "$project/figures/$asset"
  test -f "$project/_site/figures/$asset"
  test ! -e "$project/$asset"
  test ! -e "$project/_site/$asset"
done

# Reveal's slide state suppresses both numbering implementations and the logo
# on the cover; the defaults remain present for every ordinary slide.
grep -q 'html.fs-cover-active #fs-header' "$html"
grep -q 'html.fs-cover-active .slide-number' "$html"
grep -q 'html.fs-cover-active #custom-slide-number' "$html"
grep -Eq 'slideNumber: (true|"c/?t?")' "$html"

# Check the referenced resources through an HTTP server, as preview/publishing
# accesses them, rather than treating a successful render as sufficient.
(
  cd "$project/_site"
  python -m http.server 8765 >"$output_dir/http.log" 2>&1 &
  server_pid=$!
  trap 'kill "$server_pid" 2>/dev/null || true' EXIT
  for _ in {1..20}; do
    curl --fail --silent --output /dev/null http://127.0.0.1:8765/presentation.html && break
    sleep 0.1
  done
  curl --fail --silent --output /dev/null http://127.0.0.1:8765/figures/fs_logo_blue.svg
  curl --fail --silent --output /dev/null http://127.0.0.1:8765/figures/title_background.png
)

# A document-level image replaces the extension default without changing the
# generated extension or adding a second copy of its assets.
cp "$project/_extensions/fs-ise-presentation/figures/title_background.png" "$project/figures/override.png"
python - "$project/presentation.qmd" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
source = path.read_text()
source = source.replace('author: "CI"\n', 'author:\n  - "Ada Lovelace"\n  - "Grace Hopper"\n', 1)
path.write_text(source.replace("date: today\n", "date: today\ncover-image: figures/override.png\n", 1))
PY
(cd "$project" && quarto render)
grep -q 'data-background-image="figures/override.png"' "$project/_site/presentation.html"
grep -q '>Ada Lovelace</p>' "$project/_site/presentation.html"
grep -q '>Grace Hopper</p>' "$project/_site/presentation.html"
test -f "$project/_site/figures/override.png"
