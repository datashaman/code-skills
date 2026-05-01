#!/usr/bin/env bash
# Uninstaller for the harness skill.
#
# Scope-agnostic: targets either user scope (~/.claude/) or project scope
# (<project>/.claude/). Default is auto-detected from $SKILL_DIR — same logic
# as install.sh. Conservative: only removes files whose content still matches
# the installed template; user-modified files are kept.
#
# Usage:
#   bash uninstall.sh                    # auto-detect scope; remove unmodified hooks + commands + hook-entries
#   bash uninstall.sh --scope=user       # force user scope
#   bash uninstall.sh --scope=project    # force project scope
#   bash uninstall.sh --target=PATH      # explicit .claude/ target dir
#   bash uninstall.sh --dry-run          # show what would happen; remove nothing
#   bash uninstall.sh --force            # remove hooks/commands even if user-modified
#
# Opt in to wider removal (default keeps these):
#   --remove-memory     # remove auto-memory entries (user scope only)
#   --remove-claude-md  # remove CLAUDE.md (content-match policy)
#   --remove-env        # remove CLAUDE_CODE_AUTO_COMPACT_WINDOW env (user scope only)
#   --all               # = --force + --remove-memory + --remove-claude-md + --remove-env
#
# Or keep specific surfaces that the default WOULD remove:
#   --keep-hooks        # leave hook .sh files alone
#   --keep-commands     # leave slash command .md files alone
#   --keep-settings     # leave settings.json untouched (don't strip hook entries)

set -euo pipefail

FORCE=0
DRY=0
REMOVE_MEMORY=0
REMOVE_CLAUDE_MD=0
REMOVE_ENV=0
# Per-surface keep flags (escape hatch — keep these regardless of defaults).
KEEP_HOOKS=0
KEEP_COMMANDS=0
KEEP_SETTINGS=0
SCOPE=""
TARGET=""
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    --dry-run) DRY=1 ;;
    --remove-memory) REMOVE_MEMORY=1 ;;
    --remove-claude-md) REMOVE_CLAUDE_MD=1 ;;
    --remove-env) REMOVE_ENV=1 ;;
    --keep-hooks) KEEP_HOOKS=1 ;;
    --keep-commands) KEEP_COMMANDS=1 ;;
    --keep-settings) KEEP_SETTINGS=1 ;;
    --all) FORCE=1; REMOVE_MEMORY=1; REMOVE_CLAUDE_MD=1; REMOVE_ENV=1 ;;
    --scope=user) SCOPE=user ;;
    --scope=project) SCOPE=project ;;
    --scope=*) echo "invalid --scope (use user|project): $arg" >&2; exit 2 ;;
    --target=*) TARGET="${arg#--target=}" ;;
    -h|--help)
      # Print the leading comment block (after the shebang) up to the first
      # non-comment line. Robust to script edits — no fixed line numbers.
      awk 'NR>1 { if (/^#/) { sub(/^# ?/, ""); print } else { exit } }' "${BASH_SOURCE[0]}"
      exit 0 ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

SKILL_DIR="${SKILL_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
ASSETS="$SKILL_DIR/assets"
[ -d "$ASSETS" ] || { echo "error: $ASSETS not found" >&2; exit 1; }

detect_scope_root() {
  local d="$SKILL_DIR"
  while [ "$d" != "/" ] && [ -n "$d" ]; do
    if [ "$(basename "$d")" = ".claude" ]; then
      dirname "$d"
      return 0
    fi
    d="$(dirname "$d")"
  done
  return 1
}

if [ -n "$TARGET" ]; then
  :
elif [ "$SCOPE" = "user" ]; then
  TARGET="$HOME/.claude"
elif [ "$SCOPE" = "project" ]; then
  TARGET="${CLAUDE_PROJECT_DIR:-$PWD}/.claude"
else
  if scope_root="$(detect_scope_root)"; then
    TARGET="$scope_root/.claude"
    if [ "$scope_root" = "$HOME" ]; then SCOPE=user; else SCOPE=project; fi
  else
    cat >&2 <<EOF
error: cannot auto-detect scope (no .claude/ ancestor of \$SKILL_DIR).
       SKILL_DIR=$SKILL_DIR
       Pass --scope=user, --scope=project, or --target=PATH.
EOF
    exit 2
  fi
fi
if [ -z "$SCOPE" ]; then
  if [ "$TARGET" = "$HOME/.claude" ]; then SCOPE=user; else SCOPE=project; fi
fi

USER_PROJECT_KEY="${USER_PROJECT_KEY:-$(printf '%s' "$HOME" | tr '/' '-')}"
MEMORY_DIR="$HOME/.claude/projects/$USER_PROJECT_KEY/memory"

# See install.sh comment — these are literal strings written into settings.json.
if [ "$SCOPE" = "user" ]; then
  # shellcheck disable=SC2088
  HOOK_CMD_BASE='~/.claude/hooks'
  CLAUDE_MD_PATH="$TARGET/CLAUDE.md"
else
  # shellcheck disable=SC2016
  HOOK_CMD_BASE='"$CLAUDE_PROJECT_DIR"/.claude/hooks'
  CLAUDE_MD_PATH="$(dirname "$TARGET")/CLAUDE.md"
fi

say() { echo "→ $*"; }

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

sha256_eq() {
  [ -f "$1" ] && [ -f "$2" ] || return 1
  local a b
  a="$(sha256 "$1")" || return 1
  b="$(sha256 "$2")" || return 1
  [ "$a" = "$b" ]
}

remove_safe() {
  local installed="$1" template="$2"
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

# Preflight: tell the user what this run will touch and what it WON'T.
cat <<EOF
══════════════════════════════════════════════════════════════════════
  harness uninstall — preflight
══════════════════════════════════════════════════════════════════════
  Scope:  $SCOPE
  Target: $TARGET

  Removed by default (only if content still matches the installed template;
  customisations are kept and reported as "keep (modified)"; --force overrides):
EOF
[ $KEEP_HOOKS -eq 1 ]    && echo "    — $TARGET/hooks/*.sh                      (KEEP — --keep-hooks)" \
                         || echo "    • $TARGET/hooks/*.sh"
[ $KEEP_COMMANDS -eq 1 ] && echo "    — $TARGET/commands/{verify,plan}.md       (KEEP — --keep-commands)" \
                         || echo "    • $TARGET/commands/{verify,plan}.md"
[ $KEEP_SETTINGS -eq 1 ] && echo "    — Hook entries in $TARGET/settings.json   (KEEP — --keep-settings)" \
                         || echo "    • Hook entries in $TARGET/settings.json   (other settings untouched)"
cat <<EOF

  KEPT unless explicitly opted in:
    • $CLAUDE_MD_PATH$([ $REMOVE_CLAUDE_MD -eq 1 ] && echo '   ← will be REMOVED (--remove-claude-md)' || echo '   (--remove-claude-md to remove)')
EOF
if [ "$SCOPE" = "user" ]; then
  cat <<EOF
    • $MEMORY_DIR/*.md$([ $REMOVE_MEMORY -eq 1 ] && echo '   ← will be REMOVED (--remove-memory)' || echo '   (--remove-memory to remove)')
    • env.CLAUDE_CODE_AUTO_COMPACT_WINDOW$([ $REMOVE_ENV -eq 1 ] && echo '   ← will be REMOVED (--remove-env)' || echo '   (--remove-env to remove)')
EOF
fi
if [ $FORCE -eq 1 ]; then
  echo
  echo "  ⚠  --force is active: files will be removed even if you have customised them."
fi
cat <<EOF

  Escape hatches:
    --keep-hooks  --keep-commands  --keep-settings   (preserve specific surfaces)
    --remove-memory  --remove-claude-md  --remove-env  (broaden the sweep)
    --all  (everything: --force + all three --remove-* flags)
    --dry-run  (always recommended first run)
══════════════════════════════════════════════════════════════════════

EOF

[ $DRY -eq 1 ] && say "DRY RUN — no changes will be written"

say "scope: $SCOPE  target: $TARGET"

# 1. Hooks.
if [ $KEEP_HOOKS -eq 1 ]; then
  say "keeping hooks (--keep-hooks)"
else
  say "removing hooks"
  for f in "$ASSETS/hooks/"*.sh; do
    name="$(basename "$f")"
    remove_safe "$TARGET/hooks/$name" "$f"
  done
fi

# 2. Slash commands.
if [ $KEEP_COMMANDS -eq 1 ]; then
  say "keeping slash commands (--keep-commands)"
else
  say "removing slash commands"
  for f in "$ASSETS/commands/"*.md; do
    name="$(basename "$f")"
    remove_safe "$TARGET/commands/$name" "$f"
  done
fi

# 3. Memory (opt-in; user scope only — memory is per-user by design).
if [ "$SCOPE" != "user" ]; then
  say "skipping memory (project scope; memory is per-user)"
elif [ $REMOVE_MEMORY -eq 1 ]; then
  say "removing memory templates"
  for f in "$ASSETS/memory/"*.tmpl; do
    name="$(basename "$f" .tmpl)"
    remove_safe "$MEMORY_DIR/$name" "$f"
  done
else
  say "keeping memory (pass --remove-memory to opt in)"
fi

# 4. CLAUDE.md (opt-in).
# At user scope: $TARGET/CLAUDE.md (= ~/.claude/CLAUDE.md).
# At project scope: <project>/CLAUDE.md (the project root, not under .claude/).
if [ "$SCOPE" = "user" ]; then
  CLAUDE_MD_PATH="$TARGET/CLAUDE.md"
else
  CLAUDE_MD_PATH="$(dirname "$TARGET")/CLAUDE.md"
fi
if [ $REMOVE_CLAUDE_MD -eq 1 ]; then
  say "removing CLAUDE.md"
  remove_safe "$CLAUDE_MD_PATH" "$ASSETS/CLAUDE.md.tmpl"
else
  say "keeping CLAUDE.md (pass --remove-claude-md to opt in)"
fi

# 5. Patch settings.json — remove our hook entries (and env var if user scope + --remove-env).
SETTINGS="$TARGET/settings.json"
if [ $KEEP_SETTINGS -eq 1 ]; then
  say "keeping settings.json untouched (--keep-settings)"
elif [ ! -f "$SETTINGS" ]; then
  say "no settings.json — skipping settings patch"
else
  say "cleaning settings.json"
  if [ $DRY -eq 1 ]; then
    echo "  [dry-run] would strip 4 hook entries$([ $REMOVE_ENV -eq 1 ] && [ "$SCOPE" = user ] && echo ' + env var')"
  else
    SETTINGS="$SETTINGS" SCOPE="$SCOPE" HOOK_CMD_BASE="$HOOK_CMD_BASE" REMOVE_ENV="$REMOVE_ENV" python3 - <<'PY'
import json, os
p = os.environ["SETTINGS"]
scope = os.environ["SCOPE"]
base = os.environ["HOOK_CMD_BASE"]
with open(p) as f:
    s = json.load(f)

removed = []

OUR_CMDS = {
    "PreToolUse":  f"{base}/block-force-push.sh",
    "PostToolUse": f"{base}/format-on-edit.sh",
    "PostCompact": f"{base}/post-compact-reinject.sh",
    "Stop":        f"{base}/verify-before-stop.sh",
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
    if new_blocks:
        hooks[event] = new_blocks
    elif event in hooks:
        del hooks[event]
        removed.append(f"{event} (empty)")

if not hooks and "hooks" in s:
    del s["hooks"]

# Env var only exists at user scope.
if scope == "user" and os.environ.get("REMOVE_ENV") == "1":
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
for d in "$TARGET/hooks" "$TARGET/commands" "$TARGET/agents"; do
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
  if [ "$SCOPE" = "user" ]; then
    [ $REMOVE_MEMORY -eq 0 ]    && echo "  --remove-memory     (memory entries in $MEMORY_DIR)"
    [ $REMOVE_ENV -eq 0 ]       && echo "  --remove-env        (env.CLAUDE_CODE_AUTO_COMPACT_WINDOW in settings.json)"
  fi
  [ $REMOVE_CLAUDE_MD -eq 0 ] && echo "  --remove-claude-md  ($CLAUDE_MD_PATH)"
  echo "  --all               (everything above + --force)"
fi
