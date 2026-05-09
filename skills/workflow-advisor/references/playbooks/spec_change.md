# Playbook: spec_change

Runs when a spec file is modified — either via direct push, PR merge,
or manual edit detected at reconcile. Drives the full cascade flow
because spec changes propagate through impl-plans, test-plans, obs-plans,
audience docs, and any in-flight PRs implementing the spec.

This is the most complex single playbook. It exercises the full power
of the reconcile loop's cascade operation. The same logic applies to
ADRs, impl-plans, test plans, obs plans, and audience docs — the
artifact type is read from the file's location and sidecar, then
profile-specific cascade rules apply.

## When this playbook runs

This is a **derived** playbook — not directly tied to a single GitHub
event. It runs when:

- `push` event includes changes to files in `artifacts.spec.lives_in`.
- `pull_request.merged` includes spec changes.
- `schedule.daily` drift detection finds a spec hash mismatch.
- `artifact.modified` event fires (during reconcile observation).

The transport layer routes these into a synthetic `spec_change` invocation
of this playbook with normalized input.

## Inputs

- `spec_id` — canonical ID
- `spec_file` — path
- `before_hash` — sidecar's recorded hash
- `after_hash` — current file hash
- `actor` — who pushed the change
- `change_context` — `{ commit_sha?, pr_number?, manual_edit?, ... }`

## Steps

### 1. Compute the diff

`diff = spec_file_content_at(after_hash) - spec_file_content_at(before_hash)`

Bound the diff representation: full unified diff if under ~500 lines,
otherwise a structural summary (sections changed, line counts).

### 2. Classify the change

This is the highest-stakes classification in the skill. Misclassifying
a substantive change as editorial allows downstream stages to proceed on
stale information; misclassifying editorial as substantive triggers
unnecessary rework.

`config.ai_usage.spec_amendment_classify: always_llm` — this judgment
always uses LLM (no mechanical-only shortcut), because spec amendments
require contextual judgment (a typo fix in code samples vs. a behavior
change to the same code samples).

Classification pipeline:

a. **Mechanical pre-pass** as input signal, not decision:
   - Sections changed (which headings).
   - Words added/removed.
   - Code blocks modified.
   - Front-matter changed.

b. **LLM call** with diff + spec content + classification rubric. The
   rubric:

```
EDITORIAL = surface-level changes that don't alter behavior, contracts,
  or design. Examples: typos, formatting, clearer wording with same
  meaning, link updates, version bumps in references that don't change
  the contract.

SUBSTANTIVE = changes that alter behavior, contracts, design choices,
  acceptance criteria, scope, or any decision that downstream artifacts
  depend on. Default to substantive when in doubt.

STRUCTURAL = the spec is being replaced wholesale, superseded, or split.
  Triggered when the front-matter `id` or `supersedes` field changes,
  or when the LLM judges the change is a fundamental rewrite.
```

c. **Honor prior `/reclassify` overrides** — if the same change was
   previously reclassified by an authorized actor, use that.

Record the classification in the spec sidecar and the decision log.

### 3. Determine cascade scope

Look up the cascade rule for the classification:

```yaml
cascade:
  spec_substantive_change:
    impl_plan: revert_to_draft
    open_prs: revert_to_arch_review
    related_adrs: flag_for_review
    audience_docs: flag_for_update     # documentation profile
  spec_editorial_change:
    impl_plan: no_change
    open_prs: notify_only
    related_adrs: no_change
    audience_docs: no_change
  spec_supersession:
    impl_plan: archive
    open_prs: link_to_new_spec_and_notify
    related_adrs: append_supersession_note
```

Build the cascade plan:
- Find all `impl_plan` artifacts linked to this spec.
- Find all open PRs with `Spec: {this}` linkage.
- Find all `adr` artifacts cross-referenced.
- Find all audience docs cross-referenced (documentation profile).
- For each, compute the desired action.

### 4. Apply in-flight protection

For each item in the cascade plan:

- **PR is in `stage:review` or later** with non-trivial activity (approvals
  in, threads in progress) → in-flight conflict.
- **Item state is `superseded` or `archived`** → already terminal; skip.
- **Item was modified more recently than the spec** → human-recent-edit;
  prefer label-and-notify over revert.

Default behavior (`cascade.preserve_in_flight: true`):
- Keep the item at its current stage.
- Add `blocked:in-flight-conflict` label.
- Post a comment explaining the spec amendment and what review is needed.
- Notify the spec author and the in-flight item's author.
- Do NOT revert the stage.

Override (`cascade.preserve_in_flight: false`):
- Revert per the cascade rule.
- Comment loudly: "Reverted because spec amended substantively. See
  decision log for context."

### 5. Apply non-conflicting cascades

For items with no in-flight conflict:
- Update sidecars to new state per the cascade rule.
- Apply label changes.
- Post a brief comment on each affected PR/issue noting the cascade and
  what the author needs to do.
- Update lifecycle sidecars.

### 6. Update audience-doc states (documentation profile)

If documentation profile is enabled:
- For each audience doc cross-referenced from this spec:
  - If `editorial` change: no doc state change.
  - If `substantive` change: revert audience doc to `in-review`, apply
    `needs:doc-update`, notify the audience role.
  - If `supersession`: archive the audience doc; new spec will require
    new audience docs.

### 7. Notify roles

For each affected item:
- Resolve the relevant roles (architect, tech_lead, audience roles).
- Use `role.notify` to post structured notification comments with
  context: what changed, which classification, what's required.

### 8. Log decision

The decision log entry for a spec change is fuller than typical:

```markdown
## decision-15: spec/0042 amended substantively

**Spec:** docs/specs/0042-user-auth.md
**Revision:** 6 → 7
**Actor:** marlin
**Classification:** substantive
**Rationale:** LLM judgment — change to acceptance criteria for token
  expiration window. Before: tokens expire after 24h. After: tokens expire
  after 8h with refresh. This is a behavior change downstream PRs depend on.

**Cascade:**
- impl-plan/0042: approved → in-review (revert per cascade rule)
- pr/127: in-flight conflict, retained at stage:review with blocked label
- pr/132: stage:implementation → stage:arch-review (revert)
- adr/0009: flagged for review (depends on token model)
- doc:operator:0042: in-review → needs-update
- doc:end_user:0042: in-review → needs-update

**Notifications:**
- @marlin (architect): notified of cascade and downstream impact
- @alice (tech_lead): notified for impl-plan re-review
- support team (external): notified via comment for doc update

**Reversibility:** This decision can be reverted by `git revert {commit_sha}`.
```

### 9. Reconcile commit

The whole pass produces one git commit:

```
workflow: spec/0042 amended substantively — cascade to 5 affected items
```

The commit message includes the classification, count of cascaded items,
and any in-flight conflicts retained.

## Idempotency

Re-running this playbook on the same change is a no-op:
- Classification matches the sidecar's `last_change_classification`.
- Hash matches the sidecar's `content_hash`.
- All cascade actions are themselves idempotent (state transitions skip
  if already in target state).

## Edge cases

### Spec amended in a PR (not yet merged)
The change appears in the PR's diff but isn't on `main` yet. Behavior:
- Run classification immediately (so reviewers see the impact).
- Build a *speculative* cascade plan; do not apply.
- Post a comment on the PR: "If merged, this spec amendment will cascade
  to: [list]. Reviewers should consider whether this is intended."
- Wait until `pull_request.merged` to actually cascade.

### Spec change in a feature branch's spec
A feature branch authoring a *new* spec — not amending an existing one.
This is `artifact.created`, not `spec_change`. Different playbook.

### Concurrent spec amendments
Two PRs both modify the same spec. On merge of the second, the cascade
re-runs against the merged state. Already-cascaded items may need
re-cascade; reconcile handles this idempotently.

### Spec moved (file rename)
`git mv docs/specs/0042-foo.md docs/specs/0042-foo-bar.md` is detected as
a path change in the sidecar's `file` field. Not a content change; not a
substantive amendment. The sidecar's `file` field updates; no cascade.

### Spec deleted
Treated as supersession with no successor. Heavy:
- All linked impl-plans archive.
- All open PRs get a stop-the-line comment asking what should happen.
- ADRs flag for review.
- Decision log entry is loud.

## Failure modes

| Failure | Behavior |
|---|---|
| LLM classification fails | Default to substantive (safer); log the failure; user can `/reclassify` to correct. |
| Cascade target lookup fails | Process what we can; log the unreachable items; retry on next reconcile. |
| In-flight conflict labels can't be applied | Log; retry next reconcile. The cascade plan is preserved in `.workflow/state/pending_cascades.yml`. |
| Decision log write fails | Continue; metrics record the gap; manual reconciliation may be needed. |

## Profile interactions

- **testability** contributes `test_plan_*_change` rules and adds
  test-plan reverts to spec cascades.
- **observability** contributes `obs_plan_*_change` rules and adds
  obs-plan reverts to spec cascades.
- **documentation** adds audience-doc invalidation: substantive spec
  changes flag all linked audience docs as stale.
- **security** adds threat-model re-review on spec changes touching
  security-classified specs.
- **compliance** adds compliance assessment re-attestation requirement
  on substantive changes to compliance-relevant specs.

See `references/profiles/composition.md` for the composition rules.

## See also

- `references/reconcile.md` — cascade operation in detail.
- `references/profiles/spec-driven.md` — cascade rules per change type.
- `references/playbooks/pull_request.opened.md` — sister playbook for
  initial PR classification.
