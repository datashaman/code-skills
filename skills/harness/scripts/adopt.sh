#!/usr/bin/env bash
# /harness adopt — retrofit harness into an existing project.
# Scaffolds a starter scripts/harness-check.sh — the project-side pass/fail
# gate that verify-before-stop.sh and /verify call — then prints the install
# command to run next. Project scope only.
#
# Usage:
#   bash adopt.sh                         # auto-detect project (CWD or $CLAUDE_PROJECT_DIR)
#   bash adopt.sh --target=PATH           # explicit project root
#   bash adopt.sh --dry-run               # show plan, change nothing
#   bash adopt.sh --force                 # overwrite an existing harness-check.sh
set -euo pipefail

DRY=0
FORCE=0
TARGET=""
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --force)   FORCE=1 ;;
    --target=*) TARGET="${arg#--target=}" ;;
    -h|--help)
      awk 'NR>1 { if (/^#/) { sub(/^# ?/, ""); print } else { exit } }' "${BASH_SOURCE[0]}"
      exit 0 ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

SKILL_DIR="${SKILL_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
TEMPLATE="$SKILL_DIR/assets/harness-check.sh.tmpl"
[ -f "$TEMPLATE" ] || { echo "error: template not found at $TEMPLATE" >&2; exit 1; }

[ -z "$TARGET" ] && TARGET="${CLAUDE_PROJECT_DIR:-$PWD}"

# Refuse to write into $HOME — adopt is for project scope only. User scope
# already has its own gate (~/.claude/CLAUDE.md says how to run /verify).
if [ "$TARGET" = "$HOME" ]; then
  echo "error: refusing to adopt into \$HOME — adopt is for project scope." >&2
  echo "       cd into a project, or pass --target=PATH." >&2
  exit 2
fi

CHECK_PATH="$TARGET/scripts/harness-check.sh"

# Detect what's already there so the preflight is honest.
have_claude_md=no;        [ -f "$TARGET/CLAUDE.md" ]              && have_claude_md=yes
have_claude_dir=no;       [ -d "$TARGET/.claude" ]                && have_claude_dir=yes
have_check=no;            [ -e "$CHECK_PATH" ]                    && have_check=yes
have_settings=no;         [ -f "$TARGET/.claude/settings.json" ]  && have_settings=yes

stack_bullets=""
if command -v python3 >/dev/null 2>&1 && [ -x "$SKILL_DIR/scripts/_detect_stack.py" ]; then
  stack_bullets="$("$SKILL_DIR/scripts/_detect_stack.py" "$TARGET" 2>/dev/null || true)"
fi

cat <<EOF
══════════════════════════════════════════════════════════════════════
  /harness adopt — retrofit into existing project
══════════════════════════════════════════════════════════════════════
  Project root: $TARGET

  Detected:
    CLAUDE.md present:                 $have_claude_md
    .claude/ present:                  $have_claude_dir
    .claude/settings.json present:     $have_settings
    scripts/harness-check.sh present:  $have_check
EOF

if [ -n "$stack_bullets" ]; then
  echo
  echo "  Stack signals:"
  # shellcheck disable=SC2001  # the search uses a newline; ${//} is awkward here
  echo "$stack_bullets" | sed 's/^/    /'
fi

cat <<EOF

  Plan (two layers, both optional — pick what you want):

  Layer 1 — user-scope guardrails into the project (this script):
    • Scaffold scripts/harness-check.sh — the project pass/fail gate that
      verify-before-stop.sh + /verify call. Stack-aware starter; edit it
      after this script runs to keep only the sensors you want.
    • Then run:
        bash $SKILL_DIR/scripts/install.sh --scope=project
      → installs 4 hooks (block-force-push, format-on-edit,
        post-compact-reinject, verify-before-stop), /verify, /plan, and a
        project CLAUDE.md (skipped if one exists; --force overrides).

  Layer 2 — deeper project harness (optional, separate repo):
    • https://github.com/datashaman/harness-template
    • Adds policy YAMLs, harness/grades.yml, .skip ledger, stack profiles.
    • Copy the spine when you've outgrown the starter.

  Pointers:
    • Dry-run any step:        bash $SKILL_DIR/scripts/install.sh --dry-run
    • Pick & choose surfaces:  --include=hooks,commands  (or --skip-*)
    • Uninstall:               bash $SKILL_DIR/scripts/uninstall.sh
    • Diagnose:                bash $SKILL_DIR/scripts/doctor.sh

EOF

if [ "$have_check" = "yes" ] && [ $FORCE -eq 0 ]; then
  echo "→ scripts/harness-check.sh already exists — keeping (--force to overwrite)."
  echo
  echo "Next: bash $SKILL_DIR/scripts/install.sh --scope=project"
  exit 0
fi

if [ $DRY -eq 1 ]; then
  echo "[dry-run] would write $CHECK_PATH"
  exit 0
fi

mkdir -p "$(dirname "$CHECK_PATH")"
cp "$TEMPLATE" "$CHECK_PATH"
chmod +x "$CHECK_PATH"
echo "→ wrote $CHECK_PATH (chmod +x)"
echo
echo "Next: bash $SKILL_DIR/scripts/install.sh --scope=project"
echo "Then: edit scripts/harness-check.sh, restart Claude Code, run /verify"
