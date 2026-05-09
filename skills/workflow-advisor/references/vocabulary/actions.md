# Actions Vocabulary

Actions are what playbooks dispatch in response to events. They are the
verb half of the skill's API: events tell the skill what happened; actions
are what the skill does in response.

Each action has:
- **Name** — `category.verb` form, lowercase, dot-separated.
- **Inputs** — what the action needs.
- **Side effects** — what changes (folder, provider, both, neither).
- **Idempotency** — whether re-running with the same inputs is a no-op.
- **Owner** — which profile or core component contributes the action.

Most actions are thin wrappers over helpers in `scripts/helpers/`. The
vocabulary is the contract; implementations vary.

---

## Label actions (core)

### `labels.apply`
Add labels to an item; idempotent (skipped if already present).
- Inputs: `item, labels[]`
- Side effects: provider only.

### `labels.remove`
Remove labels; idempotent.
- Inputs: `item, labels[]`
- Side effects: provider only.

### `labels.swap_in_group`
Atomically swap within a mutually exclusive group (e.g., stages, artifact
states). Removes any current label in the group and applies the new one
in a single API operation.
- Inputs: `item, group, new_label`
- Side effects: provider only.

### `labels.sync_taxonomy`
Ensure provider labels match the config taxonomy. Creates missing labels,
updates colors/descriptions on existing matches, leaves unrelated labels alone.
- Inputs: `taxonomy_config`
- Side effects: provider only.

### `labels.bootstrap`
First-time taxonomy creation. Same as `sync_taxonomy` but additionally
prompts about existing-label aliasing.
- Inputs: `taxonomy_config, existing_labels`
- Side effects: provider + folder (writes aliases to config).

---

## Stage actions (core)

### `stage.set`
Move a lifecycle item to a new stage. Uses `labels.swap_in_group` underneath.
- Inputs: `item, new_stage, reason?`
- Side effects: provider (label swap) + folder (`lifecycle/active/{item}.yml` updated).

### `stage.advance`
Move to the next stage in the composed sequence if all gates pass.
- Inputs: `item`
- Side effects: as `stage.set`, only when gates allow.

### `stage.revert`
Move back a stage with reason logged. Used in cascade.
- Inputs: `item, reason, source_event?`
- Side effects: as `stage.set` + decision log entry.

### `stage.skip`
Jump stages with override (logged loudly). Auth: tech_lead or maintainer.
- Inputs: `item, target_stage, reason, actor`
- Side effects: as `stage.set` + prominent decision log entry.

---

## Gate actions (core)

### `gate.evaluate`
Run all gates for an item's current stage. Returns pass/fail per gate with
reasons. Read-only; does not write.
- Inputs: `item, stage`
- Side effects: none (pure).

### `gate.evaluate_one`
Single named gate.
- Inputs: `item, gate_name`
- Side effects: none.

### `gate.override`
Mark a gate as satisfied with reason and approver. Auth-checked per the
gate's override policy in config.
- Inputs: `item, gate_name, reason, actor`
- Side effects: folder (override recorded in `lifecycle/active/{item}.yml`).

---

## Artifact actions (core)

### `artifact.scaffold`
Create from template, write sidecar, optionally add front-matter to markdown.
- Inputs: `artifact_type, id, title, author, template_overrides?`
- Side effects: folder (markdown + sidecar) + git stage.

### `artifact.classify_change`
Run classification pipeline: mechanical signals first, LLM judgment if
ambiguous, log result.
- Inputs: `artifact, before_hash, after_hash, diff`
- Side effects: folder (sidecar's classification field updated, decision logged).

### `artifact.update_state`
Change state, with cascade if applicable.
- Inputs: `artifact, new_state, actor, reason?`
- Side effects: folder (sidecar + front-matter sync) + cascade triggers.

### `artifact.supersede`
Link old artifact to new, archive old.
- Inputs: `old_id, new_id, actor`
- Side effects: folder (both sidecars updated, old marked superseded).

### `artifact.link`
Bidirectional link between artifact and PR/issue.
- Inputs: `artifact, link_type: pr|issue, link_target`
- Side effects: folder (sidecar updated) + provider (comment with link, label).

### `artifact.sync_frontmatter`
Update markdown front-matter from sidecar (or vice versa).
- Inputs: `artifact, direction: from_sidecar|from_frontmatter`
- Side effects: folder.

### `artifact.detect_drift`
Compare hash, flag if changed externally without sidecar update.
- Inputs: `artifact_type, id`
- Side effects: none (pure); returns drift report.

---

## Cascade actions (core)

### `cascade.compute`
Given a change, compute downstream effects. Dry-run.
- Inputs: `source_artifact, classification`
- Side effects: none.

### `cascade.apply`
Execute computed cascade with in-flight protection.
- Inputs: `cascade_plan`
- Side effects: folder + provider (per cascade plan).

### `cascade.preserve_in_flight`
Handle a cascade conflict via label-and-notify instead of revert.
- Inputs: `item, conflict_reason`
- Side effects: provider (labels, comment) + folder (decision log).

---

## Role actions (core)

### `role.resolve`
Given role + context (e.g., changed paths), return concrete members.
- Inputs: `role_name, context?`
- Side effects: none.

### `role.assign_reviewers`
Assign reviewers to a PR per role resolution.
- Inputs: `pr, role_names[]`
- Side effects: provider.

### `role.notify`
Comment/mention role members.
- Inputs: `target, role_names[], message`
- Side effects: provider.

### `role.check_authority`
Verify an actor has authority for an action (used by slash commands).
- Inputs: `actor, command_or_action`
- Side effects: none.

---

## Comment actions (core)

### `comment.post`
Add a comment with the provided body.
- Inputs: `target, body, author_alias?`
- Side effects: provider.

### `comment.update_or_post`
Idempotent: if a skill-authored comment with a matching marker exists,
edit it; otherwise post a new one. Used to avoid spamming PR threads with
repeated status updates.
- Inputs: `target, marker, body`
- Side effects: provider.

### `comment.respond_to_command`
Acknowledge a slash command result with structured output.
- Inputs: `command_event, result`
- Side effects: provider.

---

## PR actions (core)

### `pr.assign_reviewers`
Set reviewer list explicitly.
- Inputs: `pr, reviewers[]`
- Side effects: provider.

### `pr.request_changes`
Leave a review with changes requested.
- Inputs: `pr, body`
- Side effects: provider.

### `pr.dismiss_review`
Used when basis changed (e.g., spec amended substantively).
- Inputs: `pr, reviewer, reason`
- Side effects: provider.

### `pr.set_draft`
Mark as draft. Used when reverting stage.
- Inputs: `pr, reason`
- Side effects: provider.

### `pr.link_artifacts`
Extract spec/ADR/plan links from PR body and commits, write to lifecycle sidecar.
- Inputs: `pr`
- Side effects: folder.

---

## Issue actions (core)

### `issue.triage`
Apply type/area labels based on title, body, file references.
- Inputs: `issue`
- Side effects: provider.

### `issue.route_to_role`
Assign or notify the appropriate role based on triage.
- Inputs: `issue, role_names[]`
- Side effects: provider.

### `issue.scaffold_from_template`
When an issue type requires structured info but was opened freeform, post a
template comment asking the author to fill it in.
- Inputs: `issue, template_name`
- Side effects: provider.

---

## Provider config actions (core)

### `provider_config.propose`
Generate provider config files (e.g., `.github/workflows/*.yml`) and return
as a unified diff.
- Inputs: `config_type, current_state`
- Side effects: none (pure proposal).

### `provider_config.apply`
Write proposed config to disk after confirmation.
- Inputs: `proposal_id`
- Side effects: folder + git stage.

### `provider_config.detect_drift`
Compare what we'd generate now vs what's currently committed.
- Inputs: `config_type`
- Side effects: none.

---

## Reconcile actions (core)

### `reconcile.observe`
Scan repo + provider, build observed state.
- Inputs: `event_context`
- Side effects: none.

### `reconcile.classify`
Categorize observed changes.
- Inputs: `observation`
- Side effects: none.

### `reconcile.apply`
Execute reconcile pass with checkpoint commit.
- Inputs: `event, observation`
- Side effects: folder + provider + git commit (one commit, scoped to `.workflow/`).

### `reconcile.dry_run`
Same as apply, but no writes; returns the would-be diff.
- Inputs: `event`
- Side effects: none.

---

## Decision log actions (core)

### `decision.append`
Add an entry to today's decision file.
- Inputs: `entry: { kind, summary, details, refs }`
- Side effects: folder.

### `decision.link`
Cross-reference between related decisions (e.g., a re-cascade superseding a prior one).
- Inputs: `from_decision_id, to_decision_id, relationship`
- Side effects: folder.

---

## Metrics actions (core)

### `metrics.emit_event`
Append a structured record to `events.jsonl`.
- Inputs: `event_record`
- Side effects: folder.

### `metrics.compute_report`
Generate a rolled-up report from archive + events.
- Inputs: `report_type, time_range, render_as?`
- Side effects: folder (`metrics/reports/...`).

### `metrics.compare_periods`
Before/after comparison.
- Inputs: `report_type, period_a, period_b`
- Side effects: folder.

---

## Test actions (core)

### `test.run_simulator`
Replay an event against current config + folder state. Returns the would-be
outcome.
- Inputs: `event_fixture, config?`
- Side effects: none.

### `test.run_process_tests`
Run `.workflow/tests/*.yml` assertions against current config.
- Inputs: `tests_dir?`
- Side effects: none (returns results).

### `test.coverage_check`
Verify coverage thresholds (testability profile).
- Inputs: `coverage_report`
- Side effects: none.

---

## Documentation actions (documentation profile)

### `docs.identify_required_audiences`
Given a PR's classification, return the set of required audience docs.
- Inputs: `pr, classification`
- Side effects: none.

### `docs.scaffold_audience_doc`
Create a doc for a specific audience from template.
- Inputs: `pr, audience, doc_type`
- Side effects: folder.

### `docs.draft_release_notes`
AI-draft release notes from artifacts and merged PRs.
- Inputs: `release_tag, time_range`
- Side effects: folder (draft saved; requires product approval to finalize).

### `docs.detect_stale`
Find docs whose source artifacts changed since the doc was approved.
- Inputs: `since?`
- Side effects: provider (labels) + folder (decision log).

### `docs.cross_reference_check`
Verify bidirectional links between artifacts and docs.
- Inputs: `artifact_or_doc`
- Side effects: none (returns gaps).

---

## Test plan actions (testability profile)

### `test_plan.scaffold`
Create a test plan artifact for a spec.
- Inputs: `spec_id`
- Side effects: folder.

### `test_plan.verify_levels_present`
Check that required test levels are addressed in the plan.
- Inputs: `test_plan`
- Side effects: none.

### `test_plan.check_evidence`
Verify coverage report, test results attached to the PR.
- Inputs: `pr, test_plan`
- Side effects: none.

---

## Observability actions (observability profile)

### `obs_plan.scaffold`
Create observability plan for a spec.
- Inputs: `spec_id`
- Side effects: folder.

### `obs.detect_instrumentation`
Scan PR diff for log/metric/trace additions matching the plan.
- Inputs: `pr, obs_plan`
- Side effects: none (returns coverage report).

### `obs.verify_alerts_configured`
Check alert configs present in the diff or referenced.
- Inputs: `pr, obs_plan`
- Side effects: none.

### `obs.start_validation_window`
Begin post-release watch on a release.
- Inputs: `release_tag, window_days`
- Side effects: folder.

### `obs.check_baseline_metrics`
Verify metrics captured before merge.
- Inputs: `pr, obs_plan`
- Side effects: none.

### `obs.check_post_release_metrics`
Verify post-release validation criteria met.
- Inputs: `release_tag`
- Side effects: none.

---

## Security actions (security profile)

### `security.threat_model_required`
Check if a PR triggers threat-model requirement (auth, payments, pii, etc.).
- Inputs: `pr, classification`
- Side effects: none.

### `security.scan_required_evidence`
Check SAST, dependency audit, secret-scan results.
- Inputs: `pr`
- Side effects: none.

### `security.classify_findings`
Triage finding severity.
- Inputs: `findings[]`
- Side effects: provider (labels) + folder.

---

## Accessibility actions (accessibility profile)

### `a11y.detect_ui_change`
Flag PRs touching UI files.
- Inputs: `pr`
- Side effects: provider (label).

### `a11y.check_evidence`
Verify scan results, manual test attestations.
- Inputs: `pr, a11y_plan`
- Side effects: none.

---

## Compliance actions (compliance profile)

### `compliance.assess_required`
Determine which frameworks apply to this change.
- Inputs: `pr, classification`
- Side effects: none.

### `compliance.collect_attestations`
Record signed approvals from compliance roles.
- Inputs: `artifact_or_release, attesters`
- Side effects: folder (immutable audit log entry).

### `compliance.write_audit_entry`
Append to immutable audit log.
- Inputs: `entry`
- Side effects: folder.

### `compliance.export_audit_trail`
Generate an auditor-readable export.
- Inputs: `time_range, scope?`
- Side effects: folder.

---

## Adding a new action

1. Add an entry here with inputs, side effects, idempotency, owner.
2. Implement the helper in `scripts/helpers/{owner}/...`.
3. Reference the action by name in playbooks; never hand-roll its logic in a playbook.
4. Add a unit test in `tests/unit/`.
