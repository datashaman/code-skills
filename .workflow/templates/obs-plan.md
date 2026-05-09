---
# Observability plan template (observability profile).
#
# Approved by sre. Approval gates entry to `stage:implementation`.
#
id:
title:
state: draft                           # draft | in-review | approved
spec_id:

# Signals the plan covers (the skill verifies presence per
# `obs.detect_instrumentation`):
signals:
  logs: planned
  metrics: planned
  traces: planned                      # required for performance_sensitive
  events: planned                      # required for user_facing
  alerts: planned                      # required for feature/breaking

# Skill-managed:
revision: 1
content_hash: null
last_observed: null
---

# Observability plan: {{ title }}

> Spec: [{{ spec_id }}](../specs/{{ spec_id }}.md)

## What we need to know in production

What signals tell us this feature is healthy? Working? Failing in
unexpected ways? Drive the rest of the plan from this list.

## Logs

What gets logged, at what level, with what context fields? Include the
log key naming so search/queries are predictable.

| Event | Level | Fields | Notes |
|---|---|---|---|
| ... | INFO / WARN / ERROR | ... | ... |

## Metrics

What's measured? Use names that fit the team's existing naming
convention.

| Metric | Type | Labels | Purpose |
|---|---|---|---|
| `...` | counter / gauge / histogram | ... | ... |

## Traces

(if performance_sensitive) Which spans are added? What attributes?

## Events

(if user_facing or async_workflow) What domain events are emitted? To
where? With what schema?

## Alerts

What conditions page someone? What conditions just notify? Reference
each alert's owner and the runbook it points to.

| Alert | Condition | Severity | Runbook | Owner |
|---|---|---|---|---|
| ... | ... | page / warn / info | ... | sre |

## Baseline metrics

What metrics should be captured *before* this ships? Used by the
post-release validation window to compare.

- ...

## Validation criteria

What does "validated" mean for this release?

- ...

## Approvals

- [ ] sre
