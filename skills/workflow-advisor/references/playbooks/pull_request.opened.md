# Playbook: pull_request.opened

The most-exercised playbook. Runs whenever a PR is opened. Classifies
the PR, resolves required artifacts, evaluates initial gates, applies
labels, assigns reviewers, and posts a status comment.

## Inputs

- `event_payload` — `{ pr_number, title, body, author, base, head, files, draft }`
- `config` — loaded from `.workflow/config.yml`
- `lifecycle_sidecar` (optional) — exists if the PR was previously seen

## Steps

### 1. Bootstrap or load lifecycle sidecar

```
file = `.workflow/lifecycle/active/pr-{number}.yml`
if file exists:
  load it (continuing PR flow)
else:
  create new sidecar with initial state
```

### 2. Classify the PR

Apply `pr.link_artifacts` to extract spec/ADR/plan references from PR body
and commits.

Classify type by:
- Manual `type:*` label if author already applied → use it
- `classification.type_triggers` from config (title keywords, branch
  prefix, file paths, label) → first match wins
- LLM judgment if ambiguous (subject to `ai_usage.classification`)

Classify areas by:
- `classification.area_triggers` — file path patterns matched against
  changed files; multiple matches OK (a PR can be `area:auth` AND
  `area:pii`)

Apply the classified labels via `labels.apply`.

### 3. Identify required artifacts

For each enabled profile, ask the profile what artifacts are required
given the type + areas:

- **spec-driven:** spec required if `type ∈ {feature, breaking, api_change}`.
- **testability:** test plan required if `type ∈ {feature, breaking}`.
- **observability:** obs plan required if `type ∈ {feature, breaking}`.
- **documentation:** audience docs per `docs.identify_required_audiences`.
- **security:** threat model required if `area ∋ security_sensitive`.
- **accessibility:** a11y plan required if `area ∋ ui`.
- **compliance:** compliance assessment required if `area ∋ pii | payments`
  or `type ∈ {regulated, audit_relevant}`.

Build the required-artifacts list. For each that's missing or in wrong
state, mark a gate failure.

### 4. Evaluate initial-stage gates

The PR enters at the earliest stage where the required artifacts are
satisfied:

- If `needs:spec`, enter at `stage:spec`.
- If spec approved but `needs:impl-plan`, enter at appropriate planning
  stage.
- If all planning approved, enter at `stage:implementation`.
- If author marked PR as draft, enter at the determined stage but with
  an `is_draft: true` marker — gates still evaluate, but reviewers aren't
  assigned until ready_for_review.

Apply the stage label via `labels.swap_in_group(stage, ...)`.

### 5. Resolve and assign reviewers

For the determined stage:
- Look up which roles need to review per profile gates.
- For each role, call `role.resolve(role, context={ paths: changed_files })`.
- Assign reviewers via `pr.assign_reviewers`.
- Apply `review:{role}` labels.

If any required role is empty, fall back to `tech_lead` and apply
`needs:role-assignment:{role}` label.

### 6. Apply needs/blocked labels

For each gate that failed:
- Apply the appropriate `needs:*` label.
- If a hard blocker, apply `blocked:*` as well.

### 7. Post status comment

Use `comment.update_or_post` with marker `<!-- workflow-advisor:status -->`
so subsequent updates edit the existing comment rather than spamming.

Comment body:
```
## Workflow status

**Stage:** stage:spec
**Type:** type:feature
**Areas:** area:auth, area:pii

### Required artifacts
- [ ] Spec — needs drafting and architect approval
- [ ] Test plan — required (feature)
- [ ] Obs plan — required (feature)
- [ ] Threat model — required (area:auth)
- [ ] Compliance assessment — required (area:pii)
- [ ] Audience docs: developer, operator, security, support, end_user, legal

### Reviewers assigned
- @marlin (architect)
- @alice (codeowner: src/auth/)

### Next step
Draft a spec linking it in the PR body as `Spec: docs/specs/...`.
Run `/workflow-help` for available commands.
```

### 8. Emit metrics and log decision

`metrics.emit_event` with the classification, stage, gate evaluations.
`decision.append` with the classification rationale (especially if LLM
was consulted).

### 9. Reconcile commit

The whole pass is wrapped in `reconcile.checkpoint`. The commit message
follows the pattern:

```
workflow: pr-{number} opened — type:feature, stage:spec, 5 required artifacts pending
```

## Idempotency

If the PR is already known (sidecar exists with current state), most
steps are no-ops:
- Same classification → no label changes.
- Same stage → no stage swap.
- Same reviewers → no re-assignment.
- Same comment body → `update_or_post` skips the API call.

The reconcile pass produces no commit on a true no-op.

## In-flight protection

This playbook runs only on `pull_request.opened`, so in-flight protection
mostly doesn't apply (the PR is just starting). The exception: if a PR
is reopened after closing (`pull_request.reopened` reuses this playbook),
the prior sidecar may exist with non-trivial state. In that case:
- Restore the PR to its prior stage rather than re-classifying from
  scratch.
- Re-evaluate gates against current code.
- Note the reopen in the decision log.

## Profile-specific overrides

Profiles can hook into this playbook by extending the required-artifacts
step. New profiles should not add new steps to this playbook — they
extend existing steps via the profile API.

## Variant: `pull_request.synchronized`

`pull_request.synchronized` (new commits pushed) reuses most of this
playbook with these changes:
- Don't re-create the sidecar; update it.
- Re-run classification only if files or title changed (cheap check first).
- Don't re-assign reviewers (preserve what's already there).
- Re-evaluate gates that depend on code (test evidence, instrumentation).
- Update the status comment if anything changed.

The variant lives at `playbooks/pull_request.synchronized.md` (similar
structure, lighter).

## Error cases

| Case | Behavior |
|---|---|
| Classification fails (LLM error) | Default to `type:feature` (safer; more gates apply); log decision. |
| Role resolution fails (provider API) | Skip reviewer assignment; flag for retry on next reconcile. |
| Comment post fails | Continue; surfaces in metrics; retry on next event. |
| Sidecar write fails | Atomic via checkpoint; whole pass rolls back. |
