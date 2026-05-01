#!/usr/bin/env bash
# Diagnose a harness install end-to-end.
# Combines status + sanity checks: hashing tool, write permissions, hook script
# is executable AND fires correctly when invoked, no conflicting hook entries
# pointing elsewhere, settings.json is parseable, memory dir exists at user scope.
#
# Usage:
#   bash doctor.sh                       # auto-detect scope
#   bash doctor.sh --scope=user|project
#   bash doctor.sh --target=PATH

set -u

SCOPE=""
TARGET=""
for arg in "$@"; do
  case "$arg" in
    --scope=user) SCOPE=user ;;
    --scope=project) SCOPE=project ;;
    --scope=*) echo "invalid --scope: $arg" >&2; exit 2 ;;
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
    [ "$(basename "$d")" = ".claude" ] && { dirname "$d"; return 0; }
    d="$(dirname "$d")"
  done
  return 1
}

if [ -n "$TARGET" ]; then :
elif [ "$SCOPE" = "user" ]; then TARGET="$HOME/.claude"
elif [ "$SCOPE" = "project" ]; then TARGET="${CLAUDE_PROJECT_DIR:-$PWD}/.claude"
else
  if scope_root="$(detect_scope_root)"; then
    TARGET="$scope_root/.claude"
    [ "$scope_root" = "$HOME" ] && SCOPE=user || SCOPE=project
  else
    echo "error: cannot auto-detect scope; pass --scope or --target" >&2
    exit 2
  fi
fi
[ -z "$SCOPE" ] && { [ "$TARGET" = "$HOME/.claude" ] && SCOPE=user || SCOPE=project; }

green()  { printf '\033[32m%s\033[0m' "$1"; }
yellow() { printf '\033[33m%s\033[0m' "$1"; }
red()    { printf '\033[31m%s\033[0m' "$1"; }
if ! [ -t 1 ]; then green() { printf '%s' "$1"; }; yellow() { printf '%s' "$1"; }; red() { printf '%s' "$1"; }; fi

PASS=0; WARN=0; FAIL=0
ok()   { printf '  [%s]    %s\n' "$(green '  OK  ')" "$*"; PASS=$((PASS+1)); }
warn() { printf '  [%s]  %s\n' "$(yellow ' WARN ')" "$*"; WARN=$((WARN+1)); }
bad()  { printf '  [%s]  %s\n' "$(red ' FAIL ')" "$*"; FAIL=$((FAIL+1)); }

echo "harness doctor — scope=$SCOPE target=$TARGET"
echo

# 1. Hashing tool available.
if command -v sha256sum >/dev/null 2>&1 || command -v shasum >/dev/null 2>&1 || command -v python3 >/dev/null 2>&1; then
  ok "sha256 tool available"
else
  bad "no sha256 tool (need sha256sum, shasum, or python3) — content-match checks won't work"
fi

# 2. Target writable.
if [ -w "$TARGET" ] || [ ! -e "$TARGET" ]; then
  ok "target dir is writable: $TARGET"
else
  bad "target dir is not writable: $TARGET"
fi

# 3. settings.json parseable.
SETTINGS="$TARGET/settings.json"
if [ -f "$SETTINGS" ]; then
  if python3 -m json.tool < "$SETTINGS" >/dev/null 2>&1; then
    ok "settings.json is valid JSON"
  else
    bad "settings.json is not valid JSON — Claude Code will refuse to load it"
  fi
else
  warn "no settings.json at $SETTINGS — install.sh will create one"
fi

# 4. Hook scripts exist and are executable; foreign hooks pointing elsewhere flagged.
say_hook() { printf '       %s\n' "$1"; }
if [ -f "$SETTINGS" ]; then
  for name in block-force-push.sh format-on-edit.sh post-compact-reinject.sh verify-before-stop.sh; do
    f="$TARGET/hooks/$name"
    if [ -x "$f" ]; then
      ok "hook executable: $name"
    elif [ -e "$f" ]; then
      warn "hook not executable (need chmod +x): $f"
    else
      warn "hook missing on disk: $f"
    fi
  done

  # Check for hook entries in settings.json that point at *unexpected* paths.
  SETTINGS="$SETTINGS" python3 - <<'PY' || true
import json, os, sys
p = os.environ["SETTINGS"]
try:
    s = json.load(open(p))
except Exception as e:
    print(f"  [ FAIL ]  settings.json parse error: {e}")
    sys.exit(0)
hooks = s.get("hooks", {})
expected_names = {
    "block-force-push.sh", "format-on-edit.sh",
    "post-compact-reinject.sh", "verify-before-stop.sh",
}
seen = set()
for event, blocks in hooks.items():
    for b in blocks:
        for h in b.get("hooks", []):
            cmd = h.get("command", "")
            for n in expected_names:
                if n in cmd:
                    seen.add(n)
                    if "harness" not in cmd and ".claude/hooks/" not in cmd:
                        print(f"  [ WARN ]  hook entry '{event}' for {n} points at unexpected path: {cmd}")
missing = expected_names - seen
if missing:
    for n in sorted(missing):
        print(f"  [ WARN ]  no settings.json entry references {n} — hook won't fire")
else:
    print(f"  [  OK  ]  all 4 hooks wired in settings.json")
PY
fi

# 5. Hook smoke-test: invoke block-force-push with a known-bad command.
HOOK="$TARGET/hooks/block-force-push.sh"
if [ -x "$HOOK" ]; then
  if echo '{"tool_name":"Bash","tool_input":{"command":"git push --force origin main"}}' \
     | "$HOOK" >/dev/null 2>&1; then
    bad "block-force-push.sh did NOT block 'git push --force origin main' (should exit 2)"
  else
    rc=$?
    if [ $rc -eq 2 ]; then
      ok "block-force-push.sh fires correctly on dangerous input"
    else
      warn "block-force-push.sh exited $rc (expected 2); behavior unclear"
    fi
  fi
fi

# 6. Memory dir at user scope.
if [ "$SCOPE" = "user" ]; then
  USER_PROJECT_KEY="${USER_PROJECT_KEY:-$(printf '%s' "$HOME" | tr '/' '-')}"
  MEMORY_DIR="$HOME/.claude/projects/$USER_PROJECT_KEY/memory"
  if [ -d "$MEMORY_DIR" ]; then
    if [ -f "$MEMORY_DIR/MEMORY.md" ]; then
      ok "memory store populated at $MEMORY_DIR"
    else
      warn "memory dir exists but no MEMORY.md index"
    fi
  else
    warn "no memory dir at $MEMORY_DIR — run install.sh"
  fi
fi

# 7. CLAUDE.md present + Stack signals filled.
if [ "$SCOPE" = "user" ]; then
  CLAUDE_MD_PATH="$TARGET/CLAUDE.md"
else
  CLAUDE_MD_PATH="$(dirname "$TARGET")/CLAUDE.md"
fi
if [ -f "$CLAUDE_MD_PATH" ]; then
  if grep -q '## Stack signals' "$CLAUDE_MD_PATH" 2>/dev/null; then
    if grep -A1 '^## Stack signals' "$CLAUDE_MD_PATH" | grep -q 'Replace with your default'; then
      warn "CLAUDE.md still has placeholder Stack signals — fill it in"
    else
      ok "CLAUDE.md present and Stack signals look filled"
    fi
  else
    ok "CLAUDE.md present (no Stack signals heading — custom format)"
  fi
else
  warn "no CLAUDE.md at $CLAUDE_MD_PATH"
fi

# 8. Snapshot repo (if env points at one) — last commit recency.
if [ -n "${SNAPSHOT_REPO:-}" ] && [ -d "$SNAPSHOT_REPO/.git" ]; then
  if [ -d "$SNAPSHOT_REPO/.git" ]; then
    cd "$SNAPSHOT_REPO" || true
    days_old=$(($(date +%s) - $(git log -1 --format=%ct 2>/dev/null || echo 0)))
    days_old=$((days_old / 86400))
    if [ "$days_old" -gt 60 ]; then
      warn "snapshot repo last commit is $days_old days old — run snapshot.sh"
    else
      ok "snapshot repo last commit: $days_old days ago"
    fi
  fi
fi

echo
echo "Summary: $(green "$PASS pass"), $(yellow "$WARN warn"), $(red "$FAIL fail")"
[ $FAIL -gt 0 ] && exit 1 || exit 0
