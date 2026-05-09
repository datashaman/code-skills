# Event Dispatch

This file is the routing table from canonical events
(see `references/vocabulary/events.md`) to playbooks that handle them.
Every event the skill recognizes maps to exactly one primary playbook.

Some playbooks handle multiple events (e.g., `spec_change.md` handles
both `push` and `pull_request.synchronized` when the changed files
include artifact paths). The dispatch is by event class plus optional
file-pattern filter.

## Dispatch table

| Canonical event | Primary playbook | Notes |
|---|---|---|
| `repo.initialized` | `bootstrap.md` | First-run; not technically a playbook in `playbooks/` but a top-level reference. |
| `repo.config_changed` | `playbooks/operational.md` | Reconcile lifecycle composition, label taxonomy. |
| `repo.profiles_changed` | `playbooks/operational.md` | Recompose lifecycle, regenerate provider configs. |
| `repo.schema_migrated` | (no playbook; handled by migrator) | |
| `push` (non-default branch) | `playbooks/push.md` (filter by changed files) | If artifact files: also `spec_change.md`. |
| `push.protected_branch` | `playbooks/push.protected_branch.md` | Stricter checks; release detection. |
| `branch.created` | (no-op for v1) | |
| `branch.deleted` | (no-op for v1) | |
| `tag.created` | `playbooks/release.md` | Release flow trigger. |
| `pull_request.opened` | `playbooks/pull_request.opened.md` | |
| `pull_request.synchronized` | `playbooks/pull_request.synchronized.md` | Lighter than opened; uses `spec_change.md` for artifact updates. |
| `pull_request.ready_for_review` | `playbooks/pull_request.ready_for_review.md` | Re-evaluate gates that don't apply to drafts. |
| `pull_request.review_requested` | (idempotent; folded into reviewer assignment in opened/synchronized) | |
| `pull_request.review_submitted` | `playbooks/review.submitted.md` | Update gate `min_approvals_met`. |
| `pull_request.approved` | `playbooks/review.submitted.md` (subset) | |
| `pull_request.changes_requested` | `playbooks/review.submitted.md` (subset) | Apply `blocked:changes-requested`. |
| `pull_request.closed` | `playbooks/pull_request.closed.md` | Move sidecar to archive. |
| `pull_request.merged` | `playbooks/pull_request.merged.md` | Advance to `stage:released` if observability enabled; archive. |
| `pull_request.reopened` | `playbooks/pull_request.opened.md` (variant) | Restore from archive sidecar. |
| `pull_request.labeled` | `playbooks/labels_changed.md` | Sync to sidecar; if external, classify as manual override. |
| `pull_request.unlabeled` | `playbooks/labels_changed.md` | |
| `pull_request.assigned` | (sync to sidecar) | |
| `pull_request.unassigned` | (sync to sidecar) | |
| `pull_request.title_changed` | `playbooks/pull_request.opened.md` (re-classify subset) | Re-run type classification. |
| `pull_request.body_changed` | `playbooks/pull_request.opened.md` (re-link subset) | Re-extract spec links. |
| `issue.opened` | `playbooks/issues.md` | Triage, route, scaffold from template. |
| `issue.closed` | `playbooks/issues.md` | Archive sidecar. |
| `issue.reopened` | `playbooks/issues.md` (variant) | |
| `issue.labeled` | `playbooks/labels_changed.md` | |
| `issue.unlabeled` | `playbooks/labels_changed.md` | |
| `issue.assigned` | (sync to sidecar) | |
| `issue.unassigned` | (sync to sidecar) | |
| `comment.created` | `playbooks/comments.md` | Routes to slash_command if body matches `/{cmd}` pattern. |
| `comment.edited` | `playbooks/comments.md` (re-evaluate) | If a slash command was edited, re-process. |
| `comment.slash_command` | `playbooks/comment.slash_command.md` | |
| `review.thread.created` | (sync to sidecar; gate `no_unresolved_threads`) | |
| `review.thread.resolved` | (sync to sidecar) | |
| `review.thread.unresolved` | (sync to sidecar) | |
| `artifact.created` | `playbooks/spec_change.md` (creation branch) | |
| `artifact.modified` | `playbooks/spec_change.md` | |
| `artifact.classified` | (internal; emitted by classify phase) | Not a top-level dispatch target. |
| `artifact.state_changed` | `playbooks/artifact_state_changed.md` | Cascade state changes. |
| `artifact.superseded` | `playbooks/spec_change.md` (structural branch) | |
| `artifact.linked` | (sync to sidecar) | |
| `artifact.unlinked` | (sync to sidecar) | |
| `lifecycle.stage_entered` | (internal) | |
| `lifecycle.stage_exited` | (internal) | |
| `lifecycle.gate_evaluated` | (internal) | |
| `lifecycle.gate_failed` | (internal; triggers comment update) | |
| `lifecycle.gate_passed` | (internal) | |
| `lifecycle.cascade_triggered` | (internal) | |
| `lifecycle.in_flight_conflict_detected` | `playbooks/in_flight_conflict.md` | Comment + role notification. |
| `release.created` | `playbooks/release.md` | |
| `release.published` | `playbooks/release.md` | |
| `release.validation_window_opened` | (sync to lifecycle; observability profile only) | |
| `release.validation_window_closed` | `playbooks/release.validation.md` | |
| `release.validated` | (sync to lifecycle) | |
| `release.rolled_back` | `playbooks/release.rollback.md` | Notify, log, surface in metrics. |
| `schedule.daily` | `playbooks/schedule.daily.md` | Stale detection, drift checks, archive thresholds. |
| `schedule.weekly` | `playbooks/schedule.weekly.md` | Report rollups, retention sweeps. |
| `schedule.on_demand` | (route by `inputs.operation`) | Manual invocation via `workflow_dispatch`. |

## Dispatcher implementation

The dispatcher is a small helper at `scripts/helpers/dispatch.py`:

```python
def dispatch(event: Event, config: dict) -> Playbook:
    """Map a canonical event to its playbook."""
    table = _load_dispatch_table()
    primary = table[event.name]
    if callable(primary):
        return primary(event, config)   # variants by file pattern
    return primary
```

Variant playbooks (like `spec_change` triggered by `push` when changed
files are artifacts) are expressed as filter functions:

```python
def push_dispatcher(event, config):
    artifact_paths = _all_artifact_paths(config)
    if any(_path_matches(f, artifact_paths) for f in event.payload.files):
        return [load_playbook("push.md"), load_playbook("spec_change.md")]
    return load_playbook("push.md")
```

Multiple playbooks for one event run sequentially in declared order.
Each is its own reconcile pass with its own commit. This is preferred
over compound playbooks because it makes git history clearer.

## Adding a new event

To add a new canonical event and its handler:

1. Add the event to `references/vocabulary/events.md` with name, payload
   shape, GitHub mapping.
2. Add a row to the table above with the primary playbook name.
3. Create the playbook file at `references/playbooks/{event-name}.md`.
4. If the playbook needs new actions, add them to
   `references/vocabulary/actions.md`.
5. Add tests under `tests/integration/test_{event-name}.py`.

The dispatcher's `_load_dispatch_table()` reads this file to populate
the routing.

## Unmapped events

If an event arrives that's not in this table, the dispatcher logs a
warning and no-ops. New GitHub event types occasionally appear; the
skill won't break, but it won't act on them until the table is updated.

The skill's `doctor` command surfaces unmapped events seen in the
metrics log so maintainers know what to add.
