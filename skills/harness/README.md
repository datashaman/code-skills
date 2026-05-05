# `/harness` — Claude Code harness control surface

> **⚠️ WIP — not ready for use.** This skill is under active development and is not yet stable. Don't install it on a setup you care about.

A small opinionated skill that turns `~/.claude/` into a proper **harness**: feedforward guides Claude reads before it acts, deterministic sensors that catch drift after, and an optional drift-detection loop that PRs deltas against the latest releases each month.

Sub-actions: **install**, **uninstall**, **update**, **doctor**, **adopt**, **snapshot**, **status**, **audit**. All idempotent. No surface gets clobbered without consent.

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

## Context model: spatial vs temporal

The harness manages context on two axes. Naming them gives design discussions vocabulary ("is this a spatial concern or a temporal one?") and makes coverage gaps visible at a glance. Most hooks are *sensors* on the feedback axis — they're documented under install below, not here. The one exception is `post-compact-reinject.sh`: implemented as a hook, but its job is *context preservation*, so it sits in the temporal table.

**Spatial — what occupies the window in a given turn:**

| Surface                 | Always loaded?                | Notes                                                              |
| ----------------------- | ----------------------------- | ------------------------------------------------------------------ |
| `~/.claude/CLAUDE.md`   | yes                           | user-scope operating contract                                      |
| `<project>/CLAUDE.md`   | yes (when in that project)    | project-scope override                                             |
| `<project>/AGENTS.md`   | yes (when present)            | sibling to project CLAUDE.md; re-injected after autocompact        |
| `MEMORY.md` (index)     | yes                           | pointers to memory entries, not the entries themselves             |
| Memory entries          | on demand                     | loaded when the agent decides they're relevant                     |
| Skills                  | on demand                     | progressive disclosure — `SKILL.md` frontmatter triggers the load  |
| System prompt           | yes                           | tools + harness instructions                                       |

**Temporal — what survives across boundaries:**

| Boundary                          | Mechanism                                                                         |
| --------------------------------- | --------------------------------------------------------------------------------- |
| Autocompact (mid-session)         | `post-compact-reinject.sh` — re-cats `CLAUDE.md` / `AGENTS.md` / `~/.claude/CLAUDE.md` |
| Between tool steps (mid-session)  | `/critique` — deliberate critique pass without waiting for Stop (PTC, see #6)     |
| Session end → next session        | auto-memory write — agent stores durable facts to `memory/`                       |
| Across sessions                   | `memory/` store + `MEMORY.md` index                                               |
| Memory hygiene over time          | `memoize` sub-action (deterministic) + weekly remote routine (semantic)           |
| Config drift over time            | `snapshot` (mirror to private repo) + monthly remote `audit` routine              |

The PTC loop named in `CLAUDE.md` cuts across these axes: **Plan** is spatial preparation (load the right context before editing), **Tool** is the work itself, **Critique** is *temporal* — carrying findings forward, at session boundaries (Stop gate, `advisor()`) and intra-session via `/critique`.

## When to use

`/harness` — the skill detects intent from your phrasing. Examples:

| You say                                            | It runs    |
| -------------------------------------------------- | ---------- |
| "set up my Claude Code", "install harness"         | `install`  |
| "uninstall harness", "remove the bootstrap"        | `uninstall`|
| "update harness", "pull latest templates"          | `update`   |
| "doctor", "diagnose my setup", "is it working?"    | `doctor`   |
| "adopt harness", "retrofit into my project"        | `adopt`    |
| "snapshot my setup", "back up `~/.claude/`"        | `snapshot` |
| "what's installed?", "is the harness wired?"       | `status`   |
| "schedule a monthly audit", "audit my setup"       | `audit`    |
| Just `/harness`                                    | `status`, then asks |

## Scope auto-detection (no forced user-default)

The skill installs at the **scope where it itself lives** — derived from `$SKILL_DIR`. If the skill is at `<X>/.claude/skills/harness/` (or under a plugin cache below `<X>/.claude/`), the install lands at `<X>/.claude/`. That `<X>` becomes user scope if it's `$HOME`, project scope otherwise.

You can override:
- `--scope=user` → `$HOME/.claude/`
- `--scope=project` → `$CLAUDE_PROJECT_DIR/.claude/` (or `$PWD/.claude/` if unset)
- `--target=PATH` → explicit `.claude/` directory

If the skill is being invoked from a checkout (no `.claude/` ancestor), the script errors with a clear message asking for one of the flags above.

## What `install` lays down

**User scope** (`~/.claude/`):

| Surface                  | What lands                                                                                          |
| ------------------------ | --------------------------------------------------------------------------------------------------- |
| `~/.claude/CLAUDE.md`    | Operating-contract template (default stance, editing rules, expected tools)                         |
| `~/.claude/hooks/`       | `block-force-push.sh`, `format-on-edit.sh`, `post-compact-reinject.sh`, `verify-before-stop.sh`     |
| `~/.claude/commands/`    | `/verify` (project pass/fail), `/plan` (Goal/Constraints/Acceptance), `/critique` (mid-flow critique pass) |
| `~/.claude/projects/<slug>/memory/` | `MEMORY.md` index + `user_role`, `feedback_concise`, `feedback_plan_first`, `feedback_verification` |
| `~/.claude/settings.json`| Adds `env.CLAUDE_CODE_AUTO_COMPACT_WINDOW=400000` + 4 hook entries (only if missing)                |

**Project scope** (`<project>/.claude/`):

| Surface         | What lands                                                                                       |
| --------------- | ------------------------------------------------------------------------------------------------ |
| `<project>/CLAUDE.md` | Operating contract — **skipped if a project CLAUDE.md already exists** (`--force` overrides) |
| `<project>/.claude/hooks/`    | Same 4 hooks                                                                            |
| `<project>/.claude/commands/` | `/verify`, `/plan`, `/critique`                                                         |
| `<project>/.claude/settings.json` | 4 hook entries with **project-relative** paths (`.claude/hooks/...`)                |
| Memory          | NOT seeded at project scope — memory is per-user by design and lives under `$HOME`               |
| Env var         | NOT set at project scope — `CLAUDE_CODE_AUTO_COMPACT_WINDOW` is session-wide                     |

Project-scope install never modifies `$HOME`.

The hooks:

- **`block-force-push.sh`** (PreToolUse:Bash) — segment-aware matcher. Blocks force-push to main/master, hard reset to remote, `rm -rf ~`, `--no-verify`, world-writable chmod, branch -D. Allows `--force-with-lease`. Doesn't false-trigger on echoed strings.
- **`format-on-edit.sh`** (PostToolUse:Write|Edit) — runs Pint / `bun run format` / `npm run format` / ruff / gofmt / cargo fmt if the project's config is present. Silent on success.
- **`post-compact-reinject.sh`** (PostCompact) — re-cats `./CLAUDE.md`, `./AGENTS.md`, `~/.claude/CLAUDE.md` after autocompact, so the operating contract survives compression.
- **`verify-before-stop.sh`** (Stop) — refuses Stop if `./scripts/harness-check.sh` fails. `CLAUDE_SKIP_VERIFY=1` to override mid-investigation.

## Escape hatches — pick what to accept

Both `install.sh` and `uninstall.sh` print a **preflight banner** showing the scope, target, and per-surface plan before any change is made. To customise the plan:

- **install:** `--skip-claude-md`, `--skip-hooks`, `--skip-commands`, `--skip-memory`, `--skip-settings`. Or a positive list: `--include=hooks,commands` (everything not listed is skipped).
- **uninstall:** `--keep-hooks`, `--keep-commands`, `--keep-settings` to preserve specific surfaces that the default would remove. Plus the standard `--remove-claude-md`, `--remove-memory`, `--remove-env`, `--all` to broaden.
- Always available: `--dry-run` (recommended first run), `--force`.

## What `uninstall` does

Symmetric reversal. Conservative defaults:

- Removes hooks + commands **only if their sha256 still matches** the installed template — your customisations stay.
- Strips the 4 hook entries from `settings.json`. Drops empty hook event arrays. Doesn't touch permissions, marketplaces, statusLine, advisorModel, theme, or anything else.
- Keeps `CLAUDE.md`, memory entries, and the env var by default — opt in with `--remove-claude-md`, `--remove-memory`, `--remove-env`, or `--all`.
- Flags: `--dry-run`, `--force` (override content-match check).

## What `adopt` does

Retrofits the harness into an existing project that wasn't built around it. Walkthrough:

1. **Detects state.** Reports what's already there — `CLAUDE.md`, `.claude/`, `settings.json`, `scripts/harness-check.sh` — plus stack signals from manifest files.
2. **Writes a starter `scripts/harness-check.sh`** — the project-side pass/fail gate that `verify-before-stop.sh` and `/verify` invoke. Stack-aware: runs lint / types / tests for whichever ecosystem files are present (`package.json`, `composer.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `Gemfile`). Refuses to overwrite an existing one (`--force` to override). Empty-sensor case is treated as PASS so the script never strands `Stop`.
3. **Prints the next-step install command.** Doesn't run install itself — you read the preflight banner there separately.

```bash
/harness adopt                # detect + drop starter + print next steps
/harness install --scope=project   # then this — 4 hooks, /verify, /plan, CLAUDE.md
# edit scripts/harness-check.sh to taste
# restart Claude Code so hooks load
/verify                       # smoke-test the gate
```

For a deeper project-scope harness (policy YAMLs, `harness/grades.yml`, `.skip` ledger, stack profiles), see [`datashaman/harness-template`](https://github.com/datashaman/harness-template). `adopt` gives you the spine; harness-template is the next floor up.

Refuses to write into `$HOME` — adopt is project-scope only.

## What `update` does

Refreshes installed files against the current templates without clobbering customisations. For each surface compares installed vs template via sha256:

- **identical** → re-install (no-op cosmetically)
- **missing** → install
- **modified** → print diff and SKIP, unless you pass `--merge` or `--force`

`--merge` writes the new template to `<file>.new` alongside the original — diff/merge by hand. Run after pulling new versions of this skill.

## What `doctor` does

End-to-end diagnostic that catches drift `status` doesn't see. Sample checks:

- a sha256 tool is on PATH
- target dir is writable
- `settings.json` is valid JSON
- all 4 hooks are executable and wired into `settings.json`
- hook entries don't point at unexpected paths (foreign installs)
- smoke-tests `block-force-push.sh` with a known-bad command (must exit 2)
- memory dir is populated
- `CLAUDE.md` `## Stack signals` isn't still placeholder text
- snapshot repo (if `$SNAPSHOT_REPO` set) hasn't gone stale

Exits non-zero on any FAIL. Run after `install` and after each Claude Code upgrade.

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
| `assets/commands/*.md`            | `/verify`, `/plan`, `/critique`                                       |
| `assets/memory/*.tmpl`            | MEMORY.md index + 3 feedback memories + user_role template            |
| `scripts/install.sh`              | Idempotent installer (`--dry-run` / `--force` / `--skip-*`)            |
| `scripts/uninstall.sh`            | Symmetric uninstaller (content-match check; `--all` for full sweep)   |
| `scripts/update.sh`               | Refresh installed files vs current templates (`--merge` / `--force`)  |
| `scripts/doctor.sh`               | End-to-end diagnostic (perms, hook smoke-test, settings JSON, etc.)   |
| `scripts/adopt.sh`                | Retrofit into an existing project — writes `scripts/harness-check.sh`|
| `scripts/snapshot.sh`             | Sanitised mirror of `~/.claude/` → target git repo                    |
| `scripts/status.sh`               | Read-only — reports installed / modified / missing per surface         |
| `scripts/_detect_stack.py`        | Stack-signal detector — auto-fills `## Stack signals` at install time |
| `assets/harness-check.sh.tmpl`    | Starter project pass/fail gate written by `adopt`                     |
| `scripts/audit-prompt.md`         | Prompt template for the monthly remote-audit routine                  |

## Requirements

- macOS or Linux with `python3` and `grep -E` on PATH (both standard).
- A SHA-256 tool for `uninstall`/`status` content-match: any one of `sha256sum` (default on Linux), `shasum` (default on macOS), or `python3` (already required, so this is automatic).
- For `snapshot`: `git`, plus `gh` if you want help creating a private repo.
- For `audit`: a Claude Code account where `/schedule` is available.

## Install via `skills.sh`

```bash
npx skills add https://github.com/datashaman/code-skills --skill harness
```

## A note on the name

This was originally `bootstrap-harness`. Renamed because the skill is a *control surface*, not a one-shot bootstrap — `install` is just one of five sub-actions, and "bootstrap" undersells what it does. `harness` is the noun the discipline already uses (see the OpenAI / Fowler articles above), so `/harness install`, `/harness uninstall`, `/harness snapshot`, `/harness status`, `/harness audit` all read the way the corresponding sub-CLI would in any other tool.
