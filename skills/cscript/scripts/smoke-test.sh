#!/usr/bin/env bash
# Smoke test for the cscript dispatcher. Exercises register/list/which/
# state-dir/show/run/rm in an isolated data directory and exits non-zero
# on the first failure.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
CS="$HERE/cscript"
CSCRIPT_DATA_DIR="$(mktemp -d)"
export CSCRIPT_DATA_DIR
TMP="$(mktemp -d)"
trap 'rm -rf "$CSCRIPT_DATA_DIR" "$TMP"' EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "ok: $*"; }

# 1. Empty index
out=$("$CS" list)
[[ "$out" == *"No scripts registered"* ]] || fail "empty list message"
pass "empty list"

if "$CS" which "nothing matches" >/dev/null 2>&1; then
  fail "which on empty index should exit non-zero"
fi
pass "which on empty index returns non-zero"

# 2. Register a script
cat > "$TMP/hello.sh" <<'EOF'
#!/usr/bin/env bash
echo "hello $*"
EOF
chmod +x "$TMP/hello.sh"

"$CS" register \
  --source "$TMP/hello.sh" \
  --name hello \
  --description "say hello (smoke test)" \
  --language bash \
  --read-only >/dev/null
pass "register"

out=$("$CS" list)
[[ "$out" == *"hello"*"[ro]"* ]] || fail "list should show hello with [ro] tag"
pass "list shows registered script"

out=$("$CS" which "hello")
[[ "$out" == *"hello"* ]] || fail "which should match hello"
pass "which finds match"

# 3. State directory
state_dir=$("$CS" state-dir hello)
[[ -d "$state_dir" ]] || fail "state-dir should create the directory"
pass "state-dir creates and prints path"

# 4. Show
out=$("$CS" show hello)
[[ "$out" == *"name:"*"hello"* ]] || fail "show should print metadata header"
[[ "$out" == *"echo \"hello"* ]] || fail "show should print source"
pass "show"

# 5. Run (read-only script; no TTY needed since --read-only skips confirm)
# Subshell so os.execv only replaces the subshell process.
out=$( "$CS" run hello world )
[[ "$out" == "hello world" ]] || fail "run output mismatch: '$out'"
pass "run executes and forwards args"

# 6. Re-register archives prior version
cat > "$TMP/hello.sh" <<'EOF'
#!/usr/bin/env bash
echo "hello v2 $*"
EOF
chmod +x "$TMP/hello.sh"
"$CS" register \
  --source "$TMP/hello.sh" \
  --name hello \
  --description "say hello v2" \
  --language bash \
  --read-only >/dev/null
out=$( "$CS" run hello world )
[[ "$out" == "hello v2 world" ]] || fail "re-registered script not active"
archived=$(find "$CSCRIPT_DATA_DIR/scripts/.archive" -name 'hello.*' | wc -l | tr -d ' ')
[[ "$archived" -ge 1 ]] || fail "prior version should be archived"
pass "re-register archives prior version"

# 7. Ambiguous resolve
cat > "$TMP/hello-again.sh" <<'EOF'
#!/usr/bin/env bash
echo "again"
EOF
chmod +x "$TMP/hello-again.sh"
"$CS" register \
  --source "$TMP/hello-again.sh" \
  --name hello-again \
  --description "another hello" \
  --language bash \
  --read-only >/dev/null

if "$CS" show hell >/dev/null 2>&1; then
  fail "ambiguous show 'hell' should fail"
fi
err=$("$CS" show hell 2>&1 || true)
[[ "$err" == *"ambiguous"* ]] || fail "ambiguous error message missing"
pass "ambiguous match prints candidates and exits non-zero"

# 8. rm cleans state dir
"$CS" rm hello >/dev/null
[[ ! -d "$state_dir" ]] || fail "rm should remove the state directory"
out=$("$CS" list)
[[ "$out" != *"say hello v2"* ]] || fail "list should not contain removed script"
[[ "$out" == *"hello-again"* ]] || fail "list should still contain hello-again"
pass "rm archives script and removes state dir"

# 9. version subcommand
out=$("$CS" version)
[[ -n "$out" ]] || fail "version should print something"
pass "version prints"

# 10. mine: which calls are logged and mined
# Generate three misses (same effective query) and one hit, then mine.
"$CS" which "convert pdf to html for archiving" >/dev/null 2>&1 || true
"$CS" which "convert pdf to html for archiving" >/dev/null 2>&1 || true
"$CS" which "convert pdf to html for archiving" >/dev/null 2>&1 || true
"$CS" which "hello-again" >/dev/null 2>&1 || true

[[ -f "$CSCRIPT_DATA_DIR/which.log" ]] || fail "which.log should exist after which calls"
log_lines=$(wc -l < "$CSCRIPT_DATA_DIR/which.log" | tr -d ' ')
[[ "$log_lines" -ge 4 ]] || fail "which.log should have at least 4 entries, got $log_lines"
pass "which appends to invocation log"

out=$("$CS" mine)
[[ "$out" == *"[3x]"* ]] || fail "mine should show 3x repeat for pdf-to-html query: '$out'"
[[ "$out" == *"convert pdf to html"* ]] || fail "mine should surface the repeated query"
[[ "$out" != *"hello-again"* ]] || fail "mine should exclude hits"
pass "mine ranks repeated misses"

# 11. mine: empty case message
empty_dir="$(mktemp -d)"
out=$(CSCRIPT_DATA_DIR="$empty_dir" "$CS" mine 2>&1 || true)
[[ "$out" == *"No \`cscript which\` history yet"* ]] || fail "mine empty message missing: '$out'"
rm -rf "$empty_dir"
pass "mine handles empty log"

echo
echo "All checks passed."
