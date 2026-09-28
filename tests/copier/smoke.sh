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
test ! -e "$project/copier.yml"
test ! -e "$project/copier-template"
test ! -e "$project/tests/copier"

(cd "$project" && quarto render)
test -f "$project/_site/presentation.html"
