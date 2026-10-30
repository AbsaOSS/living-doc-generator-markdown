#!/usr/bin/env bash
#
# Copyright 2026 ABSA Group Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Render the three document types from given `living-doc-toolkit` outputs, outside any workflow: `technical-project`,
# `ui-test-catalog` and `coverage-matrix`, each through `main.py` as the action runs it, in a venv of its own built
# from `requirements.txt` alone; then re-read every input with `read_artifact`, check each document and run report
# against it, and print what ran and what came out.
# The configuration is `.env.local` (copy `.env.local.example`). See DEVELOPER.md § Local Integration Run.
#
#   ./local-integration.sh            # check, build the venv, render the three documents, check and report
#   ./local-integration.sh --check    # check Python, git, the configuration and the three inputs; nothing else
#
# Runs in bash 3.2 or later: Linux, macOS, or Git Bash on Windows.

set -euo pipefail

ME="local-integration.sh"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

ENV_FILE=".env.local"
# The script's own venv, never the developer's `.venv`: it holds `requirements.txt` and nothing else, so a runtime
# requirement missing from that file fails here as it would on a runner.
VENV=".venv-local-integration"

# Every setting `.env.local` may hold; a line with any other key is ignored and reported by its number only.
KEYS="TECHNICAL_PROJECT_INPUT UI_TEST_CATALOG_INPUT COVERAGE_MATRIX_INPUT OUT_DIR PYTHON"
REQUIRED="TECHNICAL_PROJECT_INPUT UI_TEST_CATALOG_INPUT COVERAGE_MATRIX_INPUT"

die() { printf '%s: %s\n' "$ME" "$*" >&2; exit 1; }
note() { printf '%s: %s\n' "$ME" "$*" >&2; }
is_key() { local key; for key in $KEYS; do [ "$key" = "$1" ] && return 0; done; return 1; }

# Echo a command, each argument quoted where the shell would need it, then run it.
run() {
  local line="+" arg
  for arg in "$@"; do
    case "$arg" in
      "" | *[!A-Za-z0-9_./:=@,+-]*) line="$line '${arg//\'/\'\\\'\'}'" ;;
      *) line="$line $arg" ;;
    esac
  done
  printf '%s\n' "$line" >&2
  "$@"
}

usage() {
  cat <<EOF
usage: ./$ME [--check]

Renders technical-project, ui-test-catalog and coverage-matrix from the three files configured in $ENV_FILE (copy
.env.local.example), checks each document against its input and prints a report.

  --check   verify Python, git, the configuration and the three inputs; create no venv, run nothing
EOF
}

CHECK_ONLY=false
case "${1-}" in
  "") ;;
  --check) CHECK_ONLY=true ;;
  -h | --help) usage; exit 0 ;;
  *) die "unknown argument '$1'; usage: ./$ME [--check]" ;;
esac
[ $# -le 1 ] || die "too many arguments; usage: ./$ME [--check]"

# The generator reads no credential: it reads one local file and calls no API. Drop the token names an operator's
# shell may carry, so nothing this script starts can print or write one.
unset GITHUB_TOKEN GH_TOKEN GH_ENTERPRISE_TOKEN GITHUB_ENTERPRISE_TOKEN
# Every action input comes from `.env.local`; none is inherited from the shell, where `main.py` would read it.
for name in $(compgen -e); do
  case "$name" in INPUT_*) unset "$name" ;; esac
done

# --- Configuration -------------------------------------------------------------------------------------------
# Read as data, never sourced: a sourced file runs whatever it holds and would put any token it carries into the
# environment of every command below.
for key in $KEYS; do printf -v "CFG_$key" '%s' ""; done
[ -f "$ENV_FILE" ] || die "$ENV_FILE not found; copy .env.local.example to $ENV_FILE"
line_no=0
while IFS= read -r line || [ -n "$line" ]; do
  line_no=$((line_no + 1))
  line="${line%$'\r'}"
  line="${line#"${line%%[![:space:]]*}"}"
  case "$line" in "" | "#"*) continue ;; esac
  line="${line#export }"
  key="${line%%=*}"
  # A line is reported by its number only, never by its text: it may be a pasted secret, and a base64 one ending in
  # `=` padding reads as a key.
  [[ "$line" == *=* && "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || die "$ENV_FILE:$line_no: not a KEY=value line"
  value="${line#*=}"
  value="${value%"${value##*[![:space:]]}"}"
  case "$value" in
    \"*\") value="${value#\"}"; value="${value%\"}" ;;
    \'*\') value="${value#\'}"; value="${value%\'}" ;;
  esac
  if is_key "$key"; then
    printf -v "CFG_$key" '%s' "$value"
  else
    note "$ENV_FILE:$line_no: ignored, not a setting of this script"
  fi
done < "$ENV_FILE"

for key in $REQUIRED; do
  var="CFG_$key"
  [ -n "${!var}" ] || die "$key is not set in $ENV_FILE"
done
CFG_OUT_DIR="${CFG_OUT_DIR:-./output}"

# A configured path: `~/` is the home directory, and a relative one resolves against this repository's root.
resolve() {
  case "$1" in
    "~/"*) printf '%s\n' "$HOME/${1#"~/"}" ;;
    /* | [A-Za-z]:[/\\]*) printf '%s\n' "$1" ;;
    *) printf '%s\n' "$ROOT/${1#./}" ;;
  esac
}

# An existing directory's absolute path in the form the venv's Python reads. Git Bash's `pwd -W` gives `C:/...`;
# elsewhere `-W` is an error, and plain `pwd` is already right.
native_dir() { (cd "$1" && { pwd -W 2>/dev/null || pwd; }); }

# --- Checks (also the whole of --check) ----------------------------------------------------------------------
# The interpreter: `PYTHON` when set, else `python3`, else `python` - the order `action.yml` resolves it in.
PY="${CFG_PYTHON:-$(command -v python3 || command -v python || true)}"
[ -n "$PY" ] || die "needs Python >= 3.10, and neither python3 nor python is on PATH; set PYTHON in $ENV_FILE"
PY_VERSION="$("$PY" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null | tr -d '\r')" \
  || die "needs Python >= 3.10, and '$PY' does not run; set PYTHON in $ENV_FILE"
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
  || die "needs Python >= 3.10, and '$PY' is $PY_VERSION; set PYTHON in $ENV_FILE"

# The header reads this repository's commit.
command -v git >/dev/null 2>&1 || die "git is not on PATH"

# A configured input file's absolute path, in the form the venv's Python reads.
input_file() {  # input_file KEY
  local var="CFG_$1" path
  path="$(resolve "${!var}")"
  [ -e "$path" ] || die "$1 not found: $path"
  [ -f "$path" ] || die "$1 is not a file: $path"
  printf '%s/%s\n' "$(native_dir "$(dirname "$path")")" "$(basename "$path")"
}
TECHNICAL_PROJECT_INPUT="$(input_file TECHNICAL_PROJECT_INPUT)"
UI_TEST_CATALOG_INPUT="$(input_file UI_TEST_CATALOG_INPUT)"
COVERAGE_MATRIX_INPUT="$(input_file COVERAGE_MATRIX_INPUT)"

OUT="$(resolve "$CFG_OUT_DIR")"
[ ! -e "$OUT" ] || [ -d "$OUT" ] || die "OUT_DIR is not a directory: $OUT"

# A run clears the generator's output directory before its first document, so an input inside it would be deleted
# before it is read. Compared as physical paths (`pwd -P`): a symlink, or a case-insensitive file system, can spell
# the same directory another way. A symlinked input is followed to its file, which the run would delete.
if [ -d "$OUT/generator-markdown" ]; then
  CLEARED="$(cd "$OUT/generator-markdown" && pwd -P)"
  for key in $REQUIRED; do
    var="CFG_$key"
    path="$(resolve "${!var}")"
    while [ -L "$path" ]; do
      target="$(readlink "$path")"
      case "$target" in
        /*) path="$target" ;;
        *) path="$(dirname "$path")/$target" ;;
      esac
    done
    case "$(cd "$(dirname "$path")" && pwd -P)/" in
      "$CLEARED"/*) die "$key is in the directory the run clears: $path; move it, or set another OUT_DIR" ;;
    esac
  done
fi

if [ "$CHECK_ONLY" = true ]; then
  printf '%s: check passed - Python %s (%s), git, %s, %s %s, %s %s, %s %s\n' "$ME" "$PY_VERSION" "$PY" "$ENV_FILE" \
    TECHNICAL_PROJECT_INPUT "$TECHNICAL_PROJECT_INPUT" UI_TEST_CATALOG_INPUT "$UI_TEST_CATALOG_INPUT" \
    COVERAGE_MATRIX_INPUT "$COVERAGE_MATRIX_INPUT"
  exit 0
fi

# --- The venv, as `action.yml` builds its own --------------------------------------------------------------------
# The install must land in the venv and nowhere else: these redirect pip's target, install into another interpreter,
# or prepend to `sys.path`. Unset, not set empty: pip reads its own variables as configuration values.
unset PIP_TARGET PIP_PREFIX PIP_USER PIP_ROOT PIP_PYTHON PYTHONPATH

venv_python() {
  if [ -x "$VENV/bin/python" ]; then
    printf '%s\n' "$VENV/bin/python"
  elif [ -x "$VENV/Scripts/python.exe" ]; then
    printf '%s\n' "$VENV/Scripts/python.exe"
  else
    return 1
  fi
}

# Reuse the venv only when the interpreter now configured built it, from the `requirements.txt` now in the tree.
# A requirement dropped from the file would otherwise stay installed, and the run would hide what it should show.
IDENTITY='import sys; print(sys.base_prefix, sys.version_info[:3])'
WANT="$("$PY" -c "$IDENTITY")"
HAVE=""
if VPY="$(venv_python)" && cmp -s requirements.txt "$VENV/requirements.txt"; then
  HAVE="$("$VPY" -c "$IDENTITY" 2>/dev/null || true)"
fi
if [ "$HAVE" != "$WANT" ]; then
  run rm -rf "$VENV"
  run "$PY" -m venv "$VENV" || die "'$PY -m venv' failed; install the venv module"
  VPY="$(venv_python)" || die "'$PY -m venv' made no interpreter under $VENV/bin or $VENV/Scripts"
fi
# From this repository's root, as the action installs from its own: `requirements.txt` holds pins only, and
# `generator_markdown` is imported from the checkout.
run "$VPY" -m pip install --disable-pip-version-check -r requirements.txt
# pip's own config files can still redirect the install while pip exits 0; the import `action.yml` checks, through
# the venv's interpreter and from this root, reports it here, where it happened.
run "$VPY" -E -c 'import living_doc_utilities, generator_markdown' \
  || die "the requirements did not land in $VENV; check pip's configuration for a 'target' or 'prefix' setting"
run cp requirements.txt "$VENV/requirements.txt"

# --- What runs ---------------------------------------------------------------------------------------------------
commit_of() {  # commit_of DIR: its HEAD, marked when tracked files differ from it
  local sha
  sha="$(git -C "$1" rev-parse HEAD 2>/dev/null)" || { echo "unknown (not a git checkout)"; return 0; }
  if [ -n "$(git -C "$1" status --porcelain --untracked-files=no 2>/dev/null)" ]; then
    sha="$sha (uncommitted changes)"
  fi
  printf '%s\n' "$sha"
}

UTILITIES_VERSION="$("$VPY" -E -c 'from importlib.metadata import version; print(version("living-doc-utilities"))' \
  | tr -d '\r')"
VENV_PY_VERSION="$("$VPY" -E -c 'import platform; print(platform.python_version())' | tr -d '\r')"
run mkdir -p "$OUT"
OUTPUT_DIR="$(native_dir "$OUT")/generator-markdown"
# A document type that fails stops the run, which would leave a later type's previous document beside it. Clear the
# generator's directory first, and nothing else under the output root, which may hold other components' output: the
# directory holds this run's files and nothing older.
run rm -rf "$OUT/generator-markdown"

cat <<EOF
== $ME
generator-markdown:       $(commit_of "$ROOT")
living-doc-utilities:     $UTILITIES_VERSION
python:                   $VENV_PY_VERSION ($VPY)
technical-project input:  $TECHNICAL_PROJECT_INPUT
ui-test-catalog input:    $UI_TEST_CATALOG_INPUT
coverage-matrix input:    $COVERAGE_MATRIX_INPUT
output:                   $OUTPUT_DIR
EOF

# `main.py` writes the `output-path` action output to `$GITHUB_OUTPUT`, which only a runner provides; without one it
# logs that it has none.
GITHUB_OUTPUT_FILE="$VENV/github-output.txt"

now_ms() { "$VPY" -E -c 'import time; print(int(time.time() * 1000))' | tr -d '\r'; }

# Render one document type as the action does - `main.py` with `-E`, its three inputs alone in its environment, no
# title, so the title is the input's - then check and report the document against the file it read.
generate() {  # generate DOCUMENT_TYPE INPUT
  local document_type="$1" input="$2" started finished status=0
  echo
  echo "== $document_type"
  : > "$GITHUB_OUTPUT_FILE"
  started="$(now_ms)"
  run env GITHUB_OUTPUT="$GITHUB_OUTPUT_FILE" INPUT_DOCUMENT_TYPE="$document_type" INPUT_SOURCE_PATH="$input" \
    INPUT_OUTPUT_PATH="$OUTPUT_DIR" "$VPY" -E main.py || status=$?
  finished="$(now_ms)"
  [ "$status" -eq 0 ] || die "the generator failed on '$document_type' (exit $status); its log is above"
  run "$VPY" -E -X utf8 -m tools.local_integration report "$document_type" "$input" "$OUTPUT_DIR" \
    "$((finished - started))" || die "the '$document_type' document failed its check"
}

generate technical-project "$TECHNICAL_PROJECT_INPUT"
generate ui-test-catalog "$UI_TEST_CATALOG_INPUT"
generate coverage-matrix "$COVERAGE_MATRIX_INPUT"

echo
echo "$ME: the three documents are written and valid under $OUTPUT_DIR"
