#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="$ROOT/tests/fixtures/minimal-repo/.workflow/config.yml"
CLI="$ROOT/scripts/cli.py"

python3 "$CLI" --config "$CONFIG" --help >/dev/null
python3 "$CLI" --config "$CONFIG" status >/dev/null
python3 "$CLI" --config "$CONFIG" status pr-42 >/dev/null
python3 "$CLI" --config "$CONFIG" simulate replay smoke-run >/dev/null
python3 "$CLI" --config "$CONFIG" simulate config-diff >/dev/null
python3 "$CLI" --config "$CONFIG" report cycle-times >/dev/null
python3 "$CLI" --config "$CONFIG" report cycle-times --format json | python3 -m json.tool >/dev/null
python3 "$CLI" --config "$CONFIG" report gate-friction >/dev/null
python3 "$CLI" --config "$CONFIG" report gate-friction --format json | python3 -m json.tool >/dev/null
python3 "$CLI" --config "$CONFIG" report documentation >/dev/null
python3 "$CLI" --config "$CONFIG" lifecycle validate >/dev/null
python3 "$CLI" --config "$CONFIG" profiles disable documentation >/dev/null
python3 "$CLI" --config "$CONFIG" interview --profile spec-driven >/dev/null
python3 "$CLI" --config "$CONFIG" interview --config-key transport.mode >/dev/null
python3 "$CLI" --config "$CONFIG" provider-actions list >/dev/null
python3 "$CLI" --config "$CONFIG" provider-actions flush >/dev/null

echo "cli matrix OK"
