# bootstrap-harness

Bootstraps a "harness-engineering" Claude Code setup at user scope (`~/.claude/`): operating contract, deterministic guardrail hooks, verify/plan slash commands, auto-memory seed, and an optional monthly drift-detection audit. Idempotent.

## When to use

Good prompts: *bootstrap my Claude Code*, *install harness*, *wire hooks*, *set up auto-memory*, *harden my setup*, *make my setup agent-ready*.

## What it installs

| Surface                  | What lands                                                                                          |
| ------------------------ | --------------------------------------------------------------------------------------------------- |
| `~/.claude/CLAUDE.md`    | Operating contract template (default stance, editing rules, expected tools)                         |
| `~/.claude/hooks/`       | `block-force-push.sh`, `format-on-edit.sh`, `post-compact-reinject.sh`, `verify-before-stop.sh`     |
| `~/.claude/commands/`    | `/verify` (run project's pass/fail check), `/plan` (Goal/Constraints/Acceptance template)           |
| `~/.claude/projects/<slug>/memory/` | `MEMORY.md` index + `user_role`, `feedback_concise`, `feedback_plan_first`, `feedback_verification` |
| `~/.claude/settings.json`| Adds `CLAUDE_CODE_AUTO_COMPACT_WINDOW=400000` + 4 hook entries (only if missing — no clobber)       |

## How it works

Three stages:

1. **Bootstrap** (`scripts/install.sh`) — copies templates from `assets/` into `~/.claude/`, never overwrites without `--force`. Patches `settings.json` to wire hooks. `--dry-run` shows what would happen.
2. **Snapshot** (`scripts/snapshot.sh`, optional) — mirrors `~/.claude/` into a private git repo, scrubs caches and secret patterns, commits + pushes only on diff. Run after material config changes.
3. **Audit** (optional) — schedule a monthly remote routine using the prompt at `scripts/audit-prompt.md`.

4. **Uninstall** (`scripts/uninstall.sh`) — symmetric reversal. Removes the 4 hooks, 2 commands, and the 4 hook entries from `settings.json`, but only for files that still match the installed template (so any customisation you made is kept). Pass `--remove-memory`, `--remove-claude-md`, `--remove-env`, or `--all` to broaden the sweep. `--dry-run` shows what would happen. The agent clones your snapshot repo, researches the last ~30 days of Anthropic releases and canonical Claude Code voices (Cherny / Willison / Vincent / Huntley / Husain / Yegge), and PRs `audits/YYYY-MM-DD-setup-audit.md` with prioritised deltas.

The hooks:
- **block-force-push.sh** (PreToolUse:Bash) — segment-aware matcher. Blocks force-push to main/master, hard reset to remote, `rm -rf ~`, `--no-verify`, world-writable chmod, branch -D. Allows `--force-with-lease`. Doesn't false-trigger on echoed strings.
- **format-on-edit.sh** (PostToolUse:Write|Edit) — runs Pint / `bun run format` / `npm run format` / ruff / gofmt / cargo fmt if config exists. Silent on success.
- **post-compact-reinject.sh** (PostCompact) — re-cats `./CLAUDE.md`, `./AGENTS.md`, `~/.claude/CLAUDE.md` after autocompact, so the operating contract survives.
- **verify-before-stop.sh** (Stop) — blocks Stop if `./scripts/harness-check.sh` fails. `CLAUDE_SKIP_VERIFY=1` to override mid-investigation.

## Arguments

None. The skill detects what's already in `~/.claude/`, reports gaps, runs the installer, and walks the user through the two hand-edit steps (CLAUDE.md stack signals, memory user_role).

## Files in this folder

| File                              | Role                                                                  |
| --------------------------------- | --------------------------------------------------------------------- |
| `SKILL.md`                        | Full agent instructions                                               |
| `README.md`                       | This overview                                                         |
| `assets/CLAUDE.md.tmpl`           | Operating-contract template                                           |
| `assets/hooks/*.sh`               | Four hook scripts                                                     |
| `assets/commands/*.md`            | `/verify`, `/plan`                                                    |
| `assets/memory/*.tmpl`            | MEMORY.md index + 3 feedback memories + user_role template            |
| `scripts/install.sh`              | Idempotent installer (`--dry-run` / `--force` / `--skip-memory` / `--skip-settings`) |
| `scripts/uninstall.sh`            | Symmetric uninstaller — content-match check keeps user-modified files; `--all` for full sweep |
| `scripts/snapshot.sh`             | Sanitised mirror of `~/.claude/` → target git repo                    |
| `scripts/audit-prompt.md`         | Prompt template for the monthly remote-audit routine                  |

## Requirements

- macOS or Linux with `python3` and `grep -E` on PATH
- For the snapshot phase: `git`, plus `gh` if you want the installer to help create the private repo
- For the audit routine: a Claude Code account with `/schedule` available

## Inspiration

Convergent patterns from Boris Cherny (howborisusesclaudecode.com), Simon Willison (Auto Mode safety analysis), Jesse Vincent (Superpowers framework), Geoffrey Huntley (Ralph loop), Hamel Husain (eval skills), and Steve Yegge (Gas Town orchestration). The harness vocabulary (feedforward / sensors / GC) follows OpenAI's harness-engineering article and Martin Fowler's writeup.

For the full step-by-step workflow, open **`SKILL.md`**.
