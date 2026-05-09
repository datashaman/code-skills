# Playbook: pull_request.synchronized

Runs when new commits are pushed to a PR head. Lighter variant of
`pull_request.opened` — most state is preserved; only re-evaluate what
might have changed.

## Inputs

- `event_payload` — `{ pr_number, before_sha, after_sha }`
- `lifecycle_sidecar` — exists (PR was previously seen)

## Steps

### 1. Diff old and new commits

Fetch the diff between `before_sha` and `after_sha` (single API call).

### 2. Cheap re-classification check

Compare:
- New title vs. previous title.
- New file paths vs. previous file paths.
- New body vs. previous body.

If unchanged: skip re-classification.

If changed: re-run classification (fast path — most signals already cached
in the sidecar). If type or areas change, apply label diff.

### 3. Re-evaluate code-dependent gates

Some gates depend on what's in the diff:
- `tests_pass` — re-check after CI re-runs.
- `coverage_threshold_met` — re-check coverage report.
- `instrumentation_present_if_required` (observability) — re-scan diff.
- `sast_clean`, `no_high_findings` (security) — re-check scan output.

For gates that have moved from passing to failing or vice versa, update
labels and recompute stage.

### 4. Detect spec amendments in the diff

If files matching `artifacts.spec.lives_in` are in the diff, dispatch
to the `spec_change` playbook in **speculative mode** (don't cascade
until merge).

Same for ADRs, impl-plans, etc. — speculative cascade plans posted as
a comment so reviewers see the impact.

### 5. Don't re-assign reviewers

Preserve existing reviewer assignments unless:
- A required role's CODEOWNERS pattern now matches a newly-touched path
  (add the new owner).
- A previously-required role no longer applies (don't remove; reviewers
  who were already engaged stay engaged).

### 6. Update status comment

`comment.update_or_post` with the marker. If the comment body is
unchanged, no API call. If changed, edit in place.

### 7. Reconcile commit

Most synchronized events produce no commit (no folder state changed).
When they do (e.g., classification changed, cascade plan updated),
the commit is scoped accordingly.

## Idempotency

Strong by construction. The sidecar's `last_observed_sha` field tracks
the most recent SHA processed; re-running on the same SHA is a no-op.

## Failure modes

Same as `pull_request.opened`. Inherit from that playbook.
