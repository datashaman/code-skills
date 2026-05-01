#!/usr/bin/env bash
# Idempotent installer for the harness skill.
# Copies templates from $SKILL_DIR/assets/ into ~/.claude/, never clobbers existing files
# unless --force is passed. Patches settings.json to wire up hooks.
#
# Usage:
#   bash install.sh                    # interactive, never clobber
#   bash install.sh --force            # overwrite existing hooks/commands/CLAUDE.md
#   bash install.sh --dry-run          # show what would be done
#   bash install.sh --skip-memory      # leave memory/ alone (recommended if already populated)
#   bash install.sh --skip-settings    # leave settings.json alone
#
# Reads SKILL_DIR from env if set, otherwise computes from script location.

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
HOME_CLAUDE="${HOME_CLAUDE:-$HOME/.claude}"
USER_PROJECT_KEY="${USER_PROJECT_KEY:-$(printf '%s' "$HOME" | tr '/' '-')}"  # e.g. -Users-marlinf
MEMORY_DIR="$HOME_CLAUDE/projects/$USER_PROJECT_KEY/memory"

[ -d "$ASSETS" ] || { echo "error: $ASSETS not found" >&2; exit 1; }

say() { echo "→ $*"; }
do_or_dry() { if [ $DRY -eq 1 ]; then echo "  [dry-run] $*"; else eval "$@"; fi; }

# 1. Ensure target dirs.
say "ensuring directories"
do_or_dry "mkdir -p '$HOME_CLAUDE/hooks' '$HOME_CLAUDE/commands' '$HOME_CLAUDE/agents' '$MEMORY_DIR'"

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
  do_or_dry "chmod +x '$HOME_CLAUDE/hooks/$name'"
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
    do_or_dry "echo '{}' > '$SETTINGS'"
  fi
  if [ $DRY -eq 0 ]; then
    python3 - <<PY
import json, os
p = os.path.expanduser("$SETTINGS")
with open(p) as f:
    s = json.load(f)

s.setdefault("env", {})
s["env"].setdefault("CLAUDE_CODE_AUTO_COMPACT_WINDOW", "400000")

s.setdefault("hooks", {})

def ensure_hook(event, matcher, cmd):
    blocks = s["hooks"].setdefault(event, [])
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

changed = False
changed |= ensure_hook("PreToolUse",  "Bash",       "~/.claude/hooks/block-force-push.sh")
changed |= ensure_hook("PostToolUse", "Write|Edit", "~/.claude/hooks/format-on-edit.sh")
changed |= ensure_hook("PostCompact",  None,        "~/.claude/hooks/post-compact-reinject.sh")
changed |= ensure_hook("Stop",         None,        "~/.claude/hooks/verify-before-stop.sh")

with open(p, "w") as f:
    json.dump(s, f, indent=2)
    f.write("\n")
print("  settings.json updated" if changed else "  settings.json already current")
PY
  else
    echo "  [dry-run] would patch $SETTINGS with env + 4 hooks"
  fi
fi

# (MEMORY.md is installed in step 5 alongside the other memory templates;
#  no separate bootstrap step needed.)

echo
say "done"
echo
echo "Next steps:"
echo "  1. Edit $HOME_CLAUDE/CLAUDE.md — fill in the 'Stack signals' section."
echo "  2. Edit $MEMORY_DIR/user_role.md — replace placeholders with your actual context."
echo "  3. Restart Claude Code (or open a new session) — hooks load on session start."
echo "  4. Optional: run scripts/snapshot.sh to mirror this setup into a private git repo"
echo "     and use scripts/audit-prompt.md to schedule a monthly remote audit."
