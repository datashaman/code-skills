# audit-context

**Context audit** for Claude Code setups: finds token waste and context bloat across MCP servers, CLAUDE.md rules (including `@` imports), skills, settings, and file permissions — then mines local session JSONL transcripts for behavioral signals (unused tools, cache hit rate, autocompact frequency). Returns a health score with specific, actionable fixes.

## When to use

Good prompts: *audit my context*, *check my settings*, *why is Claude so slow*, *token optimization*, *context audit*.

## How it works

1. **`/context` data** — the audit starts from the real overhead numbers shown by `/context`. The skill asks the user to run it (Claude can't run slash commands itself).
2. **Config audit** — reads MCP config, CLAUDE.md (+imports), skill descriptions/bodies, settings, and `permissions.deny`. Applies five filters to rules: default, contradiction, redundancy, bandaid, vague.
3. **Behavioral scan** — streams session transcripts from `~/.claude/projects/<slug>/*.jsonl` via Python (never `Read`s them — they can be tens of MB and contain sensitive history). Returns aggregates only: tool/skill usage, cache hit rate, autocompact events, correction rate.
4. **Score and report** — 0–100 score with CLEAN / NEEDS WORK / BLOATED / CRITICAL bands, plus top-3 fixes.
5. **Offer to fix** — auto-applies safe settings changes; shows diffs for CLAUDE.md / skill / MCP edits before modifying.

## Arguments

None. The skill runs against the current project (uses `$PWD` to locate transcripts) and asks the user for anything else it needs.

## Files in this folder

| File                        | Role                                                                                        |
| --------------------------- | ------------------------------------------------------------------------------------------- |
| `SKILL.md`                  | Full agent instructions: audit steps, filters, report template                              |
| `README.md`                 | This overview                                                                               |
| `scripts/scan_jsonl.py`     | Streams `~/.claude/projects/<slug>/*.jsonl` and emits behavioural aggregates as JSON        |
| `scripts/scan_mcp_logs.py`  | Parses `~/Library/Caches/claude-cli-nodejs/<slug>/mcp-logs-*/` to flag broken/stale servers |

## Requirements

- Claude Code with `/context` available (used as the first data source)
- `python3` on PATH (used by the JSONL aggregation script; stdlib only)
- Read access to `~/.claude/projects/` for behavioral scan (skipped gracefully if absent)

For the full step-by-step workflow, open **`SKILL.md`**.
