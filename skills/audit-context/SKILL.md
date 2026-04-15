---
name: audit-context
description: >
  Audit your Claude Code setup for token waste and context bloat. Use when
  the user says "audit my context", "check my settings", "why is Claude so
  slow", "token optimization", "context audit", or runs /audit-context.
  Starts by running /context to see real overhead, then audits MCP servers,
  CLAUDE.md rules, skills, settings, and file permissions. Mines session
  JSONL transcripts for behavioral signals (unused tools, cache hit rate,
  autocompact frequency). Returns a health score with specific fixes.
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

Audit each category from largest overhead to smallest. Run checks in
parallel where possible.

### MCP Servers

Each configured server loads full tool definitions into context every
turn (~15k–20k tokens each, more with many tools).

- Count configured servers in `settings.json` and `.mcp.json`.
- Flag servers with CLI alternatives (Playwright, GitHub, Google
  Workspace all have CLIs that cost zero tokens when idle).
- Check each server's `disabled` flag and per-server `enabledMcpjsonServers`
  / tool allowlist — a server with 40 tools where only 3 are used is
  fixable via allowlist without removing the server.
- Report total MCP overhead from /context output.

### CLAUDE.md (follow imports)

Read all CLAUDE.md files: project root, `.claude/CLAUDE.md`,
`~/.claude/CLAUDE.md`. Then follow `@path/to/file` import lines
recursively — imported files count toward the same context budget.
Report the combined line count.

Test every rule against five filters:

| Filter | Flag when... |
|--------|-------------|
| Default | Claude already does this without being told ("write clean code", "handle errors") |
| Contradiction | Conflicts with another rule in same or different file |
| Redundancy | Repeats something already covered elsewhere |
| Bandaid | Added to fix one bad output, not improve outputs generally |
| Vague | Interpreted differently every time ("be natural", "use good tone") |

If total (including imports) > 200 lines, look for progressive disclosure
opportunities: rules that only apply to specific tasks (API conventions,
deployment steps, testing guidelines) should move to reference files
with one-line pointers. A lean CLAUDE.md with universal context is fine
as a single file.

### Skills

Scan `.claude/skills/*/SKILL.md` and `~/.claude/skills/*/SKILL.md`.
Skill *descriptions* are always loaded; bodies are fetched on invocation.

For each skill:
- Count lines in the body (flag > 200, critical > 500).
- Run the same five filters on instructions.
- Check for restated goals, hedging ("you may want to"), synonymous
  instructions ("be concise" + "keep it short" + "don't be verbose").

Also compare descriptions pairwise. If two skills have highly
overlapping descriptions (same triggers, same verbs), the router
wastes tokens disambiguating. Flag the overlap and recommend merging
or narrowing triggers.

### Settings

Check `settings.json` for:

| Setting | Flag if | Recommended |
|---------|---------|-------------|
| `autoCompactWindow` | Missing *and* sessions hit autocompact (see Step 3) | ~75% of the model's context window in tokens (e.g. `150000` for 200k models, `750000` for 1M). Schema range: 100000–1000000. |
| `env.BASH_MAX_OUTPUT_LENGTH` | At default (30–50k) | `"150000"` (string) |

Before recommending `autoCompactWindow`, confirm from Step 3 that
`sessions_hit_autocompact > 0`. If the behavioral scan shows zero
autocompacts, the default is fine and setting this is noise.

Also scan `permissions.allow` for stale entries: commands or patterns
that haven't been used in the behavioral scan window (Step 3). These
cost nothing but clutter audits.

### File Permissions

Check `settings.json` for `permissions.deny` rules. If missing, check
whether bloat directories exist in the project:

| If this exists... | Should deny reads under... |
|-------------------|---------------|
| package.json | node_modules, dist, build, .next, coverage |
| Cargo.toml | target |
| go.mod | vendor |
| pyproject.toml / requirements.txt | __pycache__, .venv, *.egg-info |

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
- **Turn cost.** Average input tokens per assistant turn =
  `(cache_read + cache_create + input) / assistant_turns`. Outliers
  above 100k are candidates for context-window tightening.

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

Findings:

- **Broken MCP server** (`broken: true`). CRITICAL. Recommend removing
  the entry or fixing the command/URL. Every session pays for its
  tool schemas and gets nothing back.
- **Needs-auth MCP server.** WARNING. Either authenticate or remove.

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
| No deny rules + bloat dirs exist | -10 |
| **Behavioral:** per unused heavyweight MCP server (window) | -5 |
| **Behavioral:** per unused skill (window) | -2 (cap -10) |
| **Behavioral:** cache hit rate < 60% | -10 |
| **Behavioral:** cache hit rate < 40% | additional -10 |
| **Behavioral:** autocompact > 30% of sessions | -5 |
| **MCP logs:** per broken server (connect-fails every session) | -15 each |
| **MCP logs:** per needs-auth server left stale | -3 each |

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
Broken MCP servers: {list or "none"}
Needs-auth MCP servers: {list or "none"}
Unused MCP servers: {list or "none"}
Unused skills: {list or "none"}
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
- Show a cleaned-up CLAUDE.md with flagged rules removed
- Add missing settings.json configs
- Add permissions.deny rules for build artifacts
- Remove or disable broken MCP servers (those failing every session)
- Disable unused MCP servers (set `disabled: true`) or narrow their
  tool allowlists
- Show which skills to compress or merge"

Auto-apply settings.json and `permissions.deny` (safe, reversible).
Show diffs for CLAUDE.md, skill bodies, and MCP disable/allowlist
changes — let the user confirm before modifying.
