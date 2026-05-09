# Metrics

Use this reference when generating workflow reports or evaluating whether a
process change helped.

The current implementation reads `.workflow/metrics/events.jsonl` and lifecycle
sidecars. Reports are intentionally aggregated by default; actor attribution is
controlled by `observability_reports.reports.actor_attribution`.

## Report Types

- `process`: active item summary and recent event volume.
- `cycle-times`: time in lifecycle stages from archived sidecars.
- `gate-friction`: override count, stage skips, in-flight conflicts, and
  cascade volume.
- `role-load`: planned report for reviewer and role concentration.
- `documentation`: planned report for audience-doc completeness.
- `observability`: planned report for release validation and instrumentation.
- `before-after`: planned comparison around config changes.

## Rules

- Prefer role attribution unless the team explicitly chooses names.
- Do not expose raw event payloads in human reports.
- Link report findings back to gates, profiles, or playbooks so the team can
  tune the process instead of treating metrics as judgment.
