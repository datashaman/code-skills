---
name: bootstrap-harness
description: >
  Bootstraps a "harness-engineering" Claude Code setup at user scope (~/.claude/):
  a dense operating-contract CLAUDE.md, deterministic guardrail hooks (block force-push,
  format on edit, re-inject CLAUDE.md after compact, refuse to stop with broken build),
  /verify and /plan slash commands, an auto-memory seed (concise / plan-first /
  verification-gate feedback memories + a user_role template), and an optional
  monthly remote-audit pipeline (snapshot the setup to a git repo, schedule a routine
  that PRs deltas against the latest Anthropic releases and Claude Code community
  patterns). Idempotent. Use when asked to "set up my Claude Code", "bootstrap a
  harness", "install hooks", "wire verification", or "harden my setup".
user-invocable: true
---

# Bootstrap harness

Sets up the user-scope Claude Code "harness" — feedforward guides (CLAUDE.md, memory), feedback sensors (hooks), and an optional drift-detection loop (snapshot + monthly audit routine). Idempotent: never clobbers files unless `--force`.

## When to use

Good prompts: *bootstrap my Claude Code setup*, *install harness*, *wire up hooks and verification*, *set up auto-memory*, *make my setup agent-ready*.

## What it installs

| Surface                  | What lands                                                                                          |
| ------------------------ | --------------------------------------------------------------------------------------------------- |
| `~/.claude/CLAUDE.md`    | Operating contract (default stance, editing rules, expected tools, stack-signals placeholder)       |
| `~/.claude/hooks/`       | `block-force-push.sh`, `format-on-edit.sh`, `post-compact-reinject.sh`, `verify-before-stop.sh`     |
| `~/.claude/commands/`    | `/verify` (run pass/fail check), `/plan` (Goal/Constraints/Acceptance template)                     |
| `~/.claude/projects/<slug>/memory/` | `MEMORY.md` index + `user_role`, `feedback_concise`, `feedback_plan_first`, `feedback_verification` |
| `~/.claude/settings.json`| Adds `CLAUDE_CODE_AUTO_COMPACT_WINDOW=400000` env + 4 hook entries (only if missing — no clobber)   |

Optional second phase:
- Mirror `~/.claude/` into a private git repo via `scripts/snapshot.sh`.
- Schedule a monthly remote-audit routine that PRs deltas against the latest releases (prompt template at `scripts/audit-prompt.md`).

## Step 1: Inventory what's already there

Before installing anything, look at the current state and report what you'll do:

```bash
ls -la ~/.claude/CLAUDE.md ~/.claude/settings.json 2>/dev/null
ls ~/.claude/hooks/ ~/.claude/commands/ ~/.claude/agents/ 2>/dev/null
ls ~/.claude/projects/$(printf '%s' "$HOME" | tr '/' '-')/memory/ 2>/dev/null
```

For each surface, classify as:
- **absent** → install template
- **present, untouched template** → safe to overwrite (rare — usually only on a re-run)
- **present, customised** → skip; tell user to pass `--force` if they want to overwrite

## Step 2: Run the installer

```bash
bash "$SKILL_DIR/scripts/install.sh"
```

(Substitute the skill's absolute base directory for `$SKILL_DIR` — it's announced at the top of this invocation.)

Useful flags:
- `--dry-run` — show what would happen, change nothing.
- `--force` — overwrite existing CLAUDE.md / hooks / commands / memory templates.
- `--skip-memory` — leave memory alone (recommended if it's already populated).
- `--skip-settings` — leave `settings.json` alone (recommended if user has a complex existing config).

The installer:
1. Creates `~/.claude/{hooks,commands,agents,projects/<slug>/memory}` if missing.
2. Copies `assets/CLAUDE.md.tmpl` → `~/.claude/CLAUDE.md` (skip if exists).
3. Copies each `assets/hooks/*.sh` → `~/.claude/hooks/` and `chmod +x`.
4. Copies each `assets/commands/*.md` → `~/.claude/commands/`.
5. Copies each `assets/memory/*.tmpl` → `~/.claude/projects/<slug>/memory/<basename>` (strips `.tmpl`).
6. Patches `~/.claude/settings.json` via Python: adds `env.CLAUDE_CODE_AUTO_COMPACT_WINDOW` and 4 hook entries, only if not already present. Never overwrites unrelated settings.

## Step 3: Hand-edit two files

The installer prints these as next-steps. Walk the user through them or do it yourself if context allows:

1. **`~/.claude/CLAUDE.md`** — fill in the `## Stack signals` section with their actual default stack (look at `~/.claude/projects/` slugs and `installed_plugins.json` for hints; ask if unclear).
2. **`~/.claude/projects/<slug>/memory/user_role.md`** — replace the placeholder with their actual role/projects/stack.

Do NOT auto-fill these from guesswork. Ask.

## Step 4 (optional): Wire the snapshot + audit loop

If the user wants version-controlled config + a monthly audit:

1. **Create the snapshot repo.** Suggest a name like `<their-gh-username>/claude-setup`.
   ```bash
   mkdir -p ~/Projects/<them>/claude-setup
   cd ~/Projects/<them>/claude-setup
   git init -b main
   gh repo create <them>/claude-setup --private --source=. --remote=origin
   ```

2. **First snapshot.**
   ```bash
   SNAPSHOT_REPO=~/Projects/<them>/claude-setup bash "$SKILL_DIR/scripts/snapshot.sh"
   ```
   This sanitises and pushes. The script is idempotent — second run is a no-op if nothing changed.

3. **Schedule the audit routine.** Use `RemoteTrigger` (the user must invoke `/schedule` themselves; this skill can prepare the prompt). The prompt template is at `$SKILL_DIR/scripts/audit-prompt.md`. Recommended config:
   - cron: `0 6 1 * *` (1st of month, 06:00 UTC)
   - model: `claude-opus-4-7` (audit quality matters)
   - tools: Bash, Read, Write, Edit, Glob, Grep, WebFetch, WebSearch, Agent
   - sources: the snapshot repo URL

4. **Tell the user to re-run `snapshot.sh`** whenever they materially change `~/.claude/`. Or schedule it locally via `/loop` or a launchd plist.

## Uninstall

If the user asks to remove the harness ("uninstall", "remove the harness", "undo bootstrap-harness"), run:

```bash
bash "$SKILL_DIR/scripts/uninstall.sh"
```

The uninstaller is symmetric and conservative:

- Removes the 4 hooks and 2 slash commands **only if their content still matches the installed template** (sha256 compare against `assets/`). User-modified files are kept and reported as `keep (modified)`.
- Strips the 4 hook entries from `settings.json`. Drops empty hook event arrays. Leaves all other settings (permissions, marketplaces, statusLine, etc.) untouched.
- **Keeps by default:** `CLAUDE.md`, memory files, the `CLAUDE_CODE_AUTO_COMPACT_WINDOW` env var. Those tend to be customised. Pass `--remove-claude-md`, `--remove-memory`, `--remove-env` to opt in.
- Flags: `--dry-run`, `--force` (override content-match check), `--all` (= `--force --remove-claude-md --remove-memory --remove-env`).

After uninstall, tell the user to **restart Claude Code** so the hook deregistration takes effect.

## Step 5: Verify the install

```bash
# Hook smoke-test — should print BLOCKED.
echo '{"tool_name":"Bash","tool_input":{"command":"git push --force origin main"}}' \
  | ~/.claude/hooks/block-force-push.sh; echo "exit=$?"

# Memory index loaded.
test -f ~/.claude/projects/$(printf '%s' "$HOME" | tr '/' '-')/memory/MEMORY.md && echo "memory OK"

# Settings JSON valid.
python3 -m json.tool ~/.claude/settings.json > /dev/null && echo "settings OK"
```

Tell the user to **restart Claude Code (or open a new session)** — hooks load on session start, not mid-session.

## Constraints

- **Never auto-fill stack signals or user_role.** Templates have placeholders; ask the user to fill them.
- **Never modify `settings.json` outside `env` and `hooks`.** Specifically: don't touch their permissions, marketplaces, statusLine, advisorModel, theme — those are personal.
- **Memory is sensitive.** If `MEMORY.md` already exists with their entries, leave it alone unless they say otherwise.
- **Don't push to a public GitHub repo by default.** The snapshot contains personal config — `--private` is mandatory.
- The hooks assume `python3` and `grep -E` are on PATH. They are on macOS and most Linux. If not, the hook scripts will silently no-op (graceful by design).

## Files in this skill

| File                              | Role                                                                  |
| --------------------------------- | --------------------------------------------------------------------- |
| `SKILL.md`                        | This file — agent instructions                                        |
| `README.md`                       | Human-facing overview                                                 |
| `assets/CLAUDE.md.tmpl`           | Operating-contract template                                           |
| `assets/hooks/*.sh`               | Four hook scripts                                                     |
| `assets/commands/*.md`            | `/verify`, `/plan` slash commands                                     |
| `assets/memory/*.tmpl`            | MEMORY.md index + 3 feedback memories + user_role template            |
| `scripts/install.sh`              | Idempotent installer with `--dry-run` / `--force` / `--skip-*` flags  |
| `scripts/uninstall.sh`            | Symmetric uninstaller; content-match check keeps user-modified files; `--all` for full sweep |
| `scripts/snapshot.sh`             | Sanitised mirror of `~/.claude/` → target git repo                    |
| `scripts/audit-prompt.md`         | Prompt template for the monthly remote-audit routine                  |
