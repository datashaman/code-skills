# Playbook: issue events

Handles `issue.opened`, `issue.closed`, `issue.reopened`,
`issue.labeled`, `issue.unlabeled`, `issue.assigned`,
`issue.unassigned`. Lighter than PR playbooks — issues track work
intent, not artifact state.

## issue.opened

### Steps

1. **Triage.** Apply `issue.triage` action: classify by title, body,
   referenced files. Apply `type:*` and `area:*` labels.
2. **Route to role.** Based on areas, identify which role(s) should
   look at the issue. Apply `review:{role}` labels.
3. **Template enforcement (optional).** If config requires structured
   issues for certain types and the issue is freeform, post a comment
   with the template asking the author to fill it in.
4. **Link to existing artifacts (if mentioned).** If the issue body
   references a spec/ADR by ID, link bidirectionally in the issue's
   lifecycle sidecar.
5. **Status comment.** Post a brief comment with the triaged
   classification and what role is being asked to look at it.

### Idempotency

If reopened from a closed state, skip triage (preserve existing
classification) and just post a "reopened" notice.

## issue.closed

### Steps

1. **Determine closure reason.** From `state_reason` (completed,
   not_planned, duplicate) and any closing PR reference.
2. **Update lifecycle sidecar.** Mark as terminal state with reason.
3. **Archive.** Move sidecar to `.workflow/lifecycle/archive/issues/`
   per `archive.retention` policy.
4. **Cascade if linked.** If the issue was linked to a spec/ADR, update
   the artifact's `linked_issues` list and check whether downstream
   actions are needed (rare for issue closure).
5. **No comment by default.** Issue closure is usually self-explanatory;
   skip posting unless something unusual is detected (e.g., closed
   without a linked PR for an issue typed as a feature).

## issue.reopened

### Steps

1. **Restore from archive** if the sidecar was archived.
2. **Re-run triage** lightly — re-evaluate type/area labels in case
   they've drifted.
3. **Notify** the role(s) responsible.

## issue.labeled / issue.unlabeled

Most label changes are by humans intentionally. The skill:

1. **Detect intent.** If a label was added that conflicts with a
   mutually-exclusive group already assigned, swap rather than co-exist.
2. **Re-evaluate role routing.** If `area:*` labels changed, update
   `review:*` accordingly.
3. **No comment for routine changes.** Only comment when the change
   triggers cascade.

## issue.assigned / issue.unassigned

Update lifecycle sidecar's assignees field. Don't post comments. Don't
re-run gates (issues don't have gates the same way PRs do).

## Failure modes

Same patterns as other playbooks: fail safe, log, retry on next
reconcile.
