#!/usr/bin/env bash
# Update an existing harness install to the current skill's templates.
# Smarter than `install --force`: never silently overwrites a customised file.
# For each surface compares installed vs template via sha256 and:
#   - identical → re-install (no-op cosmetically)
#   - missing   → install
#   - modified  → print diff and SKIP, unless --merge or --force
#
# Usage:
#   bash update.sh                       # auto-detect scope; show diffs for modified files
#   bash update.sh --scope=user|project  # force scope
#   bash update.sh --target=PATH         # explicit .claude/ target
#   bash update.sh --dry-run             # show plan, change nothing
#   bash update.sh --force               # overwrite ALL files including modified ones
#   bash update.sh --merge               # for modified files, write template to <file>.new alongside
#                                        # the original so the user can diff/merge interactively

set -euo pipefail

DRY=0
FORCE=0
MERGE=0
SCOPE=""
TARGET=""
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --force) FORCE=1 ;;
    --merge) MERGE=1 ;;
    --scope=user) SCOPE=user ;;
    --scope=project) SCOPE=project ;;
    --scope=*) echo "invalid --scope: $arg" >&2; exit 2 ;;
    --target=*) TARGET="${arg#--target=}" ;;
    -h|--help)
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
      dirname "$d"; return 0
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
    echo "error: cannot auto-detect scope; pass --scope or --target" >&2
    exit 2
  fi
fi
[ -z "$SCOPE" ] && { [ "$TARGET" = "$HOME/.claude" ] && SCOPE=user || SCOPE=project; }

USER_PROJECT_KEY="${USER_PROJECT_KEY:-$(printf '%s' "$HOME" | tr '/' '-')}"
MEMORY_DIR="$HOME/.claude/projects/$USER_PROJECT_KEY/memory"
if [ "$SCOPE" = "user" ]; then
  CLAUDE_MD_PATH="$TARGET/CLAUDE.md"
else
  CLAUDE_MD_PATH="$(dirname "$TARGET")/CLAUDE.md"
fi

say() { echo "→ $*"; }

sha256() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | awk '{print $1}'
  elif command -v python3 >/dev/null 2>&1; then python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$1"
  else return 1; fi
}

# update_one <installed> <template>
update_one() {
  local installed="$1" template="$2"
  local action

  if [ ! -e "$installed" ]; then
    action="missing → install"
  else
    local lhs rhs
    lhs="$(sha256 "$installed" 2>/dev/null || echo)"
    rhs="$(sha256 "$template"  2>/dev/null || echo)"
    if [ -z "$lhs" ] || [ -z "$rhs" ]; then
      action="cannot hash — skipping"
    elif [ "$lhs" = "$rhs" ]; then
      action="identical — no-op"
    elif [ $FORCE -eq 1 ]; then
      action="modified → OVERWRITE (--force)"
    elif [ $MERGE -eq 1 ]; then
      action="modified → write template to ${installed}.new (--merge)"
    else
      action="modified → SKIP (review and re-run with --force or --merge)"
    fi
  fi

  printf '  [%s] %s\n' "$action" "$installed"

  [ $DRY -eq 1 ] && return 0

  case "$action" in
    "missing → install"|"modified → OVERWRITE (--force)")
      mkdir -p "$(dirname "$installed")"
      cp "$template" "$installed"
      ;;
    "identical — no-op")
      : # genuinely a no-op; don't touch the file's mtime.
      ;;
    "modified → write template to "*)
      cp "$template" "${installed}.new"
      printf '         diff vs new template:\n'
      diff -u "$installed" "${installed}.new" 2>/dev/null | sed 's/^/         /' | head -20 || true
      ;;
    "modified → SKIP"*)
      printf '         diff vs new template:\n'
      diff -u "$installed" "$template" 2>/dev/null | sed 's/^/         /' | head -20 || true
      ;;
  esac
}

cat <<EOF
══════════════════════════════════════════════════════════════════════
  harness update — preflight
══════════════════════════════════════════════════════════════════════
  Scope:  $SCOPE
  Target: $TARGET

  Checks every harness file: identical / modified / missing.
  Default: re-install identical and missing files; skip modified files
  and print their diffs.

  Flags:
    --force   overwrite modified files (you'll lose customisations)
    --merge   write new template to <file>.new alongside (review/merge by hand)
    --dry-run plan only

EOF
[ $DRY -eq 1 ] && say "DRY RUN — no changes will be written"
say "scope: $SCOPE  target: $TARGET"

# 1. CLAUDE.md
say "CLAUDE.md"
update_one "$CLAUDE_MD_PATH" "$ASSETS/CLAUDE.md.tmpl"

# 2. Hooks
say "hooks"
for f in "$ASSETS/hooks/"*.sh; do
  name="$(basename "$f")"
  update_one "$TARGET/hooks/$name" "$f"
done
[ $DRY -eq 0 ] && for f in "$TARGET/hooks/"*.sh; do
  [ -f "$f" ] && chmod +x "$f"
done

# 3. Commands
say "commands"
for f in "$ASSETS/commands/"*.md; do
  name="$(basename "$f")"
  update_one "$TARGET/commands/$name" "$f"
done

# 4. Memory (user scope only).
if [ "$SCOPE" = "user" ]; then
  say "memory templates"
  for f in "$ASSETS/memory/"*.tmpl; do
    name="$(basename "$f" .tmpl)"
    update_one "$MEMORY_DIR/$name" "$f"
  done
fi

echo
say "done"
echo
echo "settings.json patches are not auto-updated by this script — re-run install.sh"
echo "if hook entries or env need to be (re)added."
