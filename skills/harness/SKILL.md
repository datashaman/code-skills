---
name: harness
description: >
  Control surface for a "harness-engineering" Claude Code setup at user or
  project scope. Sub-actions: install (operating-contract CLAUDE.md, four
  guardrail hooks, /verify and /plan slash commands, auto-memory seeds,
  settings.json patch); uninstall (symmetric reversal with content-match
  protection for customised files); update (refresh installed files vs
  current templates, with --merge for diffable side-by-side); doctor
  (end-to-end diagnostic — sha256 tools, write perms, hook smoke-test,
  settings JSON validity, memory + CLAUDE.md state); adopt (retrofit into
  an existing project — detects stack, scaffolds a starter scripts/harness-
  check.sh, prints next-step install command); snapshot (sanitised mirror
  of ~/.claude/ to a private git repo); status (report what's installed,
  modified, or missing); audit (prepare a monthly remote-audit routine
  that PRs deltas against the latest Anthropic releases and Claude Code
  community patterns). All sub-actions are idempotent. Use when asked to
  "set up my Claude Code", "install harness", "uninstall harness", "update
  harness", "diagnose my setup", "adopt harness in this project",
  "retrofit", "snapshot my setup", "audit my setup", "harden my Claude",
  or any request matching the sub-actions.
user-invocable: true
---

# Harness

Control surface for the user-scope Claude Code "harness" — feedforward guides (CLAUDE.md, memory), feedback sensors (hooks), and an optional drift-detection loop (snapshot + monthly audit).

The vocabulary follows OpenAI's *Harness engineering* (https://openai.com/index/harness-engineering/) and Martin Fowler's writeup (https://martinfowler.com/articles/harness-engineering.html). Day-to-day patterns are convergent picks from Boris Cherny, Simon Willison, Jesse Vincent (Superpowers), Geoffrey Huntley (Ralph loop), Hamel Husain (eval skills), and Steve Yegge (Gas Town). See README.md for citations.

## Sub-action dispatch

The user invokes this skill, optionally with an action word. Detect intent and run the matching sub-action. If the user says `/harness` without context, run **status** first (it's read-only and informative), then ask which action they want.

| Said by user                                  | Sub-action  | Script                          |
| --------------------------------------------- | ----------- | ------------------------------- |
| "install", "set up", "bootstrap"              | `install`   | `scripts/install.sh`            |
| "uninstall", "remove", "undo"                 | `uninstall` | `scripts/uninstall.sh`          |
| "update", "pull latest templates", "refresh"  | `update`    | `scripts/update.sh`             |
| "doctor", "diagnose", "is it working"         | `doctor`    | `scripts/doctor.sh`             |
| "adopt", "add to existing project", "retrofit"| `adopt`     | `scripts/adopt.sh`              |
| "snapshot", "backup", "mirror to git"         | `snapshot`  | `scripts/snapshot.sh`           |
| "status", "what's installed", "audit local"   | `status`    | `scripts/status.sh`             |
| "audit", "schedule audit", "monthly check"    | `audit`     | (prep work — see below)         |

Substitute the skill's absolute base directory for `$SKILL_DIR` in every command — it's announced at the top of this invocation.

## install

Lays down the harness at the **scope where the skill itself lives**, derived from `$SKILL_DIR`:

- Skill at `<X>/.claude/skills/harness/` (or under a plugin cache below `<X>/.claude/`) → install at `<X>/.claude/`.
- If `<X>` is `$HOME`, that's user scope; otherwise project scope.
- Override with `--scope=user`, `--scope=project`, or `--target=PATH`.
- If the skill is being run from a checkout (no `.claude/` ancestor), the script errors with a clear message asking for `--scope` or `--target`.

What lands at user scope:

| Surface                  | Path                                                                                                |
| ------------------------ | --------------------------------------------------------------------------------------------------- |
| Operating contract       | `~/.claude/CLAUDE.md`                                                                              |
| Hooks                    | `~/.claude/hooks/{block-force-push,format-on-edit,post-compact-reinject,verify-before-stop}.sh`     |
| Slash commands           | `~/.claude/commands/{verify,plan}.md`                                                              |
| Auto-memory              | `~/.claude/projects/<slug>/memory/{MEMORY.md, user_role, feedback_concise, feedback_plan_first, feedback_verification}` |
| settings.json            | Adds `env.CLAUDE_CODE_AUTO_COMPACT_WINDOW=400000` + 4 hook entries (uses `~/.claude/hooks/...` form) |

What lands at project scope (`<project>/.claude/`):

| Surface         | Path                                                                                            |
| --------------- | ----------------------------------------------------------------------------------------------- |
| Operating contract | `<project>/CLAUDE.md` (skipped if it already exists — most projects have one. `--force` overrides) |
| Hooks           | `<project>/.claude/hooks/*.sh`                                                                 |
| Commands        | `<project>/.claude/commands/*.md`                                                              |
| settings.json   | `<project>/.claude/settings.json` — 4 hook entries with `.claude/hooks/...` (project-relative) form. **No env var, no memory** at project scope. |
| Memory          | (skipped — memory is per-user by design and lives under `$HOME` regardless of project scope)   |

```bash
bash "$SKILL_DIR/scripts/install.sh"
```

Common flags:
- `--dry-run` — show the preflight + plan, change nothing.
- `--force` — overwrite existing files (including project CLAUDE.md).

Per-surface skip flags (escape hatch — pick & choose what to install):
- `--skip-claude-md`, `--skip-hooks`, `--skip-commands`, `--skip-memory`, `--skip-settings`

Or a positive list (everything else is skipped):
- `--include=hooks,commands` — install only those.
- `--include=claude-md,settings` — only the operating contract + settings patch.
- Valid items: `claude-md`, `hooks`, `commands`, `memory`, `settings`.

The script always prints a **preflight banner** showing scope, target, the per-surface plan (with SKIP markers reflecting the active flags), and a pointer to the uninstaller with `--all` warnings. Read it before proceeding.

After install, walk the user through the hand-edits printed under "Next steps":

1. Fill in `## Stack signals` in CLAUDE.md.
2. (User scope only) Replace placeholders in `memory/user_role.md` with the user's actual role/projects/stack. **Ask, don't invent.**

Tell them to **restart Claude Code** so hooks load.

After install, walk the user through two hand-edits:

1. `~/.claude/CLAUDE.md` — fill in the `## Stack signals` section. Look at `~/.claude/projects/` slugs and `installed_plugins.json` for hints; ask if unclear. **Don't auto-fill from guesswork.**
2. `~/.claude/projects/<slug>/memory/user_role.md` — replace placeholders with the user's actual role/projects/stack. **Ask, don't invent.**

Tell them to **restart Claude Code** so hooks load.

## uninstall

```bash
bash "$SKILL_DIR/scripts/uninstall.sh"
```

Same scope auto-detection as install. Conservative defaults:

- Removes hooks + commands **only if their sha256 still matches** the installed template. User-modified files are kept and reported as `keep (modified)`.
- Strips the 4 hook entries from `settings.json`; drops empty hook event arrays. Leaves all other settings untouched.
- **Keeps by default:** `CLAUDE.md`, memory files, the `CLAUDE_CODE_AUTO_COMPACT_WINDOW` env var.

Flags:
- `--dry-run`, `--force` (skip content-match)
- Broaden the sweep: `--remove-claude-md`, `--remove-memory`, `--remove-env`, `--all`
- **Escape hatch — keep specific surfaces that default would remove:** `--keep-hooks`, `--keep-commands`, `--keep-settings`

The script prints a preflight banner showing scope, target, what will be removed vs kept, and which `--keep-*` / `--remove-*` flags are active. Always run `--dry-run` first if unsure.

Tell the user to **restart Claude Code** so hook deregistration takes effect.

## adopt

Retrofit the harness into an existing project (project scope only). Use when the user says "I have a project, how do I add this?", "adopt", "retrofit", or any variant that implies *this isn't a greenfield install*.

```bash
bash "$SKILL_DIR/scripts/adopt.sh"
```

What it does:

- Detects the project root (`$CLAUDE_PROJECT_DIR` or `$PWD`; refuses to write into `$HOME`).
- Reports what's already there: `CLAUDE.md`, `.claude/`, `settings.json`, `scripts/harness-check.sh`, plus stack signals.
- Writes a stack-aware starter file to `scripts/harness-check.sh` — the project-side pass/fail gate that `verify-before-stop.sh` and `/verify` invoke. The starter runs lint / types / tests for whichever ecosystem files are present (`package.json`, `composer.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `Gemfile`). Skipped if `harness-check.sh` already exists (`--force` to overwrite). Empty-sensor case is treated as PASS so the script never strands `Stop`.
- Prints the next-step `install.sh --scope=project` command. **Does not run install itself** — the user reviews the preflight banner there separately.

Walk-through for the agent:

1. Run `adopt.sh`. Read its preflight to the user.
2. If the user is happy, run `install.sh --scope=project` (or with `--include=hooks,commands` for a minimum-viable retrofit that doesn't add a CLAUDE.md).
3. Tell the user to edit `scripts/harness-check.sh` to match their project's commands (the starter is intentionally generous; comment out or delete blocks that don't apply).
4. Tell them to **restart Claude Code** so hooks load.
5. Suggest they run `/verify` once to smoke-test the gate end-to-end.
6. Mention `datashaman/harness-template` for the deeper project-scope layer (policy YAMLs, grades, `.skip` ledger) when they've outgrown the starter.

Flags:
- `--target=PATH` — explicit project root.
- `--dry-run` — show plan, don't write.
- `--force` — overwrite an existing `scripts/harness-check.sh` (you'll lose edits).

## update

```bash
bash "$SKILL_DIR/scripts/update.sh"
```

Smarter than `install --force`. For each surface compares installed vs current template via sha256 and:

- identical → re-install (no-op cosmetically)
- missing → install
- modified → print diff and **SKIP**, unless `--merge` or `--force`

Flags:
- `--dry-run` — show plan only.
- `--force` — overwrite ALL files including modified ones (loses customisations).
- `--merge` — for modified files, write the new template to `<file>.new` alongside the original. The user can diff/merge interactively.

Default behaviour is non-destructive: you'll see diffs but no customised file is overwritten without consent.

## doctor

```bash
bash "$SKILL_DIR/scripts/doctor.sh"
```

End-to-end diagnostic. Combines `status` with sanity checks:

- sha256 tool present
- target dir writable
- `settings.json` is valid JSON
- all 4 hooks exist, are executable, and are wired in `settings.json`
- hook entries don't point at unexpected paths (foreign installs)
- smoke-test: invoke `block-force-push.sh` with a known-bad command and verify exit code 2
- memory dir populated (user scope)
- `CLAUDE.md` present and `## Stack signals` not still placeholder
- snapshot repo (if `$SNAPSHOT_REPO` set) — last commit recency

Exits non-zero if any FAIL, zero on warnings. Run `doctor` after `install` and after each Claude Code upgrade.

## snapshot

```bash
SNAPSHOT_REPO=~/Projects/<them>/<repo> bash "$SKILL_DIR/scripts/snapshot.sh"
```

Mirrors `~/.claude/` into a target git repo, scrubs caches and secret patterns, commits + pushes only on diff. Idempotent.

If the user doesn't have a snapshot repo yet, prompt them to create one (PRIVATE — the snapshot has personal config):

```bash
mkdir -p ~/Projects/<them>/claude-setup
cd ~/Projects/<them>/claude-setup
git init -b main
gh repo create <them>/claude-setup --private --source=. --remote=origin
```

Then run `snapshot.sh` against it. The first push lands; subsequent runs are no-ops if nothing changed.

Override sources via env: `CLAUDE_DIR=...`, `USER_PROJECT_KEY=...`.

## status

```bash
bash "$SKILL_DIR/scripts/status.sh"
```

Read-only. Reports:

- For each hook + command + memory file + CLAUDE.md: `installed` (matches template), `modified` (customised), or `missing`.
- For `settings.json`: which of the 4 hook entries are wired, plus the env var.
- For snapshot repo (if `SNAPSHOT_REPO` env is set): commits ahead of origin, last snapshot timestamp.

Use `status` first when the user says `/harness` without an action word, when they say "what's installed?", when they say "is this still set up?", or before any `install` to show the diff.

## audit

The audit is a monthly **remote** routine — Claude Code's `/schedule` skill creates it. This skill prepares the prompt and suggests config; the user runs `/schedule` themselves.

Steps:

1. Read `$SKILL_DIR/scripts/audit-prompt.md` — that's the prompt for the remote agent. Confirm with the user that it covers what they want.
2. Suggested config:
   - cron: `0 6 1 * *` (1st of month, 06:00 UTC)
   - model: `claude-opus-4-7` (audit quality matters)
   - tools: Bash, Read, Write, Edit, Glob, Grep, WebFetch, WebSearch, Agent
   - sources: the user's snapshot repo URL (must exist — run `snapshot` first)
3. Tell the user to invoke `/schedule` and paste the prompt + config. Or, if they have `RemoteTrigger` available in their session, build the body and call it directly.

The remote agent clones the snapshot repo, researches the last ~30 days of Anthropic releases and canonical Claude Code voices, and PRs `audits/YYYY-MM-DD-setup-audit.md` with prioritised deltas. It never modifies tracked files outside `audits/`.

## Constraints

- **Never auto-fill stack signals or user_role.** Templates have placeholders; ask the user to fill them.
- **Never modify `settings.json` outside `env` and `hooks`.** Don't touch permissions, marketplaces, statusLine, advisorModel, theme.
- **Memory is sensitive.** If `MEMORY.md` already exists with the user's entries, leave it alone unless they explicitly say otherwise.
- **Snapshot repos must be private.** They contain personal config.
- **Hooks load on session start.** Tell the user to restart Claude Code after install/uninstall.

## Files in this skill

| File                              | Role                                                                  |
| --------------------------------- | --------------------------------------------------------------------- |
| `SKILL.md`                        | This file — agent instructions                                        |
| `README.md`                       | Human-facing overview (with sources / inspiration)                    |
| `assets/CLAUDE.md.tmpl`           | Operating-contract template                                           |
| `assets/hooks/*.sh`               | Four hook scripts                                                     |
| `assets/commands/*.md`            | `/verify`, `/plan`                                                    |
| `assets/memory/*.tmpl`            | MEMORY.md index + 3 feedback memories + user_role template            |
| `scripts/install.sh`              | Idempotent installer (`--dry-run` / `--force` / `--skip-*`)            |
| `scripts/uninstall.sh`            | Symmetric uninstaller (content-match check; `--all` for full sweep)   |
| `scripts/update.sh`               | Refresh installed files vs current templates (`--merge` / `--force`)  |
| `scripts/doctor.sh`               | End-to-end diagnostic (perms, hook smoke-test, settings JSON, etc.)   |
| `scripts/adopt.sh`                | Retrofit into existing project — writes `scripts/harness-check.sh`    |
| `scripts/snapshot.sh`             | Sanitised mirror of `~/.claude/` → target git repo                    |
| `scripts/status.sh`               | Read-only — reports installed / modified / missing per surface         |
| `scripts/_detect_stack.py`        | Stack-signal detector — auto-fills `## Stack signals` at install time |
| `assets/harness-check.sh.tmpl`    | Starter project pass/fail gate written by `adopt`                     |
| `scripts/audit-prompt.md`         | Prompt template for the monthly remote-audit routine                  |
