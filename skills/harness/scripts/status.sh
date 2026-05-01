#!/usr/bin/env bash
# Status reporter for the harness skill. Read-only.
# Reports for each surface: installed (matches template) / modified / missing.
#
# Scope-agnostic: same auto-detection as install.sh / uninstall.sh.
#   bash status.sh                # auto-detect
#   bash status.sh --scope=user   # force user scope
#   bash status.sh --scope=project
#   bash status.sh --target=PATH  # explicit .claude/ path

set -u

SCOPE=""
TARGET=""
for arg in "$@"; do
  case "$arg" in
    --scope=user) SCOPE=user ;;
    --scope=project) SCOPE=project ;;
    --scope=*) echo "invalid --scope (use user|project): $arg" >&2; exit 2 ;;
    --target=*) TARGET="${arg#--target=}" ;;
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
if [ "$SCOPE" = "user" ]; then
  HOOK_CMD_BASE='~/.claude/hooks'
  CLAUDE_MD_PATH="$TARGET/CLAUDE.md"
else
  HOOK_CMD_BASE='.claude/hooks'
  CLAUDE_MD_PATH="$(dirname "$TARGET")/CLAUDE.md"
fi

green() { printf '\033[32m%s\033[0m' "$1"; }
yellow() { printf '\033[33m%s\033[0m' "$1"; }
red() { printf '\033[31m%s\033[0m' "$1"; }
dim() { printf '\033[90m%s\033[0m' "$1"; }
if ! [ -t 1 ]; then
  green() { printf '%s' "$1"; }
  yellow() { printf '%s' "$1"; }
  red() { printf '%s' "$1"; }
  dim() { printf '%s' "$1"; }
fi

sha() {
  local f="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$f" 2>/dev/null | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$f" 2>/dev/null | awk '{print $1}'
  elif command -v python3 >/dev/null 2>&1; then
    python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$f" 2>/dev/null
  else
    return 1
  fi
}

report() {
  local installed="$1" template="$2" label="$3"
  local lhs rhs status
  if [ ! -e "$installed" ]; then
    status="$(red missing)    "
  elif [ -f "$template" ]; then
    if lhs="$(sha "$installed")" && [ -n "$lhs" ] \
       && rhs="$(sha "$template")" && [ -n "$rhs" ]; then
      if [ "$lhs" = "$rhs" ]; then
        status="$(green installed)  "
      else
        status="$(yellow modified)   "
      fi
    else
      status="$(red 'cannot hash') "
    fi
  else
    status="$(green present)    "
  fi
  printf '  %s %s  %s\n' "$status" "$label" "$(dim "$installed")"
}

echo "harness status — scope=$SCOPE target=$TARGET"
echo

echo "CLAUDE.md"
report "$CLAUDE_MD_PATH" "$ASSETS/CLAUDE.md.tmpl" "CLAUDE.md"

echo
echo "hooks"
for f in "$ASSETS/hooks/"*.sh; do
  name="$(basename "$f")"
  report "$TARGET/hooks/$name" "$f" "$name"
done

echo
echo "commands"
for f in "$ASSETS/commands/"*.md; do
  name="$(basename "$f")"
  report "$TARGET/commands/$name" "$f" "$name"
done

if [ "$SCOPE" = "user" ]; then
  echo
  echo "memory (user scope)"
  for f in "$ASSETS/memory/"*.tmpl; do
    name="$(basename "$f" .tmpl)"
    report "$MEMORY_DIR/$name" "$f" "$name"
  done
fi

echo
echo "settings.json"
SETTINGS="$TARGET/settings.json"
if [ ! -f "$SETTINGS" ]; then
  printf '  %s no settings.json\n' "$(red 'missing     ')"
else
  SETTINGS="$SETTINGS" SCOPE="$SCOPE" HOOK_CMD_BASE="$HOOK_CMD_BASE" python3 - <<'PY'
import json, sys, os

p = os.environ["SETTINGS"]
scope = os.environ["SCOPE"]
base = os.environ["HOOK_CMD_BASE"]
with open(p) as f:
    s = json.load(f)

OUR_CMDS = {
    "PreToolUse":  f"{base}/block-force-push.sh",
    "PostToolUse": f"{base}/format-on-edit.sh",
    "PostCompact": f"{base}/post-compact-reinject.sh",
    "Stop":        f"{base}/verify-before-stop.sh",
}

is_tty = sys.stdout.isatty()
def green(s): return f"\033[32m{s}\033[0m" if is_tty else s
def red(s):   return f"\033[31m{s}\033[0m" if is_tty else s
def dim(s):   return f"\033[90m{s}\033[0m" if is_tty else s

def fmt(label, colour):
    return colour(label) + (" " * max(0, 12 - len(label)))

hooks = s.get("hooks", {})
for event, cmd in OUR_CMDS.items():
    found = any(
        h.get("command") == cmd
        for b in hooks.get(event, [])
        for h in b.get("hooks", [])
    )
    label = fmt("wired", green) if found else fmt("missing", red)
    print(f"  {label} {event} -> {dim(cmd)}")

# Env var only meaningful at user scope.
if scope == "user":
    env = s.get("env", {})
    v = env.get("CLAUDE_CODE_AUTO_COMPACT_WINDOW")
    if v is not None:
        print(f"  {fmt('set', green)} env.CLAUDE_CODE_AUTO_COMPACT_WINDOW = {dim(str(v))}")
    else:
        print(f"  {fmt('missing', red)} env.CLAUDE_CODE_AUTO_COMPACT_WINDOW")
PY
fi

if [ -n "${SNAPSHOT_REPO:-}" ] && [ -d "$SNAPSHOT_REPO/.git" ]; then
  echo
  echo "snapshot ($SNAPSHOT_REPO)"
  cd "$SNAPSHOT_REPO"
  last_commit="$(git log -1 --format='%cr  %s' 2>/dev/null || echo unknown)"
  ahead="$(git rev-list --count '@{upstream}..HEAD' 2>/dev/null || echo '?')"
  behind="$(git rev-list --count 'HEAD..@{upstream}' 2>/dev/null || echo '?')"
  printf '  %s  last commit: %s\n' "$(dim '·')" "$last_commit"
  printf '  %s  ahead/behind origin: %s/%s\n' "$(dim '·')" "$ahead" "$behind"
fi

echo
