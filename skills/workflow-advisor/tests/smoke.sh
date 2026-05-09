#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURE="$ROOT/tests/fixtures/minimal-repo"
CONFIG="$FIXTURE/.workflow/config.yml"
EVENT="$ROOT/tests/fixtures/events/pr_opened.json"

cd "$FIXTURE"

python3 "$ROOT/scripts/cli.py" --help | grep -q "workflow-advisor"
python3 "$ROOT/scripts/cli.py" --config "$CONFIG" doctor >/dev/null
python3 "$ROOT/scripts/cli.py" --config "$CONFIG" status | grep -q "Active items"
python3 "$ROOT/scripts/cli.py" --config "$CONFIG" status pr-42 | grep -q "Workflow status"
python3 "$ROOT/scripts/cli.py" --config "$CONFIG" profiles list | grep -q "spec-driven: enabled"
python3 "$ROOT/scripts/cli.py" --config "$CONFIG" profiles list --verbose | grep -q "artifacts:"
python3 "$ROOT/scripts/cli.py" --config "$CONFIG" profiles enable security | grep -q '"profile": "security"'
TMP_CONFIG="$(mktemp)"
cp "$CONFIG" "$TMP_CONFIG"
python3 "$ROOT/scripts/cli.py" --config "$TMP_CONFIG" profiles enable security --apply >/dev/null
grep -q "security:.*enabled: true" "$TMP_CONFIG" || grep -q "security:" "$TMP_CONFIG"
rm -f "$TMP_CONFIG"
python3 "$ROOT/scripts/cli.py" --config "$CONFIG" migrate --dry-run | grep -q "Schema up to date"
python3 "$ROOT/scripts/cli.py" --config "$CONFIG" interview | grep -q "review_policy.codeowners_required"
python3 "$ROOT/scripts/cli.py" --config "$CONFIG" lifecycle show | grep -q "spec"
python3 "$ROOT/scripts/cli.py" --config "$CONFIG" report process | grep -q "Workflow summary"
python3 "$ROOT/scripts/cli.py" --config "$CONFIG" report role-load | grep -q "Role load"
python3 "$ROOT/scripts/cli.py" --config "$CONFIG" simulate event pull_request.opened | grep -q "Simulation"
python3 "$ROOT/scripts/cli.py" --config "$CONFIG" reconcile --dry-run --event-name pull_request --event-payload "$EVENT" | grep -q "Proposed changes"
python3 "$ROOT/scripts/cli.py" provider-actions list | grep -q "No pending provider actions"
python3 "$ROOT/tests/provider_actions_smoke.py" | grep -q "provider actions smoke OK"
python3 "$ROOT/tests/lifecycle_gates_smoke.py" | grep -q "lifecycle gates smoke OK"
python3 "$ROOT/tests/cascade_dependents_smoke.py" | grep -q "cascade dependents smoke OK"
python3 "$ROOT/tests/state_io_smoke.py" | grep -q "state io smoke OK"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cp -R "$FIXTURE"/. "$TMP"/
cd "$TMP"
git init -q
git add .
git -c user.name=test -c user.email=test@example.com commit -qm "fixture"
python3 "$ROOT/scripts/cli.py" --config "$TMP/.workflow/config.yml" reconcile --event-name pull_request --event-payload "$EVENT" | grep -q "reconcile.completed"
test -f ".workflow/artifacts/specs/demo.yml"
test -f ".workflow/metrics/events.jsonl"
test -f ".workflow/state/processed_events.yml"
grep -q "fixture-delivery-1" ".workflow/state/processed_events.yml"
test -f ".workflow/provider-actions/pending.jsonl"
grep -q "labels.apply_diff" ".workflow/provider-actions/pending.jsonl"
python3 "$ROOT/scripts/cli.py" --config "$TMP/.workflow/config.yml" reconcile --event-name pull_request --event-payload "$EVENT" | grep -q "reconcile.noop"

echo "workflow-advisor smoke OK"
