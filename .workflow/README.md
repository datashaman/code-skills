# Workflow Advisor

This folder is the source of truth for this repo's workflow-advisor process.

The current setup is intentionally local and on-demand:

- Transport is `on_demand_only`; no GitHub Actions workflow has been installed.
- Process state and sidecars live under `.workflow/`.
- Human workflow artifacts live under `docs/` using the paths in `config.yml`.
- Copilot is recorded as the review assistant; human reviewer role is unassigned.

## Enabled Profiles

- spec-driven
- testability
- observability
- documentation
- security

Accessibility and compliance are disabled for now.

## Spec Linkage

PRs should reference specs with a body line:

```text
Spec: docs/specs/0042-example.md
```

## Local Use

Use the workflow advisor from an agent session to inspect status, dry-run process
changes, or reconcile state after artifact edits. Because this repo is
on-demand only, nothing in this folder runs automatically in CI yet.
