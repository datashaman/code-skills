---
name: audit-context
description: >
  Audit your Claude Code setup for token waste and context bloat. Checks
  MCP servers, CLAUDE.md files, skills, agents, commands, plugins, hooks,
  and permissions. Mines session transcripts for cache hit rate, autocompact
  frequency, turn costs, tool errors, and unused assets. Flags broken MCP
  servers that load schemas but never connect. Returns a health score with
  specific fixes. Use when asked to "audit my context", "check my settings",
  "token optimization", or "why is Claude slow".
user-invocable: true
---

# Context Audit

Bloated context costs more and produces worse output. This skill finds
the waste and tells you what to cut. Static config audit + behavioral
scan of real session data.

## Step 1: Get /context Data

Check the conversation history for /context output. If the user already
ran /context in this session, use that data. If not, ask:

"Run /context in this session terminal and let me know when you're done.
I can't run slash commands myself, but once I can see the breakdown I'll
audit everything it flags."

STOP HERE. Do NOT proceed until the user has run /context. The breakdown
determines audit priority; without it, the audit is guessing.

## Step 2: Config Audit

Run the bundled config scanner first — it inventories everything that
contributes to per-turn context:

```bash
python3 "$SKILL_DIR/scripts/scan_configs.py"
```

Substitute the skill's absolute base directory for `$SKILL_DIR` (it's
announced at the top of this invocation). Output is a single JSON
object; use the sections below to interpret each field.

### MCP Servers

`/context` tells you the real overhead (System tools bucket). If that
bucket is small (< 5k), MCP servers are lazy-loaded and cheap — don't
over-penalize. If large, drill in:

- Count user-configured servers from `~/.claude.json > mcpServers` and
  project-scoped `projects[<cwd>] > mcpServers` (the scan scripts
  already do this).
- Look for redundant tool schemas: servers with 40 tools where only
  3 get called — narrow via per-server allowlist rather than
  uninstalling.

**CLI-alternative candidates.** Scanner emits
`cli_alternative_candidates[]` listing user-configured MCP servers
that match a known-heavyweight registry (GitHub, GitLab, AWS, GCP,
Kubernetes, Docker, Terraform, Postgres, Jira, Linear, Trello,
Playwright, Puppeteer, Stripe, Sentry, filesystem/memory/fetch
built-ins, and more). For each match, flag as a **WARNING** with the
suggested CLI and the specific reason:

- `github` MCP has 40+ tools and loads their schemas every turn —
  `gh` covers issues, PRs, workflows, releases, and repo ops at zero
  token cost when idle. Same story for `gitlab`/`glab`, `aws`/`aws`
  CLI, `gcp`/`gcloud`, `kubernetes`/`kubectl`, and so on.
- The CLI-first rule of thumb: if a reasonable CLI exists and the
  MCP server has > 5 tools, the CLI is almost always cheaper
  *unless* you specifically need schema-level awareness of the
  responses (rare).
- Context7 (docs server) and similar narrow-purpose servers don't
  have obvious CLI replacements — they aren't in the registry.

See Step 3 "MCP log scan" for broken/stale detection.

### CLAUDE.md

Scanner returns `claude_md.files[]` (path, line count, mtime) with
`@imports` followed, plus `claude_md.total_lines`.

Test every rule against five filters:

| Filter | Flag when... |
|--------|-------------|
| Default | Claude already does this without being told ("write clean code", "handle errors") |
| Contradiction | Conflicts with another rule in same or different file |
| Redundancy | Repeats something already covered elsewhere |
| Bandaid | Added to fix one bad output, not improve outputs generally |
| Vague | Interpreted differently every time ("be natural", "use good tone") |

If `total_lines > 200`, look for progressive-disclosure wins: rules
that only apply to specific tasks (API conventions, deployment steps,
testing guidelines) should move to reference files with one-line
pointers.

**Ghost references.** Scanner emits `ghost_refs[]`: slash-command-like
references (`/foo`) in CLAUDE.md that don't resolve to any installed
skill or command. These rot whenever you reorganize — recommend
removal. Each one is also a tiny correctness hazard (Claude may try
to invoke the dead name).

**Rot signal.** Cross-reference `claude_md.files[].mtime` with the
behavioral scan's `correction_user_turns / user_turns_sampled` ratio
(Step 3). A stale CLAUDE.md (> 90 days old) plus a high correction
rate (> 15%) is strong evidence the rules have drifted from what the
user actually wants. Recommend a review pass.

### Skills

Scanner emits `skills[]` with `{name, scope, path, body_lines, mtime}`
and `flags.skills_oversize` / `flags.skills_critical`.

For each oversize skill (>200 lines) or critical (>500):
- Run the same five filters on the body.
- Check for restated goals, hedging ("you may want to"), synonymous
  instructions ("be concise" + "keep it short" + "don't be verbose").
- If the body is mostly example code or long scripts, recommend
  extracting to sibling files under a `scripts/` or `examples/` dir
  and referencing them — this skill does exactly that.

Also compare descriptions pairwise. If two skills have highly
overlapping descriptions (same triggers, same verbs), the router
wastes tokens disambiguating. Flag the overlap and recommend merging
or narrowing triggers.

**Cache stability.** Skill descriptions are in every turn's prompt
cache. If a skill's `mtime` falls inside the behavioral window AND
`cache_hit_rate` dropped, flag it as cache churn — editing skills
mid-sessions silently tanks hit rate.

### Agents

Scanner emits `agents[]` (user and project scope) and
`flags.agents_oversize`. Agents are system prompts for subagents
spawned via the `Agent` tool. Each spawn pays the agent's prompt
budget.

Audit:
- Body size (same >200 / >500 thresholds as skills).
- Usage via Step 3's `agent_subagent_types` — agents never called
  are dead weight. With zero window usage, flag for removal unless
  the user confirms they're for future use.
- Description overlap with skills or other agents.

### Slash Commands

Scanner emits `commands[]` and `flags.commands_oversize`. Commands
are less chatty than skills (only load when invoked) but dead
commands still clutter `/help` output and can be confused with
ghost refs. Cross-check against `ghost_refs` — if a CLAUDE.md
mentions `/foo` and no command named `foo` exists, that's the
correct resolution.

### Plugins

Scanner emits `plugins_enabled[]` from the merged settings. Each
enabled plugin may contribute skills, agents, hooks, and MCP
servers. For each plugin with zero observed use (no matching entries
in `skill_top`, `agent_subagent_types`, hooks firing, or MCP tool
calls) over the window, recommend disabling it.

### Hooks

Scanner emits `hooks` (per-scope count of configured hooks). Hooks
run on every matching event — even a no-op fork costs latency and
tokens if it prints anything. Flag:

- Hooks guarded solely by an `|| true` or env-var check — they fork
  a shell every event for nothing. Remove unless you actively need
  them (this skill flagged one such batch earlier).
- Hook counts > 10 in any scope — audit whether each is earning its
  cost.
- `disableAllHooks: true` — note it in the report so the user knows
  hooks aren't running at all.

### Settings

Scanner reads every persisted settings source and emits `misc`
(merged in precedence order, lowest → highest):

1. `~/.claude/settings.json` (user)
2. `~/.claude/settings.local.json` (user local — not in official
   precedence docs but read in practice)
3. `<cwd>/.claude/settings.json` (project)
4. `<cwd>/.claude/settings.local.json` (project local)
5. **Managed / enterprise** — loaded from the first existing path:
   - macOS: `/Library/Application Support/ClaudeCode/managed-settings.json`
   - Linux/WSL: `/etc/claude-code/managed-settings.json`
   - Windows: `C:\Program Files\ClaudeCode\managed-settings.json`

   Managed settings take highest precedence and cannot be overridden
   by the user; `settings.managed_path` reports which file was used
   (null if none). Source:
   <https://code.claude.com/docs/en/settings.md>.

Relevant fields in `misc`:

| Setting | Flag if | Recommended |
|---------|---------|-------------|
| `autoCompactWindow` | Missing *and* sessions hit autocompact (see Step 3) | ~75% of the model's context window in tokens (e.g. `150000` for 200k models, `750000` for 1M). Schema range: 100000–1000000. |
| `env.BASH_MAX_OUTPUT_LENGTH` | At default (30–50k) | `"150000"` (string) |
| `disableSkillShellExecution` | True (if user depends on skill scripts) | Note in report |
| `advisorModel` | Missing or set to a weaker model than default | `"opus"` or leave default |
| `skillListingBudgetFraction` / `skillListingMaxDescChars` | Raised above defaults | Standard defaults unless user is intentionally spending context on skill descriptions |

Before recommending `autoCompactWindow`, confirm from Step 3 that
`sessions_hit_autocompact > 0`. Same for `BASH_MAX_OUTPUT_LENGTH` —
if no tool_result outliers above the default, there's no waste to
fix.

**Permissions staleness.** Cross-reference `permissions.allow` with
Step 3's `bash_commands_sample` and `tool_top`. A `Bash(git *)` rule
that never matched an observed command in the window is a candidate
for removal. These cost nothing but clutter audits.

### File Permissions

Scanner emits `bloat_dirs_present[]`. If non-empty and
`permissions.deny` lacks matching entries, recommend adding them:

| If this exists... | Should deny reads under... |
|-------------------|---------------|
| package.json | node_modules, dist, build, .next, coverage |
| Cargo.toml | target |
| go.mod | vendor |
| pyproject.toml / requirements.txt | __pycache__, .venv, *.egg-info |

### .mcp.json files

Scanner emits `mcp_json_files[]`. Project-scoped MCP configs live
here. Walk each up from `cwd` to `$HOME`. If a `.mcp.json` exists
that the user didn't author, it's team-shared — audit the same way
as `~/.claude.json > mcpServers`.

## Step 3: Behavioral Scan (JSONL)

Static config says what's *loaded*. JSONL says what's *used*. This is
where the real wins are.

Transcripts live under `~/.claude/projects/<slug>/*.jsonl` where
`<slug>` is the project path with `/` → `-`. The bundled scan script
resolves this automatically from `cwd`; if the script reports
`{"error": "no session history"}`, skip Step 3.

**Window:** default to last 30 days of session files (by mtime). Let
the user override.

**Critical:** JSONL files can be tens of MB each and contain sensitive
history. NEVER `Read` them into context. Use the bundled script, which
streams them and emits JSON aggregates only.

### Aggregation script

Run from the project root (the script derives the JSONL path from
`cwd`):

```bash
python3 "$SKILL_DIR/scripts/scan_jsonl.py" 30
```

Where `$SKILL_DIR` is the skill's base directory announced at the top
of this invocation (substitute the absolute path literally). The
argument is the window in days; default 30.

### Derive findings from the aggregate

- **Unused MCP servers.** For each configured MCP server, count calls
  to tools prefixed `mcp__<server>__*` in `tool_top`. Zero calls in
  the window → dead weight. Flag for removal or `disabled: true`.
- **Unused MCP tools.** For servers that *are* used, list tools in
  that server never called → candidates for allowlist narrowing.
- **Unused skills.** Compare configured skills (Step 2) against
  `skill_top`. Skills with zero invocations in the window are dead
  weight in the router.
- **Unused agents.** Compare configured agents (Step 2) against
  `agent_subagent_types`. Never-spawned agents over the window are
  candidates for removal.
- **Cache hit rate.**
  - > 80% — healthy
  - 60–80% — acceptable
  - 40–60% — warning (prompt churn; someone's editing CLAUDE.md mid-session
    or MCP list is unstable)
  - < 40% — critical
- **Autocompact rate.** `sessions_hit_autocompact / sessions`. If > 30%,
  context is being packed too tight — lower the override, prune harder,
  or split long sessions.
- **Correction rate.** `correction_user_turns / user_turns_sampled`.
  High rate (> 15%) points at missing CLAUDE.md guidance or skills
  that aren't firing. Don't score this — surface it as an INFO finding
  with examples.
- **Turn cost.** Look at `avg_input_per_turn` *and* `p95_input_per_turn`,
  `p99_input_per_turn`. Avg > 100k → context is chronically wide.
  p95 >> avg → specific turns are ballooning — often a giant tool
  result (see `large_tool_results_top`) or a runaway subagent. Tightening
  p95 is usually higher ROI than trimming the average.
- **Tool error rate.** `tool_error_rates` is a `{tool: {calls, errors,
  rate}}` map of tools whose results came back `is_error: true`. A
  high-volume tool with rate > 10% suggests a skill or CLAUDE.md rule
  is pushing Claude to use something that doesn't fit, or a missing
  permission / bad argument shape. Surface each as a WARNING with
  sample counts; the fix is usually in the skill body, not the tool.
- **Read-path repetition.** `read_paths_top` lists the 20 files
  Claude Reads most. A file read in many sessions is a candidate for
  either: (a) a CLAUDE.md pointer so Claude knows it exists without
  opening it, or (b) a pre-digested summary doc if the file is large.
- **Large tool results.** `large_tool_results_top` is a list of
  `{tool, bytes}` for single tool_result outputs over 30KB. Patterns:
  - `Bash` outliers → the command is dumping something the skill
    should pipe to a file (long logs, `ls -R`, test output).
  - `Read` outliers → Claude is reading files that might be generated
    (lockfiles, minified assets, compiled output) — a
    `permissions.deny` rule usually solves it.
  - `WebFetch` outliers → consider caching.
- **Bash command diversity.** `bash_commands_sample` contains up to
  500 commands (first 300 chars each). Scan for repetitive patterns:
  if the same `git log …` or `npm run test` appears hundreds of
  times, a skill or CLAUDE.md pointer could short-circuit some of
  the invocations.

### MCP log scan (high-signal)

Claude Code writes per-server connection logs to a cache directory
outside `~/.claude/`. A configured server whose logs show connection
failures every session is pure waste: its tool schemas load into
context every turn but the server never actually works.

**Paths to check** (try in order; first one that exists wins):

| OS | Path |
|----|------|
| macOS | `~/Library/Caches/claude-cli-nodejs/<slug>/mcp-logs-<server>/*.jsonl` |
| Linux | `~/.cache/claude-cli-nodejs/<slug>/mcp-logs-<server>/*.jsonl` |

Slug = same transformation as the transcript dir (`/` → `-`).

For each `mcp-logs-<server>` directory, count per server over the
window:

- Total sessions (one `.jsonl` file per session launch)
- `"error"` keys
- Lines matching `Connection failed` or `HTTP Connection failed`
- Lines matching `Executable not found`, `ENOENT`, `timeout`, `404`,
  `401`, `403`

A server with `connection_failures >= sessions` is **broken** —
every launch fails. Report it as CRITICAL and recommend removing
or fixing the MCP entry.

Also read `~/.claude/mcp-needs-auth-cache.json` (a flat JSON map of
`{server_name: {timestamp}}` for claude.ai MCP servers awaiting
OAuth). Entries here are configured but not authenticated — warn
once per entry; they're lighter waste than broken servers but still
load schemas.

Run the bundled script:

```bash
python3 "$SKILL_DIR/scripts/scan_mcp_logs.py" 30
```

Same convention as `scan_jsonl.py` — substitute the skill's absolute
base directory for `$SKILL_DIR`.

Findings (script emits `origin: "user" | "builtin"` per server — use
it to pick the right remediation):

- **Broken user-configured server** (`broken: true`, `origin: user`).
  CRITICAL. Remove via `claude mcp remove <name>` or delete the entry
  from `~/.claude.json > mcpServers`. Every session pays for its
  tool schemas and gets nothing back.
- **Broken built-in server** (`broken: true`, `origin: builtin`).
  Rare — the claude.ai proxy transport usually connects cleanly.
  Recommend toggling off via the `/mcp` slash command UI.
- **Needs-auth MCP server.** Handling depends on origin:
  - **Built-in `claude.ai *` servers** (Gmail, Calendar, Drive) can't
    be removed per-server. Options: (a) ignore — with Tool Search
    (default) they're nearly free when unauthenticated; (b) toggle
    individual ones off via the `/mcp` slash command UI; (c) turn
    the whole group off via env var `ENABLE_CLAUDEAI_MCP_SERVERS=false`
    (shell or `settings.json > env`). INFO, not WARNING.
  - **User-configured servers** left unauthenticated are stale config:
    recommend authenticating or removing via
    `claude mcp remove <name>`. WARNING.

The canonical source of truth for user-configured servers is
`~/.claude.json > mcpServers` (globally) and
`~/.claude.json > projects[<cwd>] > mcpServers` (per-project). The
scan script already reads both.

## Step 4: Score and Report

Score starts at 100. Deduct per issue:

| Issue | Points |
|-------|--------|
| CLAUDE.md (incl. imports) > 200 lines | -10 |
| CLAUDE.md (incl. imports) > 500 lines | -20 |
| Per 5 rules flagged by filters | -5 |
| Contradictions between files | -10 |
| Overlapping skill descriptions (per pair) | -5 |
| Missing `autoCompactWindow` *and* sessions hit autocompact | -10 |
| Missing `BASH_MAX_OUTPUT_LENGTH` | -5 |
| Skill body > 200 lines | -5 each |
| Skill body > 500 lines | -10 each |
| Per heavyweight MCP server configured (>5k tokens in `/context`) | -3 each |
| Per MCP server with a known CLI alternative (`cli_alternative_candidates`) | -5 each |
| No deny rules + bloat dirs exist | -10 |
| **Behavioral:** per unused heavyweight MCP server (window) | -5 |
| **Behavioral:** per unused skill (window) | -2 (cap -10) |
| **Behavioral:** cache hit rate < 60% | -10 |
| **Behavioral:** cache hit rate < 40% | additional -10 |
| **Behavioral:** autocompact > 30% of sessions | -5 |
| **MCP logs:** per broken server (connect-fails every session) | -15 each |
| **MCP logs:** per needs-auth user-configured server | -3 each |
| **MCP logs:** per needs-auth built-in `claude.ai *` server | 0 (INFO only) |
| Agent body > 200 lines | -5 each |
| Agent body > 500 lines | -10 each |
| Slash-command body > 200 lines | -3 each |
| **Behavioral:** per unused agent (window) | -3 (cap -9) |
| **Behavioral:** per unused plugin (window) | -5 |
| **Behavioral:** per tool with error rate > 10% and > 20 calls | -5 each |
| **Behavioral:** p95 turn cost > 150k | -5 |
| **Behavioral:** p95 turn cost > 300k | additional -10 |
| Ghost slash references in CLAUDE.md | -2 each (cap -10) |
| CLAUDE.md stale (> 90d) AND correction rate > 15% | -10 |
| Hooks counted > 10 in any scope | -5 |

"Heavyweight" = servers that load significant tool schemas into every
turn. Lazy-loaded auth stubs and 2-tool servers that show up under
"Available" in `/context` rather than the top-level System tools
budget are not heavyweight — don't penalize them, they cost almost
nothing when idle.

Floor at 0. Output this format:

```
# Context Audit

Score: {N}/100 [{CLEAN|NEEDS WORK|BLOATED|CRITICAL}]

## Context Breakdown (from /context)
{key numbers from /context}

## Behavioral Scan ({days}d, {sessions} sessions, {turns} turns)
Cache hit rate: {%}
Autocompact: {N}/{total} sessions
Turn cost: avg {k} / p95 {k} / p99 {k}
Broken MCP servers: {list or "none"}
Needs-auth MCP servers: {list or "none"}
Unused MCP servers: {list or "none"}
CLI-alternative candidates: {server → cli, or "none"}
Unused skills: {list or "none"}
Unused agents: {list or "none"}
Tools with >10% error rate: {list or "none"}
Top read paths: {top 5 file paths}
Large tool results: {tool + bytes for top 3}
Top tools: {top 5 by call count}

## Issues Found

### [{CRITICAL|WARNING|INFO}] {Category}
{What's wrong}
Fix: {One-line actionable fix}

### Rules to Cut
{Each flagged rule: the text, which filter, one-line reason}

### Conflicts
{Contradictions between files, with paths}

## Top 3 Fixes
1. {Highest-impact fix}
2. {Second}
3. {Third}
```

Score labels: 90–100 CLEAN, 70–89 NEEDS WORK, 50–69 BLOATED, 0–49 CRITICAL.
Severity: CRITICAL > 10pts, WARNING 5–10pts, INFO < 5pts.

## Step 5: Offer to Fix

After the report:

"Want me to fix any of these? I can:
- Show a cleaned-up CLAUDE.md with flagged rules removed, ghost refs
  stripped, and stale imports removed
- Add missing settings.json configs
- Add permissions.deny rules for build artifacts
- Prune stale permissions.allow rules that never matched in the window
- Remove broken user-configured MCP servers — I'll run
  `claude mcp remove <name>` for each, or show the
  `~/.claude.json > mcpServers` diff
- Disable unused user-configured MCP servers (set `disabled: true`) or
  narrow their tool allowlists
- Swap heavyweight MCP servers for their CLI equivalents (e.g.
  `github` MCP → `gh`; `aws` MCP → `aws`; `kubernetes` MCP →
  `kubectl`). I can remove the MCP entry and verify the CLI is on
  PATH; most usage transfers one-to-one
- For built-in claude.ai servers (Gmail/Calendar/Drive): I can't
  toggle individual ones from here, but you can turn each one off
  interactively via `/mcp`, or disable the whole group by adding
  `ENABLE_CLAUDEAI_MCP_SERVERS=false` to `settings.json > env`
- Show which skills / agents / commands to compress, merge, or remove
- Disable unused plugins in `enabledPlugins`
- Remove no-op hooks (common pattern: hook guarded only by an
  `|| true` when an env var is unset)"

Auto-apply settings.json and `permissions.deny` (safe, reversible).
Show diffs for CLAUDE.md, skill bodies, and MCP disable/allowlist
changes — let the user confirm before modifying.
