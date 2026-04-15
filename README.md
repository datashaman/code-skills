# code-skills

A collection of skills for software engineering workflows.

## Installation

Install any skill from this repo using [skills](https://skills.sh):

```
npx skills add https://github.com/datashaman/code-skills --skill <skillname>
```

For example:

```
npx skills add https://github.com/datashaman/code-skills --skill audit-codebase
```

## Skills

### `/audit-codebase`

Git-based codebase health audit. Runs five diagnostic git commands to identify churn hotspots, bus factor risks, bug clusters, project momentum, and firefighting patterns — then cross-references findings to surface danger zones.

**Arguments:**
- `path` (optional): Subdirectory to scope the analysis to (default: entire repo)
- `since` (optional): Time window for analysis (default: "1 year ago")

**Usage:**
```
/audit-codebase
/audit-codebase path=src/api since="6 months ago"
```

### `/audit-design`

Static design + WCAG accessibility audit for web UIs. Accepts a URL, a local directory of HTML/CSS/JSX/TSX/Vue/Svelte, or both (plan vs implementation). Every accessibility finding is mapped to a WCAG 2.1 success criterion and rolled up into a pass/fail matrix. Covers contrast ratios, color-only state signaling, semantic HTML structure (headings, landmarks, form labels, alt text, lang), microstandards (OpenGraph, JSON-LD, microdata, RDFa), Tailwind clusters that should be extracted via `@apply`, unhealthy component usage (divitis, clickable divs, inline styles, oversize JSX/TSX, repeated DOM structures), design hygiene (palette, typography, spacing scale, border-radius distribution), AI-slop patterns (purple-violet gradients, 3-col feature grids, icons in colored circles, centered everything, emoji in headings, placeholder copy), technical hygiene (outline:none, transition:all, viewport zoom-block, missing `<img>` dimensions, missing font-display), and a W3C HTML+CSS validator summary. Built for developers who can't eyeball visual problems (colorblindness, limited design experience).

**Arguments:**
- `url` (optional): Deployed URL to audit
- `path` (optional): Local directory of source
- At least one of `url` or `path` is required; pass both for plan-vs-implementation divergence mode

**Usage:**
```
/audit-design url=https://example.com
/audit-design path=./src
/audit-design url=https://example.com path=./src
```

### `/audit-context`

Audit your Claude Code setup for token waste and context bloat. Starts from `/context` output, then audits MCP servers (user-configured and built-in `claude.ai *`), CLAUDE.md rules and `@imports`, skills, agents, slash commands, plugins, hooks, all five settings scopes (including managed / enterprise policy), and file permissions. Flags user-configured MCP servers that have well-known CLI equivalents (github→gh, aws→aws, kubernetes→kubectl, etc.) since a CLI costs zero tokens when idle. Mines session JSONL transcripts for behavioral signals (cache hit rate, autocompact frequency, turn-cost percentiles, per-tool error rates, unused skills/agents, repeated Read paths, large tool-result outliers). Cross-references MCP connection logs to catch broken servers that load schemas but never connect. Returns a health score with specific fixes.

**Usage:**
```
/audit-context
```

### `/audit-jira`

Jira project health audit. Queries five dimensions of work item data to identify velocity trends, backlog rot, bug clusters, assignee concentration risk, and firefighting patterns — then cross-references findings to surface danger zones.

**Prerequisites:** `acli` installed and authenticated (`acli jira auth`).

**Arguments:**
- `project` (required): Jira project key (e.g. `ENG`, `PLAT`) — can be passed positionally
- `since` (optional): Start date for completed-work analysis (default: `2025-01-01`)
- `sprint` (optional): Sprint name or ID to scope velocity analysis (default: last 6 sprints)

**Usage:**
```
/audit-jira ENG
/audit-jira ENG since=2024-07-01
```

### `/audit-trello`

Trello board health audit. Queries five dimensions of card data to identify throughput trends, backlog rot, blocker clusters, member concentration risk, and overdue patterns — then cross-references findings to surface danger zones.

**Prerequisites:** `trello` CLI installed and authenticated (`trello auth`). Install from https://github.com/mheap/trello-cli.

**Arguments:**
- `board` (required): Trello board name or ID — can be passed positionally
- `done` (optional): Name of the Done list (default: auto-detected)
- `since` (optional): Cutoff date for age-based analysis (default: 1 year ago)

**Usage:**
```
/audit-trello "My Board"
/audit-trello board="My Board" since=2024-07-01
```

## Other skills I like

### [`agent-ready-codebase`](https://skills.sh/casper-studios/casper-marketplace/agent-ready-codebase)

Evaluates a codebase against five principles that determine AI agent effectiveness, then delivers specific improvement guidance tailored to the project's stack.

The five principles: 100% test coverage, thoughtful file structure, end-to-end types, fast/ephemeral/concurrent dev environments, and automated enforcement.

**Modes:**
- `audit`: Score an existing codebase across all five principles
- `guide`: Targeted improvement steps for a specific principle or new project setup

---

## Structure

```
skills/
  <skill-name>/
    SKILL.md        # Skill definition and instructions
```

## Adding a skill

Create a new directory under `skills/` with a `SKILL.md` file. The frontmatter should include `name` and `description` fields. See existing skills for examples.
