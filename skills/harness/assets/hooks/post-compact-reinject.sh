#!/usr/bin/env bash
# PostCompact hook. Re-inject the project's CLAUDE.md (and AGENTS.md if present)
# so context-compression doesn't strip the operating contract.
# Output goes to the model.

set -u

emit() {
  [ -f "$1" ] || return 0
  echo
  echo "--- $1 (re-injected after compact) ---"
  cat "$1"
}

emit ./CLAUDE.md
emit ./AGENTS.md
emit ~/.claude/CLAUDE.md

exit 0
