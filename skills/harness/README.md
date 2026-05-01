# `/harness` — Claude Code harness control surface

A small opinionated skill that turns `~/.claude/` into a proper **harness**: feedforward guides Claude reads before it acts, deterministic sensors that catch drift after, and an optional drift-detection loop that PRs deltas against the latest releases each month.

Sub-actions: **install**, **uninstall**, **snapshot**, **status**, **audit**. All idempotent. No surface gets clobbered without consent.

## Where the idea comes from

The vocabulary and structure follow two pieces of writing that ought to be required reading for anyone running coding agents seriously:

- **OpenAI — *Harness engineering*** · [openai.com/index/harness-engineering](https://openai.com/index/harness-engineering/)
  Frames the work as building a *harness around the agent*: feedforward guides ("here's how to act"), feedback sensors ("here's how you went wrong"), and garbage collection ("clean up while you sleep").
- **Martin Fowler — *Harness engineering*** · [martinfowler.com/articles/harness-engineering.html](https://martinfowler.com/articles/harness-engineering.html)
  Independent treatment of the same idea — the harness is the discipline, the model is just the engine.

The day-to-day patterns this skill ships came from these voices, who keep publishing the highest-signal Claude Code material:

- **Boris Cherny** (Claude Code lead, Anthropic) · [howborisusesclaudecode.com](https://howborisusesclaudecode.com/) — the canonical reference for hooks, slash commands, plan-mode, parallel worktrees, and the `CLAUDE_CODE_AUTO_COMPACT_WINDOW=400000` tip.
- **Simon Willison** · [simonwillison.net/tags/claude-code/](https://simonwillison.net/tags/claude-code/) — the Auto Mode safety analysis (deterministic hooks beat AI classifiers) and the [Skills > MCP](https://simonw.substack.com/p/claude-skills-are-awesome-maybe-a) argument that decided the format.
- **Jesse Vincent — Superpowers** · [github.com/obra/superpowers](https://github.com/obra/superpowers) and [the original blog post](https://blog.fsck.com/2025/10/09/superpowers/) — the brainstorm → plan → fresh-subagent-per-task → verify-before-completion workflow.
- **Geoffrey Huntley — the Ralph loop** · [ghuntley.com/loop/](https://ghuntley.com/loop/) — context engineering as a programmable surface; the verification loop *is* the work.
- **Hamel Husain — Evals skills for coding agents** · [hamel.dev/blog/posts/evals-skills/](https://hamel.dev/blog/posts/evals-skills/) — "improving the infrastructure around the agent mattered more than improving the model."
- **Steve Yegge — Gas Town / Gas City** · [Gas Town](https://steve-yegge.medium.com/welcome-to-gas-town-4f25ee16dd04) and [Gas City](https://steve-yegge.medium.com/welcome-to-gas-city-57f564bb3607) — multi-agent orchestration above the level this skill operates at, but the role-decomposition (Mayor / Polecats / Refinery) generalises.

This skill is also a sibling of [datashaman/harness-template](https://github.com/datashaman/harness-template) — that repo is the *project-scope* harness (drop-in stack profiles, `harness/policies/`, `scripts/harness-check.sh`, `harness/grades.yml`). `/harness` is the user-scope counterpart.

## When to use

`/harness` — the skill detects intent from your phrasing. Examples:

| You say                                            | It runs    |
| -------------------------------------------------- | ---------- |
| "set up my Claude Code", "install harness"         | `install`  |
| "uninstall harness", "remove the bootstrap"        | `uninstall`|
| "snapshot my setup", "back up `~/.claude/`"        | `snapshot` |
| "what's installed?", "is the harness wired?"       | `status`   |
| "schedule a monthly audit", "audit my setup"       | `audit`    |
| Just `/harness`                                    | `status`, then asks |

## What `install` lays down

| Surface                  | What lands                                                                                          |
| ------------------------ | --------------------------------------------------------------------------------------------------- |
| `~/.claude/CLAUDE.md`    | Operating-contract template (default stance, editing rules, expected tools)                         |
| `~/.claude/hooks/`       | `block-force-push.sh`, `format-on-edit.sh`, `post-compact-reinject.sh`, `verify-before-stop.sh`     |
| `~/.claude/commands/`    | `/verify` (run the project's pass/fail check), `/plan` (Goal/Constraints/Acceptance template)       |
| `~/.claude/projects/<slug>/memory/` | `MEMORY.md` index + `user_role`, `feedback_concise`, `feedback_plan_first`, `feedback_verification` |
| `~/.claude/settings.json`| Adds `env.CLAUDE_CODE_AUTO_COMPACT_WINDOW=400000` + 4 hook entries (only if missing)                |

The hooks:

- **`block-force-push.sh`** (PreToolUse:Bash) — segment-aware matcher. Blocks force-push to main/master, hard reset to remote, `rm -rf ~`, `--no-verify`, world-writable chmod, branch -D. Allows `--force-with-lease`. Doesn't false-trigger on echoed strings.
- **`format-on-edit.sh`** (PostToolUse:Write|Edit) — runs Pint / `bun run format` / `npm run format` / ruff / gofmt / cargo fmt if the project's config is present. Silent on success.
- **`post-compact-reinject.sh`** (PostCompact) — re-cats `./CLAUDE.md`, `./AGENTS.md`, `~/.claude/CLAUDE.md` after autocompact, so the operating contract survives compression.
- **`verify-before-stop.sh`** (Stop) — refuses Stop if `./scripts/harness-check.sh` fails. `CLAUDE_SKIP_VERIFY=1` to override mid-investigation.

## What `uninstall` does

Symmetric reversal. Conservative defaults:

- Removes hooks + commands **only if their sha256 still matches** the installed template — your customisations stay.
- Strips the 4 hook entries from `settings.json`. Drops empty hook event arrays. Doesn't touch permissions, marketplaces, statusLine, advisorModel, theme, or anything else.
- Keeps `CLAUDE.md`, memory entries, and the env var by default — opt in with `--remove-claude-md`, `--remove-memory`, `--remove-env`, or `--all`.
- Flags: `--dry-run`, `--force` (override content-match check).

## What `snapshot` does

Mirrors `~/.claude/` into a target git repo (you specify, must be PRIVATE), scrubs caches and known secret patterns, commits + pushes only on diff. Idempotent — second run is a no-op. Used as the input to the monthly `audit` routine.

```bash
SNAPSHOT_REPO=~/Projects/<you>/claude-setup bash $SKILL_DIR/scripts/snapshot.sh
```

## What `audit` does

Doesn't run an audit *here*. Prepares a prompt for a **remote** monthly routine that the user creates via `/schedule`. The remote agent clones your snapshot repo, researches the last ~30 days of Anthropic releases (release notes, CHANGELOG, blog) and the canonical voices listed above, and opens a PR with `audits/YYYY-MM-DD-setup-audit.md` containing prioritised deltas. It can never modify `CLAUDE.md` / `settings.json` / hooks — only proposes.

## Arguments

None. The skill detects intent from natural language. If unclear, it runs `status` first and asks.

## Files in this folder

| File                              | Role                                                                  |
| --------------------------------- | --------------------------------------------------------------------- |
| `SKILL.md`                        | Agent instructions (what Claude reads when invoked)                   |
| `README.md`                       | This — human-facing overview                                          |
| `assets/CLAUDE.md.tmpl`           | Operating-contract template                                           |
| `assets/hooks/*.sh`               | Four hook scripts                                                     |
| `assets/commands/*.md`            | `/verify`, `/plan`                                                    |
| `assets/memory/*.tmpl`            | MEMORY.md index + 3 feedback memories + user_role template            |
| `scripts/install.sh`              | Idempotent installer (`--dry-run` / `--force` / `--skip-*`)            |
| `scripts/uninstall.sh`            | Symmetric uninstaller (content-match check; `--all` for full sweep)   |
| `scripts/snapshot.sh`             | Sanitised mirror of `~/.claude/` → target git repo                    |
| `scripts/status.sh`               | Read-only — reports installed / modified / missing per surface         |
| `scripts/audit-prompt.md`         | Prompt template for the monthly remote-audit routine                  |

## Requirements

- macOS or Linux with `python3` and `grep -E` on PATH (both are stdlib / coreutils — should be everywhere)
- For `snapshot`: `git`, plus `gh` if you want help creating a private repo
- For `audit`: a Claude Code account where `/schedule` is available

## Install via `skills.sh`

```bash
npx skills add https://github.com/datashaman/code-skills --skill harness
```

## A note on the name

This was originally `bootstrap-harness`. Renamed because the skill is a *control surface*, not a one-shot bootstrap — `install` is just one of five sub-actions, and "bootstrap" undersells what it does. `harness` is the noun the discipline already uses (see the OpenAI / Fowler articles above), so `/harness install`, `/harness uninstall`, `/harness snapshot`, `/harness status`, `/harness audit` all read the way the corresponding sub-CLI would in any other tool.
