#!/usr/bin/env bash

# Shell test helpers that report the failed command and the artifact it was
# looking for. `set -e` alone makes CI terminate with an unhelpful status 1.
set -Eeuo pipefail
trap 'status=$?; printf "ERROR: %s:%s: command failed (%s): %s\n" "${BASH_SOURCE[0]}" "${LINENO}" "$status" "$BASH_COMMAND" >&2; exit "$status"' ERR

require_file() {
  [[ -f "$1" ]] || { printf 'ERROR: expected file does not exist: %s\n' "$1" >&2; return 1; }
}

require_dir() {
  [[ -d "$1" ]] || { printf 'ERROR: expected directory does not exist: %s\n' "$1" >&2; return 1; }
}

require_absent() {
  [[ ! -e "$1" ]] || { printf 'ERROR: path should not exist: %s\n' "$1" >&2; return 1; }
}

require_grep() {
  local pattern=$1 file=$2
  grep -Eq -- "$pattern" "$file" || {
    printf 'ERROR: pattern %q was not found in %s\n' "$pattern" "$file" >&2
    return 1
  }
}

require_not_grep() {
  local pattern=$1 file=$2
  if grep -Eq -- "$pattern" "$file"; then
    printf 'ERROR: unexpected pattern %q was found in %s\n' "$pattern" "$file" >&2
    return 1
  fi
}

# Assert against parsed HTML rather than its serializer's choice of quote style.
require_html_attribute_count() {
  local file=$1 tag=$2 attribute=$3 value=$4 expected=$5
  python - "$file" "$tag" "$attribute" "$value" "$expected" <<'PY'
from html.parser import HTMLParser
from pathlib import Path
import sys

file, wanted_tag, wanted_attribute, wanted_value, expected = sys.argv[1:]

class Counter(HTMLParser):
    def __init__(self):
        super().__init__()
        self.count = 0

    def handle_starttag(self, tag, attrs):
        if tag == wanted_tag and dict(attrs).get(wanted_attribute) == wanted_value:
            self.count += 1

parser = Counter()
parser.feed(Path(file).read_text(encoding="utf-8"))
if parser.count != int(expected):
    raise SystemExit(
        f"ERROR: expected {expected} <{wanted_tag}> element(s) with "
        f"{wanted_attribute}={wanted_value!r} in {file}, found {parser.count}"
    )
PY
}

require_html_class() {
  local file=$1 class_name=$2
  python - "$file" "$class_name" <<'PY'
from html.parser import HTMLParser
from pathlib import Path
import sys

file, wanted = sys.argv[1:]

class Classes(HTMLParser):
    def __init__(self):
        super().__init__()
        self.matches = 0

    def handle_starttag(self, _tag, attrs):
        if wanted in dict(attrs).get("class", "").split():
            self.matches += 1

parser = Classes()
parser.feed(Path(file).read_text(encoding="utf-8"))
if not parser.matches:
    raise SystemExit(f"ERROR: HTML class {wanted!r} was not found in {file}")
PY
}

# Check the value that Quarto passes to Reveal, while allowing Quarto to emit
# either JavaScript object-literal keys or JSON-style quoted keys.  This is a
# semantic assertion: all Reveal slide-number modes are accepted, but false or
# a missing setting is not.
require_reveal_slide_numbers() {
  local file=$1
  python - "$file" <<'PY'
from html.parser import HTMLParser
from pathlib import Path
import re
import sys

file = sys.argv[1]

class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_script = False
        self.scripts = []
        self.current = []

    def handle_starttag(self, tag, _attrs):
        if tag == "script":
            self.in_script = True
            self.current = []

    def handle_data(self, data):
        if self.in_script:
            self.current.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.in_script:
            self.scripts.append("".join(self.current))
            self.in_script = False

parser = Scripts()
parser.feed(Path(file).read_text(encoding="utf-8"))
initializers = [script for script in parser.scripts if ".initialize(" in script]
key = r"(?:slideNumber|['\"]slideNumber['\"])"
value = r"(true|['\"](?:c|h|v|c/t|h/v|c\\.t|h\\.v)['\"])"
matches = [
    match.group(1).strip("'\"")
    for script in initializers
    for match in re.finditer(rf"{key}\s*:\s*{value}", script)
]
if not matches:
    raise SystemExit(
        f"ERROR: Reveal is not initialized with enabled slide numbering in {file}"
    )
PY
}

# Verify that an HTML document references a matching local resource and that
# the referenced file was actually emitted beside it.
require_html_resource() {
  local file=$1 pattern=$2
  python - "$file" "$pattern" <<'PY'
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
import re
import sys

file, pattern = sys.argv[1:]
document = Path(file)

class Resources(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []

    def handle_starttag(self, _tag, attrs):
        values = dict(attrs)
        for attribute in ("src", "href"):
            value = values.get(attribute, "")
            parsed = urlsplit(value)
            if value and not parsed.scheme and not parsed.netloc and not value.startswith(("#", "//")):
                self.paths.append(unquote(parsed.path))

parser = Resources()
parser.feed(document.read_text(encoding="utf-8"))
matches = [path for path in parser.paths if re.search(pattern, path, re.IGNORECASE)]
existing = [path for path in matches if (document.parent / path).is_file()]
if not existing:
    detail = ", ".join(matches) if matches else "no matching references"
    raise SystemExit(
        f"ERROR: {file} has no existing local resource matching /{pattern}/ ({detail})"
    )
PY
}

# Compilers may minify declarations or freely change insignificant whitespace.
require_css_text() {
  local directory=$1 expected=$2
  python - "$directory" "$expected" <<'PY'
from pathlib import Path
import re
import sys

directory, expected = Path(sys.argv[1]), sys.argv[2]
files = sorted(directory.rglob("*.css"))
compact = re.sub(r"\s+", "", "\n".join(
    path.read_text(encoding="utf-8", errors="replace") for path in files
))
needle = re.sub(r"\s+", "", expected)
if needle not in compact:
    raise SystemExit(
        f"ERROR: CSS text {expected!r} was not found in {len(files)} stylesheet(s) under {directory}"
    )
PY
}

# Styling contract shared by every rendered FS-ISE presentation. Keep these
# assertions in one place so generated projects cannot silently drift from the
# repository example checked by the render workflow.
require_presentation_style() {
  local project=$1 html=$2
  local extension=${3:-"$project/_extensions/fs-ise-presentation"}
  local css_directory="${html%.html}_files"

  require_html_class "$html" quarto-title-block
  require_html_class "$html" fs-cover
  require_html_class "$html" fs-cover-logo
  require_html_attribute_count "$html" section data-state fs-cover-active 1
  require_html_attribute_count "$html" section data-background-image figures/title_background.png 1
  require_html_attribute_count "$html" section data-background-size cover 1
  require_html_attribute_count "$html" section data-background-position center 1
  require_html_attribute_count "$html" img src figures/fs_logo_blue.svg 2

  require_grep "class=['\"]menubar['\"]" "$extension/_extension.yml"
  require_html_resource "$html" 'simplemenu[^/]*\.js$'
  require_html_resource "$html" 'simplemenu[^/]*\.css$'
  require_reveal_slide_numbers "$html"

  require_css_text "$css_directory" '--fs-logo-width:190px'
  require_css_text "$css_directory" '--fs-logo-clearance:235px'
  require_css_text "$css_directory" 'left:var(--fs-edge-inset)'
  require_css_text "$css_directory" 'right:var(--fs-edge-inset)'
  require_css_text "$css_directory" 'left:auto'
  require_css_text "$css_directory" 'width:var(--fs-logo-width)'
  require_css_text "$css_directory" 'padding-right:var(--fs-logo-clearance)!important'
  require_css_text "$css_directory" 'background:none'
  require_css_text "$css_directory" 'border:0'
  require_css_text "$css_directory" 'box-shadow:none'
  require_css_text "$css_directory" 'pointer-events:none'
  require_css_text "$css_directory" 'width:54%'
  require_css_text "$css_directory" 'html.fs-cover-visible .slide-number'
  require_css_text "$css_directory" 'html.fs-cover-visible #custom-slide-number'
  require_css_text "$css_directory" 'html.fs-cover-visible .reveal .progress'
  require_css_text "$css_directory" 'html.fs-cover-visible .menubar'

  require_file "$project/figures/fs_logo_blue.svg"
  require_file "$project/figures/title_background.png"
}
