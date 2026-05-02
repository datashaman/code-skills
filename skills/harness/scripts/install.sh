#!/usr/bin/env bash
# Idempotent installer for the harness skill.
#
# Scope-agnostic: targets either user scope (~/.claude/) or project scope
# (<project>/.claude/). Default is auto-detected from $SKILL_DIR — if the skill
# lives at <X>/.claude/skills/harness/ (or under a plugin cache below <X>/.claude/),
# the install lands at <X>/.claude/.
#
# Usage:
#   bash install.sh                          # auto-detect scope; install everything
#   bash install.sh --scope=user             # force user scope ($HOME/.claude)
#   bash install.sh --scope=project          # force project scope ($CLAUDE_PROJECT_DIR or $PWD)
#   bash install.sh --target=PATH            # explicit target dir (PATH should end in .claude)
#   bash install.sh --force                  # overwrite existing CLAUDE.md / hooks / commands / memory
#   bash install.sh --dry-run                # show what would be done; change nothing
#
# Per-surface skip flags (pick what NOT to install):
#   --skip-claude-md   --skip-hooks   --skip-commands   --skip-memory   --skip-settings
#
# Or a positive list (everything not listed is skipped):
#   --include=hooks,commands             # install only hooks + commands
#   --include=claude-md,settings         # only the operating contract + settings.json patch
#
# At project scope, memory is NOT seeded (memory is per-user by design and lives
# under $HOME regardless of where the project's .claude/ is). CLAUDE.md is
# skipped if a project CLAUDE.md already exists — most projects have one.

set -euo pipefail

FORCE=0
DRY=0
# Per-surface skip flags (pick what NOT to install). Defaults: install everything
# applicable to the scope. --include=LIST flips this to a positive list.
SKIP_CLAUDE_MD=0
SKIP_HOOKS=0
SKIP_COMMANDS=0
SKIP_MEMORY=0
SKIP_SETTINGS=0
INCLUDE=""
SCOPE=""
TARGET=""
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    --dry-run) DRY=1 ;;
    --skip-claude-md) SKIP_CLAUDE_MD=1 ;;
    --skip-hooks) SKIP_HOOKS=1 ;;
    --skip-commands) SKIP_COMMANDS=1 ;;
    --skip-memory) SKIP_MEMORY=1 ;;
    --skip-settings) SKIP_SETTINGS=1 ;;
    --include=*) INCLUDE="${arg#--include=}" ;;
    --scope=user) SCOPE=user ;;
    --scope=project) SCOPE=project ;;
    --scope=*) echo "invalid --scope (use user|project): $arg" >&2; exit 2 ;;
    --target=*) TARGET="${arg#--target=}" ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

# --include=LIST is shorthand: skip everything not in the comma-separated list.
# Valid items: claude-md, hooks, commands, memory, settings.
if [ -n "$INCLUDE" ]; then
  SKIP_CLAUDE_MD=1; SKIP_HOOKS=1; SKIP_COMMANDS=1; SKIP_MEMORY=1; SKIP_SETTINGS=1
  IFS=',' read -ra _items <<< "$INCLUDE"
  for it in "${_items[@]}"; do
    case "$it" in
      claude-md) SKIP_CLAUDE_MD=0 ;;
      hooks)     SKIP_HOOKS=0 ;;
      commands)  SKIP_COMMANDS=0 ;;
      memory)    SKIP_MEMORY=0 ;;
      settings)  SKIP_SETTINGS=0 ;;
      *) echo "invalid --include item: $it (valid: claude-md, hooks, commands, memory, settings)" >&2; exit 2 ;;
    esac
  done
fi

SKILL_DIR="${SKILL_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
ASSETS="$SKILL_DIR/assets"
[ -d "$ASSETS" ] || { echo "error: $ASSETS not found" >&2; exit 1; }

# Detect scope from $SKILL_DIR by walking up looking for a `.claude` ancestor.
# If found, the parent of that .claude is the scope root. We then check whether
# the scope root is $HOME (user scope) or something else (project scope).
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

# Resolve TARGET (the .claude/ directory we install into).
if [ -n "$TARGET" ]; then
  # Explicit path. Trust the caller.
  :
elif [ "$SCOPE" = "user" ]; then
  TARGET="$HOME/.claude"
elif [ "$SCOPE" = "project" ]; then
  TARGET="${CLAUDE_PROJECT_DIR:-$PWD}/.claude"
else
  # Auto-detect from $SKILL_DIR.
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

# Derive scope label if still unset (i.e., explicit --target was used).
if [ -z "$SCOPE" ]; then
  if [ "$TARGET" = "$HOME/.claude" ]; then SCOPE=user; else SCOPE=project; fi
fi

# Memory always lives under $HOME — it's per-user, regardless of where the
# project's .claude/ is. At project scope, memory seeding is opt-out by default.
USER_PROJECT_KEY="${USER_PROJECT_KEY:-$(printf '%s' "$HOME" | tr '/' '-')}"
MEMORY_DIR="$HOME/.claude/projects/$USER_PROJECT_KEY/memory"

# Hook command paths written into settings.json. User scope uses the portable
# tilde form; project scope uses a project-relative path (cwd is the project
# root when Claude Code runs hooks).
# Hook command paths are written verbatim into settings.json — Claude Code
# expands ~ and $CLAUDE_PROJECT_DIR at hook-execution time. We want these as
# literal strings in the JSON, so the SC2088 (tilde) and SC2016 ($var) hints
# are intentional and suppressed below.
if [ "$SCOPE" = "user" ]; then
  # shellcheck disable=SC2088
  HOOK_CMD_BASE='~/.claude/hooks'
else
  # shellcheck disable=SC2016
  HOOK_CMD_BASE='"$CLAUDE_PROJECT_DIR"/.claude/hooks'
fi

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

# Preflight: tell the user exactly what's about to change and where.
# Surfaces marked SKIP reflect the active flags; marked AUTO-SKIP if scope
# inherently excludes them (e.g. memory at project scope).
plan_line() {
  # plan_line "label" "skip_var_value" "auto_skip_condition" "description"
  local label="$1" skipped="$2" auto_skipped="$3" desc="$4"
  local marker="•"
  if [ "$auto_skipped" = "1" ]; then marker="—"; status=" (SKIP — not applicable at $SCOPE scope)"
  elif [ "$skipped" = "1" ]; then marker="—"; status=" (SKIP — flag)"
  else status=""; fi
  printf '    %s %s%s\n' "$marker" "$label" "$status"
  [ -n "$desc" ] && printf '         %s\n' "$desc"
}

# Determine scope-conditional auto-skips. (Env-var gating is handled inline
# in the settings.json patcher below — only memory needs a plan-line marker.)
PROJECT_SCOPE_NO_MEMORY=0
[ "$SCOPE" != "user" ] && PROJECT_SCOPE_NO_MEMORY=1

cat <<EOF
══════════════════════════════════════════════════════════════════════
  harness install — preflight
══════════════════════════════════════════════════════════════════════
  Scope:  $SCOPE
  Target: $TARGET

  Plan:
EOF
if [ "$SCOPE" = "user" ]; then
  plan_line "$TARGET/CLAUDE.md"                "$SKIP_CLAUDE_MD" "0" "operating contract — edit Stack signals after install"
  plan_line "$TARGET/hooks/*.sh"               "$SKIP_HOOKS"     "0" "4 guardrails: block-force-push / format-on-edit / post-compact-reinject / verify-before-stop"
  plan_line "$TARGET/commands/*.md" "$SKIP_COMMANDS"  "0" "slash commands"
  plan_line "$MEMORY_DIR/*.md"                 "$SKIP_MEMORY"    "0" "MEMORY.md index + 4 auto-memory templates"
  plan_line "$TARGET/settings.json"            "$SKIP_SETTINGS"  "0" "additive: env.CLAUDE_CODE_AUTO_COMPACT_WINDOW + 4 hook entries (NEVER touches permissions, marketplaces, statusLine, advisorModel, theme)"
else
  plan_line "$(dirname "$TARGET")/CLAUDE.md"    "$SKIP_CLAUDE_MD" "0" "operating contract — skipped if project already has a CLAUDE.md (use --force to override)"
  plan_line "$TARGET/hooks/*.sh"                "$SKIP_HOOKS"     "0" "4 guardrails"
  plan_line "$TARGET/commands/*.md"  "$SKIP_COMMANDS"  "0" "slash commands"
  plan_line "memory templates"                  "$SKIP_MEMORY"    "$PROJECT_SCOPE_NO_MEMORY" "memory is per-user; not seeded at project scope"
  plan_line "$TARGET/settings.json"             "$SKIP_SETTINGS"  "0" "additive: 4 hook entries (no env var at project scope)"
  echo "    (nothing in \$HOME is modified at project scope)"
fi
cat <<EOF

  Existing files are SKIPPED by default; pass --force to overwrite.

  Escape hatch — pick & choose what to install:
    --skip-claude-md  --skip-hooks  --skip-commands  --skip-memory  --skip-settings
    --include=hooks,commands         (positive list; everything not listed is skipped)

  To reverse: bash "$SKILL_DIR/scripts/uninstall.sh"
    Default uninstall removes only files whose contents still match the installed
    template — your customisations are kept (reported as "keep (modified)").
    ⚠  --all does a full sweep: hooks, commands, CLAUDE.md, memory, env var.
       Always run --dry-run first to see what will go.
══════════════════════════════════════════════════════════════════════

EOF

[ $DRY -eq 1 ] && say "DRY RUN — no changes will be written"

say "scope: $SCOPE  target: $TARGET"

# 1. Ensure target dirs.
say "ensuring directories"
DIRS_TO_MAKE=()
[ $SKIP_HOOKS -eq 0 ]    && DIRS_TO_MAKE+=("$TARGET/hooks")
[ $SKIP_COMMANDS -eq 0 ] && DIRS_TO_MAKE+=("$TARGET/commands")
DIRS_TO_MAKE+=("$TARGET/agents")
if [ "$SCOPE" = "user" ] && [ $SKIP_MEMORY -eq 0 ]; then
  DIRS_TO_MAKE+=("$MEMORY_DIR")
fi
[ ${#DIRS_TO_MAKE[@]} -gt 0 ] && do_or_dry mkdir -p "${DIRS_TO_MAKE[@]}"

# 2. CLAUDE.md — copy the template, then auto-fill the ## Stack signals
# section if a stack manifest is detected at the project root.
fill_stack_signals() {
  local md="$1"           # path to the freshly installed CLAUDE.md
  local detect_root="$2"  # dir to scan for manifests
  [ -f "$md" ] || return 0
  local detected
  detected="$(python3 "$SKILL_DIR/scripts/_detect_stack.py" "$detect_root" 2>/dev/null || true)"
  if [ -z "$detected" ]; then
    return 0  # no manifests — leave the placeholder in place for the user to fill
  fi
  # Replace the placeholder block (the HTML comment "Replace with your default
  # stack..." + its example block) with the detected bullets. Use python for
  # robust multi-line replacement. DETECT_ROOT is exported here so the log
  # line is accurate regardless of caller convention.
  CLAUDE_MD="$md" DETECTED="$detected" DETECT_ROOT="$detect_root" python3 - <<'PY'
import os, re
p = os.environ["CLAUDE_MD"]
detected = os.environ["DETECTED"].rstrip()
text = open(p).read()
# Match: <!-- Replace with your default stack ... --> through the closing -->
# of the example block. Be flexible about exact whitespace.
pattern = re.compile(
    r"<!--\s*Replace with your default stack\..*?-->\s*\n"
    r"(<!--\s*Example:.*?-->\s*\n)?",
    re.DOTALL,
)
new = pattern.sub(detected + "\n", text, count=1)
if new != text:
    open(p, "w").write(new)
    print(f"  auto-filled Stack signals from manifests in {os.environ['DETECT_ROOT']}")
PY
}

if [ $SKIP_CLAUDE_MD -eq 1 ]; then
  say "skipping CLAUDE.md (--skip-claude-md)"
elif [ "$SCOPE" = "user" ]; then
  say "installing global CLAUDE.md"
  copy_safe "$ASSETS/CLAUDE.md.tmpl" "$TARGET/CLAUDE.md"
  # At user scope, scan the user's home for a top-level manifest. Usually
  # there isn't one — the section will stay as a placeholder for hand-edit.
  # But if the user keeps a default-project at $HOME, this picks it up.
  [ $DRY -eq 0 ] && fill_stack_signals "$TARGET/CLAUDE.md" "$HOME"
else
  PROJECT_ROOT="$(dirname "$TARGET")"
  PROJECT_CLAUDE_MD="$PROJECT_ROOT/CLAUDE.md"
  if [ -e "$PROJECT_CLAUDE_MD" ] && [ $FORCE -eq 0 ]; then
    say "skipping CLAUDE.md (project already has one at $PROJECT_CLAUDE_MD — merge by hand, or --force)"
  else
    say "installing project CLAUDE.md"
    copy_safe "$ASSETS/CLAUDE.md.tmpl" "$PROJECT_CLAUDE_MD"
    [ $DRY -eq 0 ] && fill_stack_signals "$PROJECT_CLAUDE_MD" "$PROJECT_ROOT"
  fi
fi

# 3. Hooks.
if [ $SKIP_HOOKS -eq 1 ]; then
  say "skipping hooks (--skip-hooks)"
else
  say "installing hooks"
  for f in "$ASSETS/hooks/"*.sh; do
    name="$(basename "$f")"
    copy_safe "$f" "$TARGET/hooks/$name"
    do_or_dry chmod +x "$TARGET/hooks/$name"
  done
fi

# 4. Commands.
if [ $SKIP_COMMANDS -eq 1 ]; then
  say "skipping slash commands (--skip-commands)"
else
  say "installing slash commands"
  for f in "$ASSETS/commands/"*.md; do
    name="$(basename "$f")"
    copy_safe "$f" "$TARGET/commands/$name"
  done
fi

# 5. Memory templates — user scope only (memory is per-user by design).
if [ "$SCOPE" != "user" ]; then
  say "skipping memory (project scope; memory is per-user)"
elif [ $SKIP_MEMORY -eq 1 ]; then
  say "skipping memory (--skip-memory)"
else
  say "installing memory templates"
  for f in "$ASSETS/memory/"*.tmpl; do
    name="$(basename "$f" .tmpl)"
    copy_safe "$f" "$MEMORY_DIR/$name"
  done
fi

# 6. Patch settings.json — add env var + hooks blocks if missing.
if [ $SKIP_SETTINGS -eq 1 ]; then
  say "skipping settings.json (--skip-settings)"
else
  say "patching settings.json"
  SETTINGS="$TARGET/settings.json"
  if [ ! -f "$SETTINGS" ]; then
    if [ $DRY -eq 1 ]; then
      echo "  [dry-run] would create empty $SETTINGS"
    else
      printf '{}\n' > "$SETTINGS"
    fi
  fi
  if [ $DRY -eq 0 ]; then
    SETTINGS="$SETTINGS" SCOPE="$SCOPE" HOOK_CMD_BASE="$HOOK_CMD_BASE" python3 - <<'PY'
import json, os
p = os.environ["SETTINGS"]
scope = os.environ["SCOPE"]
base = os.environ["HOOK_CMD_BASE"]

with open(p) as f:
    s = json.load(f)

changed = False

# CLAUDE_CODE_AUTO_COMPACT_WINDOW only makes sense at user scope (it's a
# session-wide knob). At project scope, leave the env block alone — projects
# shouldn't override the user's compact window.
if scope == "user":
    env = s.setdefault("env", {})
    if env.get("CLAUDE_CODE_AUTO_COMPACT_WINDOW") != "400000":
        env["CLAUDE_CODE_AUTO_COMPACT_WINDOW"] = "400000"
        changed = True

hooks = s.setdefault("hooks", {})

OUR_HOOKS = [
    ("PreToolUse",  "Bash",       f"{base}/block-force-push.sh"),
    ("PostToolUse", "Write|Edit", f"{base}/format-on-edit.sh"),
    ("PostCompact",  None,        f"{base}/post-compact-reinject.sh"),
    ("Stop",         None,        f"{base}/verify-before-stop.sh"),
]

def ensure_hook(event, matcher, cmd):
    blocks = hooks.setdefault(event, [])
    for b in blocks:
        if b.get("matcher") == matcher:
            for h in b.get("hooks", []):
                if h.get("command") == cmd:
                    return False
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

# Atomic write: tmp file in the same dir, then rename. Avoids leaving an
# empty/partial settings.json if the process is interrupted mid-write —
# Claude Code refuses to load invalid JSON.
tmp = p + ".tmp"
with open(tmp, "w") as f:
    json.dump(s, f, indent=2)
    f.write("\n")
os.replace(tmp, p)
print("  settings.json updated" if changed else "  settings.json already current")
PY
  else
    echo "  [dry-run] would patch $SETTINGS with $([ "$SCOPE" = user ] && echo 'env + ')4 hooks"
  fi
fi

echo
say "done"
echo
echo "Next steps:"
if [ "$SCOPE" = "user" ]; then
  echo "  1. Edit $TARGET/CLAUDE.md — fill in the 'Stack signals' section."
  echo "  2. Edit $MEMORY_DIR/user_role.md — replace placeholders with your actual context."
else
  echo "  1. Review $(dirname "$TARGET")/CLAUDE.md (or merge with your existing one)."
  echo "  2. Decide whether to commit $TARGET/settings.json (shared) or move the hook block"
  echo "     to $TARGET/settings.local.json (personal)."
fi
echo "  3. Restart Claude Code (or open a new session) — hooks load on session start."
echo "  4. Optional: run scripts/snapshot.sh to mirror $TARGET into a private git repo"
echo "     and use scripts/audit-prompt.md to schedule a monthly remote audit."
