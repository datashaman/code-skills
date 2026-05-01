---
description: Run the project's pass/fail verification check (harness-check.sh, or stack-default lint+types+tests)
---

Run the project's verification check and report pass/fail with concise output. Use this before declaring any task done.

Order of preference:

1. If `./scripts/harness-check.sh` exists and is executable → run it.
2. Else if `composer.json` exists with a `lint:check` script → run `composer lint:check && composer test` (and `npm run types:check` if `package.json` exists).
3. Else if `package.json` exists → run `npm run lint:check && npm run types:check && npm test` (skip any that aren't defined).
4. Else if `pyproject.toml` exists → `ruff check . && mypy . && pytest -q`.
5. Else if `Cargo.toml` → `cargo check && cargo test`.
6. Else if `go.mod` → `go vet ./... && go test ./...`.

Report:
- ✅ pass → one line.
- ❌ fail → the failing command, the salient lines from output (not full log), and the smallest fix proposal.

Do NOT propose a fix that disables a rule unless the user explicitly asks. Never use `--no-verify`.

If `$ARGUMENTS` is provided, treat it as a path filter — run checks scoped to that path where the tool supports it.
