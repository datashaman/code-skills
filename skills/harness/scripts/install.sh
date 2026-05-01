#!/usr/bin/env bash
# Idempotent installer for the harness skill.
# Copies templates from $SKILL_DIR/assets/ into ~/.claude/, never clobbers existing files
# unless --force is passed. Patches settings.json to wire up hooks.
#
# Usage:
#   bash install.sh                    # non-interactive; never clobber existing files
#   bash install.sh --force            # overwrite existing hooks/commands/CLAUDE.md
#   bash install.sh --dry-run          # show what would be done
#   bash install.sh --skip-memory      # leave memory/ alone (recommended if already populated)
#   bash install.sh --skip-settings    # leave settings.json alone
#
# Reads SKILL_DIR from env if set, otherwise computes from script location.
# To install against a different home, set HOME=/some/path before invoking — the
# script derives every path from $HOME for consistency between filesystem layout
# and the paths written into settings.json.

set -euo pipefail

FORCE=0
DRY=0
SKIP_MEMORY=0
SKIP_SETTINGS=0
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    --dry-run) DRY=1 ;;
    --skip-memory) SKIP_MEMORY=1 ;;
    --skip-settings) SKIP_SETTINGS=1 ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

SKILL_DIR="${SKILL_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
ASSETS="$SKILL_DIR/assets"
HOME_CLAUDE="$HOME/.claude"
USER_PROJECT_KEY="${USER_PROJECT_KEY:-$(printf '%s' "$HOME" | tr '/' '-')}"  # e.g. -Users-marlinf
MEMORY_DIR="$HOME_CLAUDE/projects/$USER_PROJECT_KEY/memory"

[ -d "$ASSETS" ] || { echo "error: $ASSETS not found" >&2; exit 1; }

say() { echo "→ $*"; }

# do_or_dry — execute the given argv directly (no eval), or in dry-run mode
# print a shell-quoted preview using printf %q.
do_or_dry() {
  if [ $DRY -eq 1 ]; then
    local arg
    printf '  [dry-run]'
    for arg in "$@"; do printf ' %q' "$arg"; done
    printf '\n'
  else
    "$@"
  fi
}

# 1. Ensure target dirs.
say "ensuring directories"
do_or_dry mkdir -p \
  "$HOME_CLAUDE/hooks" \
  "$HOME_CLAUDE/commands" \
  "$HOME_CLAUDE/agents" \
  "$MEMORY_DIR"

# Helper: copy with overwrite policy.
copy_safe() {
  local src="$1" dst="$2"
  if [ -e "$dst" ] && [ $FORCE -eq 0 ]; then
    echo "  skip (exists): $dst"
    return 0
  fi
  if [ $DRY -eq 1 ]; then
    echo "  [dry-run] would install: $dst"
  else
    cp "$src" "$dst"
    echo "  installed: $dst"
  fi
}

# 2. CLAUDE.md (template — never clobber by default; users edit this heavily).
say "installing global CLAUDE.md"
copy_safe "$ASSETS/CLAUDE.md.tmpl" "$HOME_CLAUDE/CLAUDE.md"

# 3. Hooks.
say "installing hooks"
for f in "$ASSETS/hooks/"*.sh; do
  name="$(basename "$f")"
  copy_safe "$f" "$HOME_CLAUDE/hooks/$name"
  do_or_dry chmod +x "$HOME_CLAUDE/hooks/$name"
done

# 4. Commands.
say "installing slash commands"
for f in "$ASSETS/commands/"*.md; do
  name="$(basename "$f")"
  copy_safe "$f" "$HOME_CLAUDE/commands/$name"
done

# 5. Memory templates.
if [ $SKIP_MEMORY -eq 1 ]; then
  say "skipping memory (--skip-memory)"
else
  say "installing memory templates"
  for f in "$ASSETS/memory/"*.tmpl; do
    name="$(basename "$f" .tmpl)"
    copy_safe "$f" "$MEMORY_DIR/$name"
  done
fi

# 6. Patch settings.json — add env vars + hooks blocks if missing.
if [ $SKIP_SETTINGS -eq 1 ]; then
  say "skipping settings.json (--skip-settings)"
else
  say "patching settings.json"
  SETTINGS="$HOME_CLAUDE/settings.json"
  if [ ! -f "$SETTINGS" ]; then
    if [ $DRY -eq 1 ]; then
      echo "  [dry-run] would create empty $SETTINGS"
    else
      printf '{}\n' > "$SETTINGS"
    fi
  fi
  if [ $DRY -eq 0 ]; then
    SETTINGS="$SETTINGS" python3 - <<'PY'
import json, os
p = os.environ["SETTINGS"]
with open(p) as f:
    s = json.load(f)

changed = False

env = s.setdefault("env", {})
if env.get("CLAUDE_CODE_AUTO_COMPACT_WINDOW") != "400000":
    env["CLAUDE_CODE_AUTO_COMPACT_WINDOW"] = "400000"
    changed = True

hooks = s.setdefault("hooks", {})

# settings.json gets the literal "~/.claude/..." form. Claude Code expands ~
# at hook-execution time, so this stays portable across machines / users.
OUR_HOOKS = [
    ("PreToolUse",  "Bash",       "~/.claude/hooks/block-force-push.sh"),
    ("PostToolUse", "Write|Edit", "~/.claude/hooks/format-on-edit.sh"),
    ("PostCompact",  None,        "~/.claude/hooks/post-compact-reinject.sh"),
    ("Stop",         None,        "~/.claude/hooks/verify-before-stop.sh"),
]

def ensure_hook(event, matcher, cmd):
    blocks = hooks.setdefault(event, [])
    for b in blocks:
        if b.get("matcher") == matcher:
            for h in b.get("hooks", []):
                if h.get("command") == cmd:
                    return False  # already present
            b.setdefault("hooks", []).append({"type": "command", "command": cmd})
            return True
    block = {"hooks": [{"type": "command", "command": cmd}]}
    if matcher is not None:
        block["matcher"] = matcher
    blocks.append(block)
    return True

for event, matcher, cmd in OUR_HOOKS:
    if ensure_hook(event, matcher, cmd):
        changed = True

with open(p, "w") as f:
    json.dump(s, f, indent=2)
    f.write("\n")
print("  settings.json updated" if changed else "  settings.json already current")
PY
  else
    echo "  [dry-run] would patch $SETTINGS with env + 4 hooks"
  fi
fi

echo
say "done"
echo
echo "Next steps:"
echo "  1. Edit $HOME_CLAUDE/CLAUDE.md — fill in the 'Stack signals' section."
echo "  2. Edit $MEMORY_DIR/user_role.md — replace placeholders with your actual context."
echo "  3. Restart Claude Code (or open a new session) — hooks load on session start."
echo "  4. Optional: run scripts/snapshot.sh to mirror this setup into a private git repo"
echo "     and use scripts/audit-prompt.md to schedule a monthly remote audit."
