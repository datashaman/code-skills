# audit-jira

**Jira project health audit** via the Atlassian MCP. Queries five dimensions
of work item data to build a picture of team health, backlog quality, and
delivery risk — then cross-references findings to surface danger zones.

## When to use

Good prompts: *audit jira*, *project health*, *backlog analysis*, *team
velocity*, *who owns this work*, *what keeps breaking*.

## Prerequisites

The Atlassian MCP must be connected and authenticated. Connect it via
`/mcp` in Claude Code and authenticate with your Atlassian account.

## Arguments

| Argument  | Default | Purpose |
|-----------|---------|---------|
| `project` | —       | Jira project key (e.g. `ENG`, `PLAT`) — required, can be passed positionally |
| `since`   | `-52w`  | JQL date expression for the analysis window |

**Usage:**
```
/audit-jira ENG
/audit-jira ENG since=-26w
```

## What it audits

1. **Velocity & throughput** — completed issues per month, broken down by
   type. Trajectory: growing / stable / declining / erratic.
2. **Backlog health** — age distribution, unestimated and unassigned items,
   stale in-progress, priority skew.
3. **Bug clusters** — bugs grouped by component and label, bug ratio vs.
   total completed work, highest-risk areas (bugs + stale backlog combined).
4. **Assignee concentration** — bus factor risk, unassigned work, knowledge
   gaps from contributors who've gone quiet.
5. **Firefighting patterns** — P0/P1 volume, hotfix/escalation/incident
   labels, frequency trend. Signals release reliability and test coverage gaps.

## Report output

Audits are written to:

`{skill-base-dir}/{project-key}/YYYY-MM-DD-audit.md`

## Files in this folder

| File       | Role |
|------------|------|
| `SKILL.md` | Full agent instructions: data queries, analysis checklist, report template |
| `README.md` | This overview |
