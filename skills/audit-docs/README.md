# audit-docs

**Documentation health audit** for projects and rendered docs sites.
Covers five facets in one pass: hygiene, Diataxis classification,
API/docstring coverage, site structure (nav / search / dead links),
and agent-readiness (CLAUDE.md, ADRs, copy-paste-safe examples,
unambiguous terminology).

## When to use

Good prompts: *audit the docs*, *documentation review*, *docs health
check*, *is my documentation agent-friendly*, *what's missing from
my README*, *Diataxis gaps*.

## Inputs

| Input | Default | Purpose                                                        |
|-------|---------|----------------------------------------------------------------|
| path  | `.`     | Local directory to audit (project root or `docs/` subtree)     |
| URL   | —       | Deployed docs site to audit via headless browser               |
| both  | —       | Source-vs-deploy divergence audit                              |

Pass `--check-links` to the scanner to HEAD-check external links
(online; slow; off by default).

## Files in this folder

| File                  | Role                                                              |
|-----------------------|-------------------------------------------------------------------|
| `SKILL.md`            | Full agent instructions: workflow, report sections, scoring       |
| `README.md`           | This overview                                                     |
| `scripts/scan_docs.py`| Static scanner — emits a single JSON object the agent interprets  |
| `reports/`            | Written audit reports (per project / date)                        |

## Report output

Audits are written as:

`reports/<project-name>/YYYY-MM-DD-audit.md`

Where `<project-name>` is the audited directory's basename (or the
URL host for URL-only mode). Reports are local output, not part of
the skill source.

## Requirements

- Python 3.9+ for the scanner
- A live browser (chrome MCP) for URL mode
- `--check-links` requires network access; it issues HEAD requests

## Distinction from sibling skills

- `audit-design` audits **UI / WCAG**, not docs.
- `audit-codebase` audits **git history**, not docs.
- `diataxis` skill **rewrites** docs into Diataxis shape; this
  skill only **scores** them. Hand off if the user wants the
  restructure.
- `grill-with-docs` produces ADRs / CONTEXT.md interactively; this
  skill checks whether they exist and are agent-readable.

For the full step-by-step workflow, open **`SKILL.md`**.
