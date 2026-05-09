# Profile: observability

Adds observability plan, runbook, and post-release validation as
first-class. Introduces the `sre` role. Extends the lifecycle past merge
to `released` and `validated`.

## Contributions

**Artifacts.**
- `obs_plan` — observability plan defining signals, SLIs, alert
  thresholds. Required for feature/breaking. Approval from `sre`.
- `runbook` — operational runbook. Required for user_facing /
  on_call_supported services. Approval from `sre`.

**Lifecycle stages.** Adds `obs-plan` stage (parallel with impl-plan by
default). Adds **post-merge** `released` and `validated` stages.

**Roles.** `sre` (default empty; falls back to `tech_lead`).

**Labels.** `stage:obs-plan`, `stage:released`, `stage:validated`,
`obs-plan:*`, `needs:obs-plan`, `needs:instrumentation`,
`needs:runbook`.

**Slash commands.** `/approve-obs-plan`, `/sign-off-instrumentation`,
`/post-release-validated`, `/rollback-release`.

**Gates.**
| Stage transition | Gate |
|---|---|
| spec → impl-plan | `obs_plan_drafted_if_required` |
| impl-plan → review | `obs_plan_approved_if_required` |
| review → merge-ready | `instrumentation_present_if_required`, `alerts_configured_if_required` |
| merge-ready → released | `deployed`, `baseline_metrics_captured` |
| released → validated | `post_release_metrics_reviewed`, `validation_window_elapsed` |

## Required signals

```yaml
observability:
  signals:
    logs:    required
    metrics: required
    traces:  required_for: [feature, performance_sensitive]
    events:  required_for: [user_facing, async_workflow]
    alerts:  required_for: [feature, breaking]
```

Each signal corresponds to a section the obs_plan must address.

## Post-release validation

When `pull_request.merged` fires for a PR with `obs_plan`, the skill emits
`release.published` and starts a validation window:

```yaml
observability:
  post_release:
    validation_window_days: 7
    require_metrics_review: true
    require_runbook_dry_run: optional
```

During the window:
- The PR moves to `stage:released`.
- A `release.validation_window_opened` event is recorded.
- `schedule.daily` checks whether validation criteria are met.
- An SRE runs `/post-release-validated` (or the validation auto-completes
  if criteria are detectable mechanically).
- After the window: if validated, advance to `stage:validated`. If not,
  raise a `needs:post-release-validation` flag and notify SRE.

## Instrumentation detection

`obs.detect_instrumentation` scans the PR diff for additions matching
the obs_plan's declared signals. Heuristics:
- Logs: lines matching language-specific log patterns (e.g.,
  `logger.info`, `console.log`).
- Metrics: imports/calls matching common metrics libraries (Prometheus
  client, StatsD, OpenTelemetry).
- Traces: span/tracer references.

This is best-effort. The `sre` review confirms whether instrumentation
is sufficient. Mechanical detection sets a baseline; sign-off via
`/sign-off-instrumentation` is the formal gate.

## Cascade — post-merge

When an SRE issues `/rollback-release`:
- Emit `release.rolled_back` event.
- Sidecar state for the release moves to `rolled_back`.
- Linked PR moves out of `stage:released`, into `stage:review` (with a
  reason).
- Post-mortem artifact may be required (configurable).

## Process tests starter pack

```yaml
# tests/feature_needs_obs_plan.yml
name: feature PRs need an approved obs plan to enter review
given:
  pr:
    type: feature
    obs_plan_state: null
when: pull_request.opened
then:
  labels_added: [needs:obs-plan]
```

```yaml
# tests/post_release_validation_window.yml
name: merged feature PRs enter released stage with 7-day validation window
given:
  pr:
    type: feature
    state: merged
    obs_plan_state: approved
when: pull_request.merged
then:
  stage: released
  events_emitted: [release.validation_window_opened]
```
