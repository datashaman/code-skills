# Playbook: release

Handles `release.created`, `release.published`, and the derived
`release.validation_window_*` events.

## release.published

The main release event. When a release is published, the observability
profile (if enabled) starts a validation window.

### Steps

1. **Identify release scope.** From the tag and the previous release,
   compute the set of merged PRs in the range. Each PR's lifecycle
   sidecar is potentially affected.

2. **Move PRs to `stage:released`** (observability profile only). For
   each PR with `obs_plan_state: approved`:
   - `stage.set(released, reason="release {tag} published")`.
   - Apply `release:{tag}` label.

3. **Open validation window** (observability profile). Emit synthetic
   `release.validation_window_opened` event:
   - Window length: `observability.post_release.validation_window_days`.
   - Capture baseline metrics if not already captured (the skill calls
     `obs.check_baseline_metrics` to verify).

4. **Compliance attestations** (compliance profile). If frameworks
   require release attestation:
   - Apply `needs:attestation` label to the release.
   - Notify `legal_compliance` role.
   - Block release-validated state until attestation collected.

5. **Release notes** (documentation profile). If `release_notes.mode:
   ai_drafted_human_approved`:
   - Dispatch `docs.draft_release_notes(release_tag, time_range)`.
   - Save draft to `docs/release-notes/{tag}-draft.md`.
   - Apply `doc:end_user:draft` label to the release.
   - Notify `product` role for review.

6. **Decision log entry.** Record the release with the cascade scope.

## release.validation_window_closed

Triggered by `schedule.daily` after `validation_window_days` have
elapsed since `validation_window_opened`.

### Steps

1. **Check validation criteria.** Run `obs.check_post_release_metrics`:
   - Were post-release metrics within expected ranges?
   - Were any alerts triggered?
   - Did anyone run `/post-release-validated`?

2. **If validated:** Move all release-tagged PRs to `stage:validated`.
   Emit `release.validated` event.

3. **If not validated:** Apply `needs:post-release-validation` label
   to the release. Notify `sre`. Don't auto-close the window — keep
   it open until someone explicitly validates or rolls back.

4. **If rolled back during window:** Already handled by
   `release.rolled_back` event; just note in metrics.

## release.rolled_back

Triggered by `/rollback-release` command or external rollback signal.

### Steps

1. **Find affected PRs.** All PRs in the release range.
2. **Move them out of `stage:released`** back to `stage:review`.
3. **Apply `release:rolled-back-{tag}`** label.
4. **Notify roles:** sre, tech_lead, security (if the rollback was for
   a security reason).
5. **Post-mortem artifact (configurable).** If
   `release.post_mortem_required_on_rollback: true`, scaffold a
   post-mortem template artifact and apply `needs:post-mortem`.

---

# Playbook: schedule.daily

Runs once per day via cron. Performs work that doesn't fit a single
event:

## Steps

### 1. Drift detection

Run `artifact.detect_drift` for every tracked artifact. For each drift
detected, dispatch to `spec_change` (or analogous artifact-change
playbook).

### 2. Stale spec/doc detection

If documentation profile is enabled, run `docs.detect_stale`. Apply
`needs:doc-update` to any audience doc whose source artifact has
changed since approval.

For specs themselves: if a spec has been in `in-review` for more than
N days (configurable), apply `stale:in-review` label and notify the
architect.

### 3. Validation window check

For each open release validation window: check if elapsed; if so,
dispatch `release.validation_window_closed`.

### 4. Bootstrap follow-up reminder

If `.workflow/bootstrap_followup.md` has unresolved items, post a
weekly reminder issue or comment (configurable).

### 5. Archive threshold check

If `archive.migration_threshold` is set:
- Compute archive folder size.
- If approaching threshold, prompt the user (open an issue with
  `archive:threshold-warning` label).
- If crossed and `on_threshold: auto-migrate`, perform migration.

### 6. Metrics rollup

Run `metrics.compute_report` for daily/weekly/monthly views. Save to
`.workflow/metrics/reports/`.

### 7. Polling-mode event fetch

If `transport.mode: polling`, run polling logic before the rest of
the daily work. See `references/transports/polling.md`.

## Failure modes

The daily run is forgiving — failures in any step don't block the
others. Each step is independent and idempotent. Crashes log and the
next daily run picks up.

---

# Playbook: schedule.weekly

Runs once per week. Heavier work than daily.

## Steps

### 1. Cycle time and gate friction reports

Compute weekly metrics:
- Median time-in-stage per stage.
- Override rate per gate.
- Slash command usage and rejection rate.
- Empty-role fallback usage.

Save to `.workflow/metrics/reports/weekly/`.

### 2. Before/after comparisons

If `config.yml` was changed in the past week, compute before/after
metrics for affected gates.

### 3. Audit trail completeness check

If compliance profile is enabled:
- Verify every state-changing reconcile commit has a corresponding
  audit trail entry.
- Flag any gaps in the audit log.
- Notify `legal_compliance`.

## Failure modes

Same as daily. Forgiving and idempotent.
