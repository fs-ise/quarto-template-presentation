#!/usr/bin/env bash
set -Eeuo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
# shellcheck source=../lib/assert.sh
source "$repo_root/tests/lib/assert.sh"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

verify_extension() {
  local project=$1 document=$2 html=$3
  local extension="$project/_extensions/fs-ise-presentation"
  local embedded="$extension/_extensions/simplemenu"

  require_file "$extension/_extension.yml"
  require_file "$embedded/_extension.yml"
  require_file "$embedded/simplemenu.js"
  require_file "$embedded/simplemenu.css"
  require_file "$embedded/LICENSE"
  require_absent "$project/_extensions/simplemenu"

  (cd "$project" && quarto render "$document")
  require_file "$html"
  # Simplemenu creates the footer from barhtml at runtime, so a menubar DOM
  # element need not occur in the unexecuted HTML. Check its configuration,
  # installed plugin, and emitted resources instead.
  require_grep "class=['\"]menubar['\"]" "$extension/_extension.yml"
  require_html_resource "$html" 'simplemenu[^/]*\.js$'
  require_html_resource "$html" 'simplemenu[^/]*\.css$'
  for group in Introduction Formatting Examples; do
    require_grep "data-name=['\"]$group['\"]" "$html"
  done
  require_grep 'slideNumber: (true|"c/?t?")' "$html"
  require_html_class "$html" fs-cover-logo
  require_html_attribute_count "$html" section data-background-image figures/title_background.png 1
  require_file "$project/figures/fs_logo_blue.svg"
  require_file "$project/figures/title_background.png"
}

# Regression: `quarto add fs-ise/quarto-template-presentation` must resolve
# Simplemenu in a project which has no other extensions installed.
add_project="$work/add"
mkdir -p "$add_project"
(cd "$add_project" && quarto add "$repo_root" --no-prompt)
cp "$repo_root/template.qmd" "$add_project/presentation.qmd"
verify_extension "$add_project" presentation.qmd "$add_project/presentation.html"

# Regression: `quarto use template fs-ise/quarto-template-presentation` must
# likewise be self-contained. A local checkout exercises the exact same Quarto
# installer while ensuring a pull-request workflow tests the proposed commit.
template_project="$work/template"
mkdir -p "$template_project"
(cd "$template_project" && quarto use template "$repo_root" --no-prompt)
require_file "$template_project/template.qmd"
require_absent "$template_project/copier.yml"
require_absent "$template_project/copier-template"
verify_extension "$template_project" template.qmd "$template_project/template.html"

printf 'All quarto add and quarto use template smoke checks passed.\n'
