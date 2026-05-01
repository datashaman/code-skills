#!/usr/bin/env bash
# PreToolUse hook for Bash. Block destructive operations.
# Reads JSON on stdin: {tool_name, tool_input: {command, ...}, ...}
# Exit 2 = block + tell model why. Exit 0 = allow.
#
# Matching strategy: split the command on shell separators (; && || | newline),
# then for each *segment*, look at its leading words. This avoids false positives
# from strings inside `echo`, `printf`, comments, heredocs, etc.

set -u
input="$(cat)"
cmd="$(printf '%s' "$input" | python3 -c 'import json,sys
try:
  d=json.load(sys.stdin); print(d.get("tool_input",{}).get("command",""))
except Exception: pass' 2>/dev/null || true)"

[ -z "$cmd" ] && exit 0

block() {
  printf 'BLOCKED by ~/.claude/hooks/block-force-push.sh\nSegment: %s\nReason: %s\nIf you genuinely need this, ask the user first.\n' "$1" "$2" >&2
  exit 2
}

# Split into segments on ; && || | & and newlines. Crude but enough.
segments="$(CLAUDE_HOOK_CMD="$cmd" python3 - <<'PY'
import os, re
src = os.environ.get("CLAUDE_HOOK_CMD","")
out = []
buf = []
i = 0
in_s = None
while i < len(src):
    c = src[i]
    if in_s:
        buf.append(c)
        if c == in_s and (i == 0 or src[i-1] != "\\"):
            in_s = None
    elif c in ("'", '"'):
        in_s = c
        buf.append(c)
    elif c in (";", "\n"):
        out.append("".join(buf)); buf = []
    elif c == "&" and i+1 < len(src) and src[i+1] == "&":
        out.append("".join(buf)); buf = []; i += 1
    elif c == "|" and i+1 < len(src) and src[i+1] == "|":
        out.append("".join(buf)); buf = []; i += 1
    elif c == "|":
        out.append("".join(buf)); buf = []
    else:
        buf.append(c)
    i += 1
out.append("".join(buf))
for seg in out:
    s = seg.strip()
    if s: print(s)
PY
)"

while IFS= read -r seg; do
  [ -z "$seg" ] && continue

  case "$seg" in
    echo*|printf*|cat*|"# "*|"#"*) continue ;;
  esac

  case "$seg" in *"--force-with-lease"*) continue ;; esac

  if echo "$seg" | grep -Eq '^[[:space:]]*git[[:space:]]+push[[:space:]].*(--force|[[:space:]]-f[[:space:]]).*[[:space:]](main|master|HEAD:main|HEAD:master)([[:space:]]|$)'; then
    block "$seg" "force-push to main/master"
  fi
  if echo "$seg" | grep -Eq '^[[:space:]]*git[[:space:]]+push[[:space:]].*(--force|[[:space:]]-f[[:space:]])'; then
    block "$seg" "force-push without --force-with-lease"
  fi
  if echo "$seg" | grep -Eq '^[[:space:]]*git[[:space:]]+reset[[:space:]]+--hard[[:space:]]+(origin|upstream)/'; then
    block "$seg" "hard reset to remote"
  fi
  if echo "$seg" | grep -Eq '^[[:space:]]*git[[:space:]]+(checkout|restore)[[:space:]]+\.[[:space:]]*$'; then
    block "$seg" "wholesale discard of working tree"
  fi
  # Force-delete branch — only block on protected names. Worktree workflows
  # rely on `git branch -D` for completed feature branches, so the rule has
  # to be specific. Block: main, master, develop, trunk, production, staging,
  # and any release/* or release-* branch.
  if echo "$seg" | grep -Eq '^[[:space:]]*git[[:space:]]+branch[[:space:]]+-D[[:space:]]+(main|master|develop|trunk|production|prod|staging|release[/-])'; then
    block "$seg" "force-delete protected branch"
  fi
  if echo "$seg" | grep -Eq '^[[:space:]]*git[[:space:]]+(commit|merge|push|rebase)[[:space:]].*--no-verify'; then
    block "$seg" "skipping git hooks (--no-verify)"
  fi
  # The \$HOME pattern matches the literal string "$HOME" in user shell commands.
  # Single quotes preserve the regex unchanged for grep — SC2016 is a false
  # positive here (we don't want shell to expand $HOME).
  # shellcheck disable=SC2016
  if echo "$seg" | grep -Eq '^[[:space:]]*rm[[:space:]]+(-[rRf]+[[:space:]]+)+(/|~|\$HOME|/\*|~/?\*)([[:space:]]|$)'; then
    block "$seg" "rm -rf on \$HOME or /"
  fi
  if echo "$seg" | grep -Eq '^[[:space:]]*git[[:space:]]+clean[[:space:]].*-f[dx]*[[:space:]]*$'; then
    block "$seg" "git clean -fd (destroys untracked work)"
  fi
  if echo "$seg" | grep -Eq '^[[:space:]]*chmod[[:space:]]+-R[[:space:]]+777'; then
    block "$seg" "chmod -R 777"
  fi
done <<< "$segments"

exit 0
