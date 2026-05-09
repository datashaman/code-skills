# Playbook: simulate

Runs an event against the current config + folder state without writing.
Used for dogfooding config changes and debugging gate logic.

## Inputs

- `event_fixture` — a path to a fixture file or an event payload.
- `config_override` (optional) — alternate config to test against.

## Steps

### 1. Snapshot the world

The current `.workflow/` state is read but not modified. The simulator
runs entirely in memory.

If `config_override` provided, load it instead of `.workflow/config.yml`.

### 2. Run the relevant playbook in dry-run mode

Dispatch to the playbook for the event in the fixture, but with the
reconcile loop set to `dry_run` mode (no writes).

The dry-run mode of `reconcile.checkpoint` returns the *would-be* apply
plan and cascade plan without committing.

### 3. Render the output

Print the would-be state changes:

```
SIMULATION: pull_request.opened on test fixture

Would apply:
  Labels added: [type:feature, area:auth, area:pii, stage:spec, needs:spec, needs:threat-model]
  Labels removed: []
  Reviewers assigned: [@marlin (architect), @alice (codeowner)]
  Comment posted: "## Workflow status — Stage: stage:spec ..." (245 chars)

Would cascade: (none — initial PR open)

Would log:
  decision-N: pr-127 classified as type:feature with 5 required artifacts pending

Gate evaluation:
  ✗ spec_drafted (no spec linked)
  ✗ test_plan_drafted (no test plan)
  ✗ obs_plan_drafted (no obs plan)
  ✗ threat_model_drafted (no threat model — required for area:auth)

No commit (simulation).
```

### 4. Comparison mode (optional)

If invoked with `--compare-config <other-config.yml>`, run twice (once
with each config) and diff the would-be outcomes:

```
SIMULATION DIFF (config A vs config B):

Stage: stage:spec (same)

Labels added (A only): [needs:threat-model]
Labels added (B only): []

Reviewers assigned (A only): []
Reviewers assigned (B only): []

Gates added (B only — security profile disabled in B):
  threat_model_drafted no longer required

This is the impact of disabling the security profile.
```

This is the killer feature for evaluating config changes before
committing them.

## Use cases

- **Pre-commit config check.** A maintainer changes `config.yml` and
  runs `workflow-advisor simulate --event recent --compare-config
  HEAD~1` to see what changes.
- **Regression test.** A process test asserts what the simulator should
  produce for a given event.
- **Debugging.** A user reports unexpected behavior; run the simulator
  with the actual event payload to reproduce.

---

# Playbook: status

Handles `/workflow-status` slash command. Reports the current state of
a PR or issue.

## Steps

### 1. Resolve item

The current PR (when invoked from a PR comment) or issue (when from an
issue). If `/workflow-status #N` was invoked, look up #N.

### 2. Read lifecycle sidecar

Pull the current state from `.workflow/lifecycle/active/{type}-{id}.yml`.

### 3. Run gate evaluation

`gate.evaluate(item, current_stage)` — pure function, no writes. Returns
a list of gate results with reasons.

### 4. Render status

Post a comment with structured status:

```
## Workflow Status

**PR #127:** User auth flow

**Type:** type:feature
**Areas:** area:auth, area:pii
**Stage:** stage:review
**Last updated:** 2 hours ago

### Required artifacts
- ✓ Spec — `docs/specs/0042-user-auth.md` (approved by @marlin)
- ✓ Impl plan — `docs/impl-plans/0042-user-auth.md` (approved by @marlin)
- ✓ Test plan — `docs/test-plans/0042-user-auth.md` (approved by @marlin)
- ✓ Obs plan — `docs/observability/0042-user-auth.md` (approved by tech_lead, sre role empty)
- ✓ Threat model — `docs/security/threat-models/0042.md` (approved)

### Gates
- ✓ tests_pass (last CI: success)
- ✓ coverage_threshold_met (lines: 87%, branches: 76%)
- ✗ no_unresolved_review_threads (2 unresolved threads — #thread-12, #thread-14)
- ✓ codeowners_approved
- ✓ no_open_blockers

### To merge:
1. Resolve the 2 review threads
2. Run `/sign-off` to advance to merge-ready

### Recent decisions
- 2026-05-08: spec/0042 amended editorially by @marlin (no cascade) — see decisions/2026-05-08.md#decision-9
- 2026-05-09: test plan approved by @marlin — see decisions/2026-05-09.md#decision-2
```

The comment uses `comment.update_or_post` with a status marker, so
repeated `/workflow-status` calls update the same comment rather than
spamming.

### 5. No commit

Status is read-only. No reconcile commit.

---

# Playbook: arch_review

Handles `/request-arch-review` slash command. Moves an item to
`stage:arch-review` and notifies the architect.

## Steps

1. **Authorize.** Anyone can request arch review (`auth: any`).
2. **Set stage.** `stage.set(arch-review, reason="requested by {actor}")`.
3. **Apply labels.** `stage:arch-review`, `review:architect`.
4. **Notify architect.** `role.notify(architect, message)`.
5. **Reply.** Confirm via `comment.respond_to_command`.
6. **Log.** Decision entry with the rationale.

Idempotent: if already in `stage:arch-review`, no-op with a friendly
"already there" reply.

---

# Playbook: reconfigure

Handles `repo.config_changed` event (when `.workflow/config.yml` is
edited).

## Steps

### 1. Validate new config

Load and validate against the schema. If invalid:
- Apply `workflow:config-invalid` label to the commit's PR (if any).
- Comment with the validation errors.
- Stop. No state changes.

### 2. Detect what changed

Diff the new config against the prior version. Categorize changes:

- **Profile additions/removals.** Triggers profile-specific bootstrap
  steps (add new artifacts/templates, remove old labels).
- **Role member changes.** No re-evaluation of past gates; new
  assignments take effect for new events.
- **Gate threshold changes.** Re-evaluate gates for all open lifecycle
  items; some may now pass that were failing (or vice versa).
- **Cascade rule changes.** No retroactive cascade; takes effect for
  future spec changes.
- **Transport change.** Triggers transport-specific generation (e.g.,
  removing the old workflow file, adding a new one).

### 3. Recompose lifecycle

Re-run the composition algorithm. Save to
`.workflow/lifecycle/composed.yml`.

### 4. Run process tests

Execute `.workflow/tests/*.yml`. Any failures become an artifact label
on the commit's PR (`workflow:tests-failing`).

### 5. Reconcile open items

For each open lifecycle item, run a focused reconcile pass against the
new config. Stage moves and label changes happen idempotently.

### 6. Decision log

Record the config change with a summary of what changed and what
reconciled.

---

# Playbook: metrics

Handles `/workflow-report` slash command and the daily metrics rollup.

## Steps

### 1. Determine report type

- `/workflow-report` with no args → most recent rollup.
- `/workflow-report cycle-time --range 30d` → cycle time over 30 days.
- `/workflow-report gate-friction` → override rate, gate failure rate.
- `/workflow-report compare-config <commit-a> <commit-b>` → before/after.

### 2. Compute the report

`metrics.compute_report(report_type, time_range, render_as)`. Reads
events.jsonl + decisions/ + lifecycle/archive/.

### 3. Apply redaction policy

If `observability_reports.actor_attribution: roles`:
- Replace specific names with role names ("architect approved spec-0042").
- Strip GitHub handles.

If `actor_attribution: hybrid`:
- Show "architect (marlin)".

If `actor_attribution: names`:
- Show names directly.

### 4. Render

Output as markdown for in-comment display, or as a static file in
`.workflow/metrics/reports/{date}-{type}.md` for committing.

### 5. Reply

`comment.post` with a summary + link to the full report file.
