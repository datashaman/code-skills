#!/usr/bin/env bash
# Status reporter for the harness skill. Read-only.
# Reports for each surface: installed (matches template) / modified / missing.

set -u

SKILL_DIR="${SKILL_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
ASSETS="$SKILL_DIR/assets"
HOME_CLAUDE="$HOME/.claude"
USER_PROJECT_KEY="${USER_PROJECT_KEY:-$(printf '%s' "$HOME" | tr '/' '-')}"
MEMORY_DIR="$HOME_CLAUDE/projects/$USER_PROJECT_KEY/memory"

[ -d "$ASSETS" ] || { echo "error: $ASSETS not found" >&2; exit 1; }

green() { printf '\033[32m%s\033[0m' "$1"; }
yellow() { printf '\033[33m%s\033[0m' "$1"; }
red() { printf '\033[31m%s\033[0m' "$1"; }
dim() { printf '\033[90m%s\033[0m' "$1"; }

# Don't colourise if not a TTY.
if ! [ -t 1 ]; then
  green() { printf '%s' "$1"; }
  yellow() { printf '%s' "$1"; }
  red() { printf '%s' "$1"; }
  dim() { printf '%s' "$1"; }
fi

# Portable sha256: prefer sha256sum (Linux), then shasum (macOS), then python3.
# Returns non-zero if no hashing tool is available — callers must check.
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

# Pad the *uncoloured* label to width 12, then colour it.
fmt_label() { printf '%s' "$(printf '%-12s' "$1")" | awk -v c="$2" '{print c$0}' ; }

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

echo "harness status — HOME = $HOME"
echo

echo "CLAUDE.md"
report "$HOME_CLAUDE/CLAUDE.md" "$ASSETS/CLAUDE.md.tmpl" "CLAUDE.md"

echo
echo "hooks"
for f in "$ASSETS/hooks/"*.sh; do
  name="$(basename "$f")"
  report "$HOME_CLAUDE/hooks/$name" "$f" "$name"
done

echo
echo "commands"
for f in "$ASSETS/commands/"*.md; do
  name="$(basename "$f")"
  report "$HOME_CLAUDE/commands/$name" "$f" "$name"
done

echo
echo "memory"
for f in "$ASSETS/memory/"*.tmpl; do
  name="$(basename "$f" .tmpl)"
  report "$MEMORY_DIR/$name" "$f" "$name"
done

echo
echo "settings.json"
SETTINGS="$HOME_CLAUDE/settings.json"
if [ ! -f "$SETTINGS" ]; then
  printf '  %s no settings.json\n' "$(red 'missing     ')"
else
  SETTINGS="$SETTINGS" python3 - <<'PY'
import json, sys, os

p = os.environ["SETTINGS"]
with open(p) as f:
    s = json.load(f)

# settings.json stores "~/.claude/..." literally; that's what install.sh writes
# and what Claude Code expands at hook-execution time.
OUR_CMDS = {
    "PreToolUse":  "~/.claude/hooks/block-force-push.sh",
    "PostToolUse": "~/.claude/hooks/format-on-edit.sh",
    "PostCompact": "~/.claude/hooks/post-compact-reinject.sh",
    "Stop":        "~/.claude/hooks/verify-before-stop.sh",
}

is_tty = sys.stdout.isatty()
def green(s): return f"\033[32m{s}\033[0m" if is_tty else s
def red(s):   return f"\033[31m{s}\033[0m" if is_tty else s
def dim(s):   return f"\033[90m{s}\033[0m" if is_tty else s

# Pad uncoloured label to width 12, then colour.
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

env = s.get("env", {})
v = env.get("CLAUDE_CODE_AUTO_COMPACT_WINDOW")
if v is not None:
    print(f"  {fmt('set', green)} env.CLAUDE_CODE_AUTO_COMPACT_WINDOW = {dim(str(v))}")
else:
    print(f"  {fmt('missing', red)} env.CLAUDE_CODE_AUTO_COMPACT_WINDOW")
PY
fi

# Snapshot repo (optional).
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
