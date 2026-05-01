#!/usr/bin/env bash
# Uninstaller for the harness skill.
# Conservative by default: only removes files whose content still matches the
# installed template (sha256 compare against $SKILL_DIR/assets/). User-modified
# files are kept. CLAUDE.md, memory entries, and the env var are kept unless
# explicitly opted in — those tend to be customised heavily.
#
# Usage:
#   bash uninstall.sh                    # remove only unmodified hooks + commands + hook entries
#   bash uninstall.sh --dry-run          # show what would happen
#   bash uninstall.sh --force            # remove hooks/commands even if modified
#   bash uninstall.sh --remove-memory    # also remove memory templates (content-match policy)
#   bash uninstall.sh --remove-claude-md # also remove CLAUDE.md (content-match policy)
#   bash uninstall.sh --remove-env       # also remove CLAUDE_CODE_AUTO_COMPACT_WINDOW env var
#   bash uninstall.sh --all              # equivalent to --force --remove-memory --remove-claude-md --remove-env

set -euo pipefail

FORCE=0
DRY=0
REMOVE_MEMORY=0
REMOVE_CLAUDE_MD=0
REMOVE_ENV=0
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    --dry-run) DRY=1 ;;
    --remove-memory) REMOVE_MEMORY=1 ;;
    --remove-claude-md) REMOVE_CLAUDE_MD=1 ;;
    --remove-env) REMOVE_ENV=1 ;;
    --all) FORCE=1; REMOVE_MEMORY=1; REMOVE_CLAUDE_MD=1; REMOVE_ENV=1 ;;
    -h|--help)
      sed -n '2,16p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'
      exit 0 ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

SKILL_DIR="${SKILL_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
ASSETS="$SKILL_DIR/assets"
HOME_CLAUDE="$HOME/.claude"
USER_PROJECT_KEY="${USER_PROJECT_KEY:-$(printf '%s' "$HOME" | tr '/' '-')}"
MEMORY_DIR="$HOME_CLAUDE/projects/$USER_PROJECT_KEY/memory"

[ -d "$ASSETS" ] || { echo "error: $ASSETS not found" >&2; exit 1; }

say() { echo "→ $*"; }

# sha256 <file> — print sha256 hex digest. Tries sha256sum, shasum, then python3
# fallback. Returns non-zero if no hashing tool is available.
sha256() {
  local f="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$f" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$f" | awk '{print $1}'
  elif command -v python3 >/dev/null 2>&1; then
    python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$f"
  else
    return 1
  fi
}

# sha256_eq <fileA> <fileB> — true iff both exist, both can be hashed, and hashes match.
sha256_eq() {
  [ -f "$1" ] && [ -f "$2" ] || return 1
  local a b
  a="$(sha256 "$1")" || return 1
  b="$(sha256 "$2")" || return 1
  [ "$a" = "$b" ]
}

# remove_safe <installed_file> <template_file> <label>
# Removes installed_file iff content matches template, or --force is set.
# Skips silently if file doesn't exist.
remove_safe() {
  local installed="$1" template="$2" label="$3"
  if [ ! -e "$installed" ]; then
    return 0
  fi
  if [ $FORCE -eq 0 ] && [ -f "$template" ] && ! sha256_eq "$installed" "$template"; then
    echo "  keep (modified): $installed"
    return 0
  fi
  if [ $DRY -eq 1 ]; then
    echo "  [dry-run] would remove: $installed"
  else
    rm -f "$installed"
    echo "  removed: $installed"
  fi
}

# 1. Hooks.
say "removing hooks"
for f in "$ASSETS/hooks/"*.sh; do
  name="$(basename "$f")"
  remove_safe "$HOME_CLAUDE/hooks/$name" "$f" "hook"
done

# 2. Slash commands.
say "removing slash commands"
for f in "$ASSETS/commands/"*.md; do
  name="$(basename "$f")"
  remove_safe "$HOME_CLAUDE/commands/$name" "$f" "command"
done

# 3. Memory (opt-in).
if [ $REMOVE_MEMORY -eq 1 ]; then
  say "removing memory templates"
  for f in "$ASSETS/memory/"*.tmpl; do
    name="$(basename "$f" .tmpl)"
    remove_safe "$MEMORY_DIR/$name" "$f" "memory"
  done
else
  say "keeping memory (pass --remove-memory to opt in)"
fi

# 4. CLAUDE.md (opt-in).
if [ $REMOVE_CLAUDE_MD -eq 1 ]; then
  say "removing CLAUDE.md"
  remove_safe "$HOME_CLAUDE/CLAUDE.md" "$ASSETS/CLAUDE.md.tmpl" "CLAUDE.md"
else
  say "keeping CLAUDE.md (pass --remove-claude-md to opt in)"
fi

# 5. Patch settings.json — remove our hook entries (and env var if --remove-env).
SETTINGS="$HOME_CLAUDE/settings.json"
if [ ! -f "$SETTINGS" ]; then
  say "no settings.json — skipping settings patch"
else
  say "cleaning settings.json"
  if [ $DRY -eq 1 ]; then
    echo "  [dry-run] would strip 4 hook entries$([ $REMOVE_ENV -eq 1 ] && echo ' + env var')"
  else
    SETTINGS="$SETTINGS" REMOVE_ENV="$REMOVE_ENV" python3 - <<'PY'
import json, os
p = os.environ["SETTINGS"]
with open(p) as f:
    s = json.load(f)

removed = []

# settings.json stores the literal "~/.claude/..." form (Claude Code expands
# ~ at hook-execution time), so we match against that exact string.
OUR_CMDS = {
    "PreToolUse":  "~/.claude/hooks/block-force-push.sh",
    "PostToolUse": "~/.claude/hooks/format-on-edit.sh",
    "PostCompact": "~/.claude/hooks/post-compact-reinject.sh",
    "Stop":        "~/.claude/hooks/verify-before-stop.sh",
}

hooks = s.get("hooks", {})
for event, cmd in OUR_CMDS.items():
    blocks = hooks.get(event, [])
    new_blocks = []
    for b in blocks:
        new_inner = [h for h in b.get("hooks", []) if h.get("command") != cmd]
        if len(new_inner) != len(b.get("hooks", [])):
            removed.append(f"{event} -> {cmd}")
        if new_inner:
            b["hooks"] = new_inner
            new_blocks.append(b)
        # else: drop the block entirely if its only hook was ours
    if new_blocks:
        hooks[event] = new_blocks
    elif event in hooks:
        del hooks[event]
        removed.append(f"{event} (empty)")

if not hooks and "hooks" in s:
    del s["hooks"]

if os.environ.get("REMOVE_ENV") == "1":
    env = s.get("env", {})
    if env.pop("CLAUDE_CODE_AUTO_COMPACT_WINDOW", None) is not None:
        removed.append("env.CLAUDE_CODE_AUTO_COMPACT_WINDOW")
    if not env and "env" in s:
        del s["env"]

with open(p, "w") as f:
    json.dump(s, f, indent=2)
    f.write("\n")

if removed:
    for r in removed:
        print(f"  removed: {r}")
else:
    print("  settings.json already clean")
PY
  fi
fi

# 6. Clean up empty dirs (best-effort).
say "tidying empty dirs"
for d in "$HOME_CLAUDE/hooks" "$HOME_CLAUDE/commands" "$HOME_CLAUDE/agents"; do
  if [ -d "$d" ] && [ -z "$(ls -A "$d" 2>/dev/null)" ]; then
    if [ $DRY -eq 1 ]; then
      echo "  [dry-run] would rmdir $d"
    else
      rmdir "$d" 2>/dev/null && echo "  rmdir $d"
    fi
  fi
done

echo
say "done"

if [ $REMOVE_MEMORY -eq 0 ] || [ $REMOVE_CLAUDE_MD -eq 0 ] || [ $REMOVE_ENV -eq 0 ]; then
  echo
  echo "Kept by default — re-run with the matching flag if you want them gone:"
  [ $REMOVE_MEMORY -eq 0 ]    && echo "  --remove-memory     (memory entries in $MEMORY_DIR)"
  [ $REMOVE_CLAUDE_MD -eq 0 ] && echo "  --remove-claude-md  ($HOME_CLAUDE/CLAUDE.md)"
  [ $REMOVE_ENV -eq 0 ]       && echo "  --remove-env        (env.CLAUDE_CODE_AUTO_COMPACT_WINDOW in settings.json)"
  echo "  --all               (everything above + --force)"
fi
