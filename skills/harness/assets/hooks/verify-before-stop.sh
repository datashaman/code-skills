#!/usr/bin/env bash
# Stop hook. Refuse to stop if the project's verification check fails.
# Exit 2 = block stop and feed stderr back to the model.
# Only runs if a verification script exists — silent otherwise.

set -u

# Honour an explicit opt-out for sessions where you're mid-investigation.
[ "${CLAUDE_SKIP_VERIFY:-}" = "1" ] && exit 0

if [ -x ./scripts/harness-check.sh ]; then
  if ! out="$(./scripts/harness-check.sh 2>&1)"; then
    printf 'Stop blocked by ~/.claude/hooks/verify-before-stop.sh: harness-check.sh failed.\n\n%s\n\nFix or amend the rule (with rationale) before declaring done. Set CLAUDE_SKIP_VERIFY=1 to override.\n' "$out" >&2
    exit 2
  fi
  exit 0
fi

# Fallback — only run if there's a clear, fast check.
if [ -f composer.json ] && grep -q '"lint:check"' composer.json 2>/dev/null; then
  if ! out="$(composer lint:check 2>&1)"; then
    printf 'Stop blocked: composer lint:check failed.\n\n%s\n' "$out" >&2
    exit 2
  fi
fi

exit 0
