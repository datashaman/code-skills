# code-skills

A collection of Claude Code skills (slash commands) for software engineering workflows.

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
