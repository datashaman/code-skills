#!/usr/bin/env bash
# Mirror ~/.claude/ into a target git repo (sanitised), commit, and push if there's a diff.
# Use this to keep a versioned snapshot of your harness for the monthly audit routine.
#
# Usage:
#   SNAPSHOT_REPO=~/Projects/<you>/claude-setup bash snapshot.sh
#
# Override sources with env:
#   CLAUDE_DIR=/some/path bash snapshot.sh
#   USER_PROJECT_KEY=-Users-foo bash snapshot.sh

set -euo pipefail

CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
USER_PROJECT_KEY="${USER_PROJECT_KEY:-$(printf '%s' "$HOME" | tr '/' '-')}"
MEMORY_SRC="$CLAUDE_DIR/projects/$USER_PROJECT_KEY/memory"

if [ -z "${SNAPSHOT_REPO:-}" ]; then
  echo "error: SNAPSHOT_REPO must be set to the target repo path" >&2
  echo "       e.g. SNAPSHOT_REPO=~/Projects/you/claude-setup bash snapshot.sh" >&2
  exit 2
fi

REPO_ROOT="$(cd "$SNAPSHOT_REPO" 2>/dev/null && pwd)" || {
  echo "error: $SNAPSHOT_REPO does not exist (mkdir + git init it first)" >&2
  exit 2
}

cd "$REPO_ROOT"
[ -d .git ] || { echo "error: $REPO_ROOT is not a git repo" >&2; exit 2; }

# 1. Wipe sync targets (preserves audits/, .git/, README.md, .gitignore, scripts/).
for d in hooks commands agents memory plugins; do
  rm -rf "${REPO_ROOT:?}/$d"
  mkdir -p "$d"
done
rm -f CLAUDE.md settings.json skills-installed.txt

# 2. Mirror.
[ -f "$CLAUDE_DIR/CLAUDE.md" ]     && cp "$CLAUDE_DIR/CLAUDE.md"     ./CLAUDE.md
[ -f "$CLAUDE_DIR/settings.json" ] && cp "$CLAUDE_DIR/settings.json" ./settings.json

shopt -s nullglob
for f in "$CLAUDE_DIR/hooks/"*.sh;    do cp "$f" ./hooks/;    done
for f in "$CLAUDE_DIR/commands/"*.md; do cp "$f" ./commands/; done
for f in "$CLAUDE_DIR/agents/"*.md;   do cp "$f" ./agents/;   done
shopt -u nullglob

if [ -d "$MEMORY_SRC" ]; then
  find "$MEMORY_SRC" -maxdepth 1 -type f \( -name '*.md' -o -name 'MEMORY.md' \) \
    -exec cp {} ./memory/ \;
fi
if [ -f "$CLAUDE_DIR/plugins/installed_plugins.json" ]; then
  cp "$CLAUDE_DIR/plugins/installed_plugins.json" ./plugins/installed_plugins.json
fi
if [ -d "$CLAUDE_DIR/skills" ]; then
  ls "$CLAUDE_DIR/skills" > ./skills-installed.txt
fi

# 3. Drop empty dirs.
for d in hooks commands agents memory plugins; do
  if [ -d "$d" ] && [ -z "$(ls -A "$d" 2>/dev/null)" ]; then
    rmdir "$d"
  fi
done

# 4. Secret scan.
SECRET_PATTERNS='(sk-ant-|ghp_|gho_|ghu_|AIza[0-9A-Za-z_-]{35}|AKIA[0-9A-Z]{16}|xox[baprs]-[0-9A-Za-z-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)'
if grep -rEln "$SECRET_PATTERNS" . 2>/dev/null \
    | grep -vE '^(\./)?(\.git/|scripts/snapshot\.sh)'; then
  echo "abort: potential secret detected — review above and re-run after scrubbing" >&2
  exit 1
fi

# 5. Commit + push.
git add -A
if git diff --cached --quiet; then
  echo "snapshot: no changes"
  exit 0
fi
ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
summary="$(git diff --cached --stat | tail -n 1)"
git -c commit.gpgsign=false commit -q -m "snapshot: refresh ~/.claude/ — $ts

$summary"
if git remote get-url origin >/dev/null 2>&1; then
  git push -q origin HEAD
  echo "snapshot: pushed"
else
  echo "snapshot: committed locally (no remote)"
fi
