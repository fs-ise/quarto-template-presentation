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
