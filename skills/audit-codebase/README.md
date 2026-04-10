# audit-codebase

Git-based **codebase health audit**: churn hotspots, bus factor, bug clusters, monthly momentum, and firefighting patterns — then a cross-reference pass to highlight danger zones. No source reads required; everything comes from git history.

## Source

This skill follows the git-first audit approach described in:

**Maciej Piechowski**, *Git commands before reading code* — [https://piechowski.io/post/git-commands-before-reading-code/](https://piechowski.io/post/git-commands-before-reading-code/)

## When to use

Good prompts: *audit the codebase*, *codebase health*, *code archaeology*, *who owns this*, *what files change most*, *bus factor*.

## Arguments


| Argument | Default      | Purpose                           |
| -------- | ------------ | --------------------------------- |
| `path`   | whole repo   | Limit analysis to a subdirectory  |
| `since`  | `1 year ago` | Time window for log-based metrics |


## Files in this folder


| File        | Role                                                                       |
| ----------- | -------------------------------------------------------------------------- |
| `SKILL.md`  | Full agent instructions: git commands, analysis checklist, report template |
| `README.md` | This overview                                                              |
| `reports/`  | Written audit reports (per project / date)                                 |


## Report output

Audits are written as:

`reports/<project-name>/YYYY-MM-DD-audit.md`

`<project-name>` should come from the audited repo’s directory basename (or git remote when that’s clearer). Do not place reports next to `SKILL.md`.

## Requirements

- A git repository with sufficient history for the chosen `since` window
- Bash available to run the diagnostic commands (see `SKILL.md`)

For the full step-by-step workflow, open `**SKILL.md`**.