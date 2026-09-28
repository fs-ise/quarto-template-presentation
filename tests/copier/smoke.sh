#!/usr/bin/env bash
set -Eeuo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
# shellcheck source=../lib/assert.sh
source "$repo_root/tests/lib/assert.sh"
output_dir=$(mktemp -d)
trap 'rm -rf "$output_dir"' EXIT

copier copy --trust --defaults \
  --data project_name="CI presentation" \
  --data presentation_title="A deliberately long presentation title that demonstrates clean wrapping on the cover page" \
  --data author="CI" \
  --data subtitle="Generated noninteractively" \
  "$repo_root" "$output_dir/project"

project="$output_dir/project"
for path in presentation.qmd _quarto.yml README.md Makefile .gitignore .copier-answers.yml; do
  require_file "$project/$path"
done
require_dir "$project/figures"
require_file "$project/figures/README.md"

# Copier excludes .gitkeep files by default, so the real README above keeps the
# figures directory in a fresh project. Parse the answers as YAML so the test is
# independent of serializer quoting and line-wrapping choices. The answers must
# retain both the user input and source revision required by `copier update`.
python - "$project/.copier-answers.yml" <<'PY'
from pathlib import Path
import sys

import yaml

answers_path = Path(sys.argv[1])
answers = yaml.safe_load(answers_path.read_text(encoding="utf-8"))
if not isinstance(answers, dict):
    raise SystemExit(f"Expected a YAML mapping in {answers_path}, got {type(answers).__name__}")

expected = {
    "project_name": "CI presentation",
    "presentation_title": (
        "A deliberately long presentation title that demonstrates clean wrapping on the cover page"
    ),
    "author": "CI",
    "subtitle": "Generated noninteractively",
}
for key, expected_value in expected.items():
    actual_value = answers.get(key)
    if actual_value != expected_value:
        raise SystemExit(
            f"Unexpected {key} in {answers_path}: expected {expected_value!r}, got {actual_value!r}"
        )

for key in ("_src_path", "_commit"):
    value = answers.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(f"Expected non-empty string {key} in {answers_path}, got {value!r}")
PY

require_file "$project/_extensions/fs-ise-presentation/_extension.yml"
require_file "$project/_extensions/fs-ise-presentation/title-slide.html"
require_file "$project/_extensions/fs-ise-presentation/figures/title_background.png"
require_file "$project/_extensions/fs-ise-presentation/figures/fs_logo_blue.svg"
require_file "$project/_extensions/fs-ise-presentation/_extensions/simplemenu/_extension.yml"
require_file "$project/_extensions/fs-ise-presentation/_extensions/simplemenu/LICENSE"
require_absent "$project/_extensions/simplemenu"
require_not_grep 'quarto-simplemenu' "$project/Makefile"
for extension in qrcode iconify; do
  require_file "$project/_extensions/$extension/_extension.yml"
done
require_absent "$project/copier.yml"
require_absent "$project/copier-template"
require_absent "$project/tests/copier"

(cd "$project" && quarto render)
html="$project/_site/presentation.html"
require_file "$html"
require_html_class "$html" quarto-title-block
require_html_class "$html" fs-cover
require_html_attribute_count "$html" section data-state fs-cover-active 1
require_html_attribute_count "$html" section data-background-image figures/title_background.png 1
require_html_attribute_count "$html" section data-background-size cover 1
require_html_attribute_count "$html" section data-background-position center 1
require_html_class "$html" fs-cover-logo
require_html_attribute_count "$html" img src figures/fs_logo_blue.svg 2
require_grep "class=['\"]menubar['\"]" "$project/_extensions/fs-ise-presentation/_extension.yml"
require_html_resource "$html" 'simplemenu[^/]*\.js$'
require_html_resource "$html" 'simplemenu[^/]*\.css$'
for group in Introduction "Main idea" Conclusion; do
  require_html_attribute_count "$html" section data-name "$group" 1
done

# Resources are copied as one directory. In particular, Quarto must not flatten
# individual format resources into the project or rendered-site roots.
for asset in fs_logo_blue.svg title_background.png; do
  require_file "$project/figures/$asset"
  require_file "$project/_site/figures/$asset"
  require_absent "$project/$asset"
  require_absent "$project/_site/$asset"
done

# The slide-change handler uses a stable document class rather than relying on
# where a particular Reveal version applies its data-state class.
require_grep 'classList\.toggle' "$html"
require_css_text "$project/_site" 'html.fs-cover-visible #fs-header'
require_css_text "$project/_site" 'section.fs-cover .fs-cover-logo'
require_css_text "$project/_site" '--fs-logo-width:190px'
require_css_text "$project/_site" '--fs-logo-clearance:235px'
require_css_text "$project/_site" 'left:var(--fs-edge-inset)'
require_css_text "$project/_site" 'width:var(--fs-logo-width)'
require_css_text "$project/_site" 'padding-right:var(--fs-logo-clearance)!important'
require_css_text "$project/_site" 'pointer-events:none'
require_grep 'currentSlide.appendChild(logo)' "$html"
require_css_text "$project/_site" 'width:54%'
require_css_text "$project/_site" 'html.fs-cover-visible .slide-number'
require_css_text "$project/_site" 'html.fs-cover-visible #custom-slide-number'
require_css_text "$project/_site" 'html.fs-cover-visible .reveal .progress'
require_css_text "$project/_site" 'html.fs-cover-visible .menubar'
require_reveal_slide_numbers "$html"

# Simplemenu must be a registered Reveal plugin, not merely a filter that emits
# dormant markup. Its shared extension defaults also keep generated projects
# and the repository example from drifting apart.
require_grep '^section-divs: true$' "$project/_extensions/fs-ise-presentation/_extension.yml"
require_grep '^revealjs-plugins:' "$project/_extensions/fs-ise-presentation/_extension.yml"
require_grep '^[[:space:]]*- simplemenu$' "$project/_extensions/fs-ise-presentation/_extension.yml"
require_grep "<div class='menubar'><ul class='menu'></ul><div class='slide-number'></div></div>" \
  "$project/_extensions/fs-ise-presentation/_extension.yml"
require_not_grep '^[[:space:]]*filters:' "$project/_quarto.yml"

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
require_html_attribute_count "$project/_site/presentation.html" section data-background-image figures/override.png 1
require_grep '>Ada Lovelace</p>' "$project/_site/presentation.html"
require_grep '>Grace Hopper</p>' "$project/_site/presentation.html"
require_file "$project/_site/figures/override.png"
