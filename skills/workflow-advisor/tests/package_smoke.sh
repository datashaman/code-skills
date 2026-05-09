#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP" "$ROOT/scripts/workflow_advisor.egg-info"' EXIT

python3 -m venv "$TMP/venv"
"$TMP/venv/bin/python" -m pip install -q -e "$ROOT"
"$TMP/venv/bin/workflow-advisor" --help >/dev/null
"$TMP/venv/bin/workflow-advisor" interview --write-default --repo example/pkg --output "$TMP/config.yml" >/dev/null
"$TMP/venv/bin/workflow-advisor" --config "$TMP/config.yml" profiles list >/dev/null

echo "package smoke OK"
