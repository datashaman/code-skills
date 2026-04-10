---
name: audit-codebase
description: |
  Git-based codebase health audit. Runs five diagnostic git commands to identify
  churn hotspots, bus factor risks, bug clusters, project momentum, and firefighting
  patterns — then cross-references findings to surface danger zones.
  Use when: "audit the codebase", "codebase health", "code archaeology",
  "who owns this code", "what files change most", "bus factor".
---

# Codebase Health Audit

Run five git-based diagnostic commands to build a picture of codebase health, team dynamics, and risk areas — all before reading a single line of source code.

Source: Maciej Piechowski, *Git commands before reading code* — [https://piechowski.io/post/git-commands-before-reading-code/](https://piechowski.io/post/git-commands-before-reading-code/)

## Arguments

- `path` (optional): Subdirectory to scope the analysis to (default: entire repo)
- `since` (optional): Time window for analysis (default: "1 year ago")

## Steps

### 1. Gather raw data

Run all five git commands in parallel using Bash. If the user provided a `path`, append `-- ${PATH}` to the git log commands. Use the `since` argument or default to "1 year ago".

**Churn hotspots** — the 30 most-changed files:

```bash
git log --format=format: --name-only --since="${SINCE}" -- ${PATH} | grep -v '^$' | sort | uniq -c | sort -nr | head -30
```

**Bus factor & authorship** — contributors ranked by commit count (all-time and recent):

```bash
git shortlog -sn --no-merges -- ${PATH}
```

```bash
git shortlog -sn --no-merges --since="6 months ago" -- ${PATH}
```

**Bug clusters** — files most often mentioned in bug-fix commits:

```bash
git log -i -E --grep="fix|bug|broken|hotfix|patch" --name-only --format='' --since="${SINCE}" -- ${PATH} | grep -v '^$' | sort | uniq -c | sort -nr | head -30
```

**Project momentum** — commit count by month:

```bash
git log --format='%ad' --date=format:'%Y-%m' -- ${PATH} | sort | uniq -c
```

**Firefighting patterns** — reverts, hotfixes, and emergency fixes:

```bash
git log --oneline --since="${SINCE}" -- ${PATH} | grep -iE 'revert|hotfix|emergency|rollback|urgent'
```

### 2. Analyze each dimension

For each of the five areas, produce a short analysis section:

#### Churn Hotspots

- List the top 20 most-changed files with their change counts
- Separate expected churn (config, migrations, lock files, changelogs) from concerning churn (application logic, core business files)
- Identify clusters: are the hot files concentrated in one domain/feature or spread across the codebase?
- Call out any files with disproportionately high churn (2x+ the median of the top 20)
- High-churn files signal ongoing maintenance struggles. Per Microsoft Research (2005), churn-based metrics predicted defects more reliably than complexity metrics alone

#### Bus Factor & Authorship

- Show all-time contributor ranking
- Show recent (6-month) contributor ranking side by side
- Calculate what percentage of total commits the top contributor accounts for
- Flag single-contributor risk: if one person accounts for 50%+ of commits, that's a bus factor concern
- Identify knowledge gaps: contributors who were active historically but absent recently — what areas of the codebase did they likely own?
- Note any areas where the original builder is no longer the active maintainer
- Compare original builders against current maintainers — misalignment indicates institutional knowledge loss

#### Bug Clusters

- List the top 20 files appearing in bug-fix commits
- **Cross-reference with churn hotspots**: files appearing on BOTH lists are highest-risk — they keep breaking and keep getting patched but never get properly fixed. These are the strongest candidates for dedicated refactoring
- Identify any domain or feature that concentrates bugs
- Note if bug-fix commits are well-distributed or concentrated among few contributors
- Caveat: this analysis depends on commit message discipline. If messages are inconsistent, results will be incomplete

#### Project Momentum

- Present the monthly commit counts as a text-based trend (use a simple ASCII bar chart if possible)
- Identify the overall trajectory: growing, stable, declining, or erratic
- Flag sharp drops or spikes and hypothesize causes (staff changes, release cycles, holiday periods)
- Note the current velocity relative to the 12-month average
- This is team data, not code data — velocity changes often correlate with organizational changes (departures, reorgs, hiring)

#### Firefighting Patterns

- Count and list all revert/hotfix/emergency commits found
- Calculate the firefighting frequency (e.g., "1 emergency per month" or "3 reverts in the last quarter")
- If frequent: this signals deploy process fragility — unreliable tests, missing staging, or a deploy pipeline that makes rollbacks harder than they should be
- If absent: either the team is stable, or commit messages don't follow conventions. Check a sample of recent commit messages to gauge message discipline before concluding stability

### 3. Cross-reference and synthesize

This is the most valuable part. Combine findings across all five dimensions:

- **Danger zones**: Files that are high-churn AND high-bug AND owned by a single/departed contributor. These are the highest-risk files in the codebase
- **Team health signals**: Is velocity stable? Are contributors well-distributed? Is knowledge being shared or siloed?
- **Process signals**: Are there many reverts? Do bug fixes concentrate in certain time periods? Does the team ship continuously or in batches?
- **Technical debt indicators**: Files that get constant patches but never a proper rewrite. Files that people fear touching

### 4. Generate the report

Write the report under `{skill-base-dir}/reports/` (never alongside `SKILL.md` or other skill files). Use a subfolder named after the current project (derive the project name from the working directory's basename or git remote). Full path: `{skill-base-dir}/reports/{project-name}/YYYY-MM-DD-audit.md`. Create `reports/` and the project subfolder if they don't exist.

Treat files under `reports/` as local output only, not part of the skill source.

```markdown
# Codebase Health Audit

**Date**: [date] | **Branch**: [branch] | **Window**: [since period] | **Total commits in window**: [count]

## Executive Summary

[3-5 bullet points capturing the most important findings. Lead with risks.]

## Risk Matrix

| Risk | Severity | Evidence | Recommendation |
|------|----------|----------|----------------|
| [risk name] | HIGH/MEDIUM/LOW | [data point from the analysis] | [actionable next step] |

---

## 1. Churn Hotspots

| # | File | Changes | Category |
|---|------|---------|----------|
| 1 | `path/to/file` | N | app logic / config / migration / etc |

**Analysis**: [interpretation]

---

## 2. Bus Factor & Authorship

### All-time contributors
| # | Contributor | Commits | % of total |
|---|------------|---------|------------|

### Recent contributors (6 months)
| # | Contributor | Commits | % of recent |
|---|------------|---------|-------------|

### Knowledge gap analysis
[Contributors who dropped off, what they likely owned, who covers it now]

---

## 3. Bug Clusters

| # | File | Bug-fix mentions |
|---|------|-----------------|

### Highest-risk files (churn + bugs)
Files appearing on BOTH the churn and bug-fix lists:

| File | Churn rank | Bug rank | Primary contributor |
|------|-----------|----------|-------------------|

**These files are the top candidates for refactoring or dedicated attention.**

---

## 4. Project Momentum

[ASCII bar chart or trend description of monthly commits]

**Trajectory**: [growing / stable / declining / erratic]
**Current velocity vs 12-month average**: [above / at / below]

[Notable inflection points and hypothesized causes]

---

## 5. Firefighting Patterns

**Total emergency commits**: [N] in [time window]
**Frequency**: [X per month/quarter]

[List of emergency commits if any]

[Analysis of what this signals about deploy process health]

---

## Cross-Reference Analysis

### Danger zones
[Files/areas that score badly across multiple dimensions — the highest-value findings]

### Positive signals
[Areas that show health — stable, well-tested, distributed ownership]

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
- If the bus factor is concerning, call it out prominently
- Ask if they want to drill deeper into any specific area (e.g., read the actual high-churn files, trace a specific contributor's ownership, analyze a specific danger zone file)

