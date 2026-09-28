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
grep -q 'class="fs-cover-logo"' "$html"
test "$(grep -c 'src="figures/fs_logo_blue.svg"' "$html")" -eq 2
grep -q 'class="menubar"' "$html"
grep -qi 'simplemenu' "$html"
for group in Introduction "Main idea" Conclusion; do
  grep -q "data-name=.$group." "$html"
done

# Resources are copied as one directory. In particular, Quarto must not flatten
# individual format resources into the project or rendered-site roots.
for asset in fs_logo_blue.svg title_background.png; do
  test -f "$project/figures/$asset"
  test -f "$project/_site/figures/$asset"
  test ! -e "$project/$asset"
  test ! -e "$project/_site/$asset"
done

# The slide-change handler uses a stable document class rather than relying on
# where a particular Reveal version applies its data-state class.
grep -q 'classList.toggle' "$html"
grep -q 'html.fs-cover-visible #fs-header' "$html"
grep -q 'section.fs-cover .fs-cover-logo' "$html"
grep -q -- '--fs-logo-width: 220px' "$html"
grep -q 'left: var(--fs-edge-inset)' "$html"
grep -q 'width: var(--fs-logo-width)' "$html"
grep -q 'width: 54%' "$html"
grep -q 'html.fs-cover-visible .slide-number' "$html"
grep -q 'html.fs-cover-visible #custom-slide-number' "$html"
grep -q 'html.fs-cover-visible .reveal .progress' "$html"
grep -q 'html.fs-cover-visible .menubar' "$html"
grep -Eq 'slideNumber: (true|"c/?t?")' "$html"

# Simplemenu must be a registered Reveal plugin, not merely a filter that emits
# dormant markup. Its shared extension defaults also keep generated projects
# and the repository example from drifting apart.
grep -q 'section-divs: true' "$project/_extensions/fs-ise-presentation/_extension.yml"
grep -A1 'revealjs-plugins:' "$project/_extensions/fs-ise-presentation/_extension.yml" | grep -q simplemenu
grep -q "<div class='menubar'><ul class='menu'></ul><div class='slide-number'></div></div>" \
  "$project/_extensions/fs-ise-presentation/_extension.yml"
! grep -q 'filters:' "$project/_quarto.yml"

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
