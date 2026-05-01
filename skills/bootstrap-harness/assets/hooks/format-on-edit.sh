#!/usr/bin/env bash
# PostToolUse hook for Write|Edit. Run the project's formatter if available.
# Silent on success, prints output on failure (advisory — non-blocking).

set -u
cd "$(pwd)" || exit 0

run() { "$@" >/dev/null 2>&1 || { echo "format hint: '$*' had non-zero exit"; return 0; }; }

# Laravel/PHP
if [ -f vendor/bin/pint ]; then
  run vendor/bin/pint --quiet
fi

# Node — only if a format script exists
if [ -f package.json ] && grep -q '"format"' package.json 2>/dev/null; then
  if command -v bun >/dev/null 2>&1; then
    run bun run format
  elif command -v npm >/dev/null 2>&1; then
    run npm run format --silent
  fi
fi

# Python — ruff if config exists
if [ -f pyproject.toml ] && grep -q 'ruff' pyproject.toml 2>/dev/null && command -v ruff >/dev/null 2>&1; then
  run ruff format .
fi

# Go
if [ -f go.mod ] && command -v gofmt >/dev/null 2>&1; then
  run gofmt -w .
fi

# Rust
if [ -f Cargo.toml ] && command -v cargo >/dev/null 2>&1; then
  run cargo fmt --quiet
fi

exit 0
