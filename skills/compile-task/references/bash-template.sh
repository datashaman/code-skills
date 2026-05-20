#!/usr/bin/env bash
# NAME: example-name
# DESC: One-line description in present tense, no trailing period
# USAGE: example-name <required-arg> [--flag]
#
# Replace this header when generating. Keep NAME / DESC / USAGE — `cscript show`
# prints them above the source. The DESC line is what `cscript which` matches.

set -euo pipefail

usage() {
  cat <<EOF
Usage: $(basename "$0") <required-arg> [--flag]

Description here.

Args:
  required-arg    What it is

Flags:
  --flag          What it does
  -h, --help      Show this help
EOF
}

# Parse args explicitly. Never use `getopts` for long flags — write the loop.
flag=0
required=""
while (($#)); do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --flag)    flag=1; shift ;;
    --)        shift; break ;;
    -*)        echo "Unknown flag: $1" >&2; usage >&2; exit 2 ;;
    *)
      if [[ -z "$required" ]]; then required="$1"; shift
      else echo "Unexpected arg: $1" >&2; usage >&2; exit 2
      fi ;;
  esac
done

if [[ -z "$required" ]]; then
  usage >&2
  exit 2
fi

# --- implementation below ---
