# audit-context

**Context audit** for Claude Code setups: finds token waste and context bloat across every surface that contributes to per-turn cost, then mines local session transcripts and MCP connection logs for the "what actually happens" signals. Returns a 0–100 health score with specific, actionable fixes.

## When to use

Good prompts: *audit my context*, *check my settings*, *why is Claude so slow*, *token optimization*, *context audit*.

## How it works

1. **`/context` data** — the audit starts from the real overhead numbers shown by `/context`. The skill asks the user to run it (Claude can't run slash commands itself).
2. **Config audit** (`scan_configs.py`) — inventories user + project scope:
   - MCP servers (user-configured in `~/.claude.json`, built-in `claude.ai *`, project `.mcp.json` files walked from cwd)
   - CLAUDE.md with `@imports` followed recursively; ghost `/slash` references; file mtimes for rot detection
   - Skills, agents, slash commands (body line counts, oversize flags)
   - Plugins enabled, hooks per scope
   - Merged settings: `autoCompactWindow`, `BASH_MAX_OUTPUT_LENGTH`, `disableAllHooks`, `advisorModel`, etc.
   - `permissions.allow` / `deny` plus detected bloat dirs (`node_modules`, `target`, …)
   - Applies five filters to rules: default, contradiction, redundancy, bandaid, vague
3. **Behavioral scan** (`scan_jsonl.py`) — streams session transcripts from `~/.claude/projects/<slug>/*.jsonl` via Python (never `Read`s them — they can be tens of MB and contain sensitive history). Returns aggregates only:
   - Cache hit rate, autocompact events, correction rate
   - Turn-cost percentiles (p50 / p95 / p99) to catch balloons the average hides
   - Per-tool error rates (flags tools failing > 10% of calls)
   - Top repeated `Read` paths (CLAUDE.md pointer candidates)
   - Large tool-result outliers (>30 KB) grouped by originating tool
   - `Agent` subagent-type usage (for unused-agent detection)
   - Bash command sample for cross-referencing `permissions.allow` staleness
4. **MCP log scan** (`scan_mcp_logs.py`) — parses `~/Library/Caches/claude-cli-nodejs/<slug>/mcp-logs-*/` to flag broken servers (connection failures every session) and stale needs-auth entries. Classifies each server as **user-configured** (can be removed) or **built-in `claude.ai *`** (only disableable via `/mcp` UI or `ENABLE_CLAUDEAI_MCP_SERVERS=false` env var).
5. **Score and report** — 0–100 score with CLEAN / NEEDS WORK / BLOATED / CRITICAL bands, plus top-3 fixes.
6. **Offer to fix** — auto-applies safe settings changes; shows diffs for CLAUDE.md / skill / MCP edits before modifying.

## Arguments

None. The skill runs against the current project (uses `$PWD` to locate transcripts) and asks the user for anything else it needs.

## Files in this folder

| File                        | Role                                                                                        |
| --------------------------- | ------------------------------------------------------------------------------------------- |
| `SKILL.md`                  | Full agent instructions: audit steps, filters, report template                              |
| `README.md`                 | This overview                                                                               |
| `scripts/scan_configs.py`   | Inventories skills, agents, commands, plugins, CLAUDE.md (with `@imports`), `.mcp.json`, hooks, all settings scopes (including managed), and matches user-configured MCP servers against a CLI-alternative registry (github→gh, aws→aws, kubernetes→kubectl, etc.); emits JSON |
| `scripts/scan_jsonl.py`     | Streams `~/.claude/projects/<slug>/*.jsonl` and emits behavioural aggregates (cache hit, turn-cost percentiles, tool error rates, top Read paths, large tool-result outliers, Agent subagent types) |
| `scripts/scan_mcp_logs.py`  | Parses `~/Library/Caches/claude-cli-nodejs/<slug>/mcp-logs-*/` to flag broken/stale servers, classified by origin (user-configured vs built-in `claude.ai *`) |

## Requirements

- Claude Code with `/context` available (used as the first data source)
- `python3` on PATH (used by the JSONL aggregation script; stdlib only)
- Read access to `~/.claude/projects/` for behavioral scan (skipped gracefully if absent)

For the full step-by-step workflow, open **`SKILL.md`**.
