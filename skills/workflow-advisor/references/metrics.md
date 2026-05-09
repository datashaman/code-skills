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
- `role-load`: active item counts by recorded actor and lifecycle stage.
- `documentation`: linked-artifact completeness plus artifact observation and
  change volume.
- `observability`: lifecycle observation volume, sidecar writes, cascade
  failures, and metrics-gate counters.
- `before-after`: comparison around config changes for supported metrics.

## Output Formats

Use `--format json` for machine-readable output. Text and markdown output apply
actor redaction according to `observability_reports.reports.actor_attribution`:

- `roles`: replace handles with `{actor}`.
- `names`: keep handles in the report.
- `hybrid`: keep handles while preserving the same aggregate structure.

Examples:

```bash
workflow-advisor report process
workflow-advisor report role-load
workflow-advisor report observability --format json
workflow-advisor report gate-friction --compare-to 30d --since 7d
```

## Rules

- Prefer role attribution unless the team explicitly chooses names.
- Do not expose raw event payloads in human reports.
- Link report findings back to gates, profiles, or playbooks so the team can
  tune the process instead of treating metrics as judgment.
