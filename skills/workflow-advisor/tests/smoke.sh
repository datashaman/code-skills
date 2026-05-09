#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURE="$ROOT/tests/fixtures/minimal-repo"
CONFIG="$FIXTURE/.workflow/config.yml"
EVENT="$ROOT/tests/fixtures/events/pr_opened.json"

cd "$FIXTURE"

python3 "$ROOT/scripts/cli.py" --help | grep -q "workflow-advisor"
python3 "$ROOT/scripts/cli.py" --config "$CONFIG" doctor >/dev/null
python3 "$ROOT/scripts/cli.py" --config "$CONFIG" interview | grep -q "review_policy.codeowners_required"
python3 "$ROOT/scripts/cli.py" --config "$CONFIG" lifecycle show | grep -q "spec"
python3 "$ROOT/scripts/cli.py" --config "$CONFIG" report process | grep -q "Workflow summary"
python3 "$ROOT/scripts/cli.py" --config "$CONFIG" simulate event pull_request.opened | grep -q "Simulation"
python3 "$ROOT/scripts/cli.py" --config "$CONFIG" reconcile --dry-run --event-name pull_request --event-payload "$EVENT" | grep -q "Proposed changes"
python3 "$ROOT/tests/provider_actions_smoke.py" | grep -q "provider actions smoke OK"

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

echo "workflow-advisor smoke OK"
