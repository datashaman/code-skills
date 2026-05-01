#!/usr/bin/env bash
# scripts/harness-check.sh — project pass/fail gate.
# Called by ~/.claude/hooks/verify-before-stop.sh and `/verify`.
# Returns non-zero on the first failed sensor.
#
# Customise the blocks below for your stack — uncomment, edit, or delete.
# Keep the script fast (under ~10s) so it can run on every Stop.
set -uo pipefail

step() {
  local label="$1"; shift
  echo "→ $label"
  if "$@"; then return 0; fi
  echo "❌ harness-check failed: $label" >&2
  exit 1
}

ran=0

# Node / JS / TS.
if [ -f package.json ]; then
  grep -q '"lint:check"'  package.json && { step "npm run lint:check"  npm run lint:check;  ran=1; }
  grep -q '"types:check"' package.json && { step "npm run types:check" npm run types:check; ran=1; }
  grep -q '"test"'        package.json && { step "npm test"            npm test;            ran=1; }
fi

# PHP / Laravel.
if [ -f composer.json ]; then
  grep -q '"lint:check"' composer.json && { step "composer lint:check" composer lint:check; ran=1; }
  [ -x ./vendor/bin/pint ] && { step "pint --test" ./vendor/bin/pint --test; ran=1; }
  [ -x ./vendor/bin/phpstan ] && { step "phpstan" ./vendor/bin/phpstan analyse --no-progress; ran=1; }
  [ -x ./vendor/bin/pest ] && { step "pest" ./vendor/bin/pest; ran=1; }
  [ -x ./vendor/bin/phpunit ] && [ ! -x ./vendor/bin/pest ] && { step "phpunit" ./vendor/bin/phpunit; ran=1; }
fi

# Shell — match CI: shellcheck every .sh under skills/harness, same exclusions.
if command -v shellcheck >/dev/null 2>&1 && \
   compgen -G "skills/harness/scripts/*.sh" >/dev/null; then
  step "shellcheck" shellcheck -e SC2155,SC2034 \
    skills/harness/scripts/*.sh \
    skills/harness/assets/hooks/*.sh
  ran=1
fi

# Python.
if [ -f pyproject.toml ]; then
  command -v ruff   >/dev/null 2>&1 && { step "ruff check" ruff check .; ran=1; }
  command -v mypy   >/dev/null 2>&1 && { step "mypy"       mypy .;       ran=1; }
  # pytest exit 5 = no tests collected; treat as PASS until the suite exists.
  command -v pytest >/dev/null 2>&1 && { step "pytest"     bash -c 'pytest; rc=$?; [ $rc -eq 5 ] && exit 0; exit $rc'; ran=1; }
fi

# Go.
[ -f go.mod ] && { step "go vet"  go vet ./...;  step "go test" go test ./...; ran=1; }

# Rust.
[ -f Cargo.toml ] && { step "cargo check" cargo check; step "cargo test" cargo test; ran=1; }

# Ruby / Rails.
if [ -f Gemfile ]; then
  [ -x ./bin/rubocop ]  && { step "rubocop" ./bin/rubocop;  ran=1; }
  [ -x ./bin/rspec ]    && { step "rspec"   ./bin/rspec;    ran=1; }
fi

if [ $ran -eq 0 ]; then
  echo "harness-check: no sensors fired."
  echo "  → edit scripts/harness-check.sh to wire your project's lint / types / tests."
  echo "  → an empty harness-check is treated as PASS so this script doesn't strand Stop."
  exit 0
fi

echo "✅ harness-check passed"
