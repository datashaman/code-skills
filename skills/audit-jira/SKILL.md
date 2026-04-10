---
name: audit-jira
description: |
  Jira project health audit. Queries five dimensions of work item data to identify
  velocity trends, backlog rot, bug clusters, assignee concentration risk, and
  firefighting patterns — then cross-references findings to surface danger zones.
  Use when: "audit jira", "project health", "backlog analysis", "team velocity",
  "who owns this work", "what keeps breaking", "sprint patterns".
---

# Jira Project Health Audit

Query five dimensions of Jira data to build a picture of team health, backlog quality, and delivery risk.

Uses `acli` (Atlassian CLI). Install at https://developer.atlassian.com/cloud/acli/ and authenticate with `acli jira auth` before running.

## Arguments

- `project` (required): Jira project key (e.g. `ENG`, `PLAT`). Can be passed positionally as the first argument — `/audit-jira ENG` is equivalent to `/audit-jira project=ENG`.
- `since` (optional): Start date for completed-work analysis in ISO format (default: `"1 year ago"`, expressed as a JQL date like `"-52w"`)
- `board` (optional): Board ID to use for sprint analysis. If not provided, look it up via `acli jira board search --project $PROJECT --json`.

## Steps

### 0. Resolve the board ID

If the user did not provide a `board` argument, find it:

```bash
acli jira board search --project $PROJECT --json
```

Pick the first board ID from the results. If multiple boards exist, ask the user which one to use.

Then fetch recent sprints for velocity bucketing:

```bash
acli jira board list-sprints --id $BOARD --state closed,active --limit 12 --json
```

### 1. Gather raw data

Run all five queries in parallel using Bash. Use `--paginate` to get full result sets. Use `--json` for structured output and parse with `jq`.

**Velocity / throughput** — completed issues in the window:
```bash
acli jira workitem search \
  --jql "project = $PROJECT AND statusCategory = Done AND resolutiondate >= $SINCE ORDER BY resolutiondate ASC" \
  --fields "key,issuetype,assignee,priority,resolutiondate,labels,components" \
  --paginate --json
```

**Backlog health** — all open issues ordered oldest first:
```bash
acli jira workitem search \
  --jql "project = $PROJECT AND statusCategory in ('To Do','In Progress') ORDER BY created ASC" \
  --fields "key,issuetype,summary,assignee,priority,status,created,story_points,labels,components" \
  --paginate --json
```

**Bug clusters** — all bugs in the window:
```bash
acli jira workitem search \
  --jql "project = $PROJECT AND issuetype = Bug AND created >= $SINCE ORDER BY created ASC" \
  --fields "key,summary,assignee,priority,status,resolutiondate,labels,components,created" \
  --paginate --json
```

**Assignee concentration** — all issues in the window:
```bash
acli jira workitem search \
  --jql "project = $PROJECT AND created >= $SINCE ORDER BY created ASC" \
  --fields "key,issuetype,assignee,status,priority" \
  --paginate --json
```

**Firefighting patterns** — high-priority and escalation-labeled issues:
```bash
acli jira workitem search \
  --jql "project = $PROJECT AND (priority in (Highest, High) OR labels in (hotfix, urgent, escalation, incident)) AND created >= $SINCE ORDER BY created DESC" \
  --fields "key,summary,priority,labels,assignee,created,resolutiondate,status" \
  --paginate --json
```

### 2. Analyze each dimension

For each area, produce a short analysis section using `jq` to aggregate the JSON output.

#### Velocity & Throughput
- Count completed issues per month: group `resolutiondate` by `YYYY-MM`
- Break down by issue type (story, task, bug, spike)
- Identify the trajectory: growing, stable, declining, erratic
- Flag sharp drops or spikes and hypothesize causes (staff changes, release crunches, holidays)
- Note current velocity relative to the period average
- Cross-reference with sprint data from step 0 to show per-sprint throughput

#### Backlog Health
- Count total open issues, split by status (To Do vs In Progress)
- Age distribution: bucket by `created` date — 0-30d / 30-90d / 90-180d / 180d+
- Unestimated items: issues with no `story_points` value
- Unassigned items: issues with no `assignee`
- Stale in-progress: items in `In Progress` status with `created` > 14 days ago and no recent activity signal
- Priority skew: what fraction are High/Highest vs lower priorities

#### Bug Clusters
- Group bugs by `components` and `labels`, count per group
- Calculate bug ratio: bugs as a percentage of all completed work in the window
- **Cross-reference with backlog**: open bugs that are also old and unassigned are highest-risk
- Flag any component with a disproportionate share (2x+ the median)
- Note if bug volume is growing or shrinking month-over-month

#### Assignee Concentration
- Group all issues in the window by `assignee`, count completed and in-progress separately
- Calculate what percentage of work the top assignee accounts for
- Flag single-assignee risk: if one person accounts for 40%+ of in-progress work, that's a bus factor concern
- Identify unassigned work: issues with no owner
- Note contributors active in earlier months but absent recently

#### Firefighting Patterns
- Count P0/P1 (Highest/High) issues and hotfix/escalation/incident-labeled items
- Calculate frequency (e.g. "2 incidents per month")
- Flag if volume is increasing month-over-month
- If frequent: signals unreliable releases, missing test coverage, or a fragile deploy process
- If absent: either the team is stable, or priority/label discipline is inconsistent — check a sample of recent issues before concluding stability

### 3. Cross-reference and synthesize

Combine findings across all five dimensions:

- **Danger zones**: Components with high bug counts AND old backlog items AND a single assignee. Highest-risk areas
- **Team health signals**: Is velocity stable? Are issues distributed? Is knowledge shared or siloed?
- **Process signals**: Are firefighting events increasing? Do bugs cluster after certain sprints?
- **Backlog rot indicators**: Items bumped repeatedly but never done. Stale in-progress with no owner. Unestimated work aged 90d+

### 4. Generate the report

Write the report into the skill's own directory, under a subfolder named after the project key. Full path: `{skill-base-dir}/{project-key}/YYYY-MM-DD-audit.md`. Create the subfolder if it doesn't exist.

```markdown
# Jira Project Health Audit

**Date**: [date] | **Project**: [key] | **Board**: [id] | **Window**: [since period] | **Total issues in window**: [count]

## Executive Summary

[3-5 bullet points capturing the most important findings. Lead with risks.]

## Risk Matrix

| Risk | Severity | Evidence | Recommendation |
|------|----------|----------|----------------|
| [risk name] | HIGH/MEDIUM/LOW | [data point from the analysis] | [actionable next step] |

---

## 1. Velocity & Throughput

| Month | Completed | Stories | Bugs | Tasks | Spikes |
|-------|-----------|---------|------|-------|--------|

[ASCII bar chart of monthly completions]

**Trajectory**: [growing / stable / declining / erratic]
**Current velocity vs period average**: [above / at / below]

[Notable inflection points and hypothesized causes]

---

## 2. Backlog Health

**Total open issues**: [N] ([X] To Do, [Y] In Progress)
**Unestimated**: [N] ([X]%)
**Unassigned**: [N] ([X]%)

### Age distribution
| Age bucket  | Count | % of backlog |
|-------------|-------|-------------|
| 0-30 days   | N     | X%          |
| 30-90 days  | N     | X%          |
| 90-180 days | N     | X%          |
| 180+ days   | N     | X%          |

### Stale in-progress (>14 days)
| Issue | Summary | Assignee | Days in progress |
|-------|---------|----------|-----------------|

**Analysis**: [interpretation]

---

## 3. Bug Clusters

### Bugs by component
| # | Component | Bug count | % of all bugs |
|---|-----------|-----------|--------------|

### Bugs by label
| # | Label | Bug count |
|---|-------|-----------|

**Bug ratio**: [N]% of completed work was bugs (window average)

### Highest-risk areas (bugs + stale backlog)
| Component/Label | Bug count | Open bugs | Oldest open | Primary assignee |
|----------------|-----------|-----------|-------------|-----------------|

**These areas are the top candidates for dedicated attention or test investment.**

---

## 4. Assignee Concentration

### All work in window
| # | Assignee | Issues | % of total |
|---|----------|--------|------------|

### Current in-progress
| # | Assignee | Issues | % of in-progress |
|---|----------|--------|-----------------|

### Knowledge gap analysis
[Assignees active earlier in the window but absent recently, what they likely owned]

---

## 5. Firefighting Patterns

**Total P0/P1 issues**: [N] in [time window]
**Hotfix/escalation/incident labels**: [N]
**Frequency**: [X per month/quarter]

| Issue | Summary | Priority | Created | Resolved | Assignee |
|-------|---------|----------|---------|----------|---------|

[Analysis of what this signals about release process and stability]

---

## Cross-Reference Analysis

### Danger zones
[Components/areas that score badly across multiple dimensions — the highest-value findings]

### Positive signals
[Areas that show health — steady velocity, distributed ownership, low bug rate]

---

## Recommendations

1. [Most urgent action based on findings]
2. [Second priority]
3. [Third priority]
```

### 5. Present findings

- Tell the user where the report was saved
- Lead with the executive summary and risk matrix
- Highlight the cross-referenced danger zones — these are the highest-value findings
- If assignee concentration is concerning, call it out prominently
- Ask if they want to drill deeper into any specific area (e.g. read the actual stale issues, trace a specific assignee's workload, analyze a specific danger zone component)
