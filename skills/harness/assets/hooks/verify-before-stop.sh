#!/usr/bin/env bash
# Stop hook. Refuse to stop if there are uncommitted code changes AND the
# project's verification check fails. Allow stop on read-only sessions
# (no working-tree changes) so investigation/exploration can end naturally.
#
# Override at any time: CLAUDE_SKIP_VERIFY=1
# Exit 2 = block stop and feed stderr back to the model.

set -u

# Explicit opt-out — for sessions where you intentionally want to stop with
# work in progress (e.g., handing off to the user, mid-debug breakpoint).
[ "${CLAUDE_SKIP_VERIFY:-}" = "1" ] && exit 0

# Only enforce on sessions that have actually modified the tree. Without this,
# a read-only session ("explain this code", "what does X do") gets trapped if
# pre-existing tests fail. We want the hook to fire when CLAUDE made changes,
# not when the user happens to be in a broken-tree state.
if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if [ -z "$(git status --porcelain 2>/dev/null)" ]; then
    # Clean working tree — nothing to verify. Allow stop.
    exit 0
  fi
else
  # Not a git repo — be permissive. Verify-on-stop is a sharp tool; only use it
  # where we have a clear "code was changed" signal.
  exit 0
fi

# Working tree is dirty. Run the verification check.
if [ -x ./scripts/harness-check.sh ]; then
  if ! out="$(./scripts/harness-check.sh 2>&1)"; then
    printf 'Stop blocked: harness-check.sh failed (working tree has changes).\n\n%s\n\nFix the failure, or set CLAUDE_SKIP_VERIFY=1 to stop anyway (e.g. handing off to user).\n' "$out" >&2
    exit 2
  fi
  exit 0
fi

# Fallback — language-default fast checks. Only run when explicitly available.
if [ -f composer.json ] && grep -q '"lint:check"' composer.json 2>/dev/null; then
  if ! out="$(composer lint:check 2>&1)"; then
    printf 'Stop blocked: composer lint:check failed (working tree has changes).\n\n%s\n\nSet CLAUDE_SKIP_VERIFY=1 to override.\n' "$out" >&2
    exit 2
  fi
fi

exit 0
