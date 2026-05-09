# Events Vocabulary

This is the canonical list of events the skill recognizes. Provider-specific
events (currently GitHub-only) map *into* these abstract events at the
transport boundary. Playbooks and the reconcile loop only ever see normalized
event names from this registry.

Each event has:
- **Name** — `category.subname` form, lowercase, dot-separated.
- **Trigger** — what causes it.
- **Payload shape** — key fields the playbooks may rely on.
- **GitHub mapping** — which provider event(s) translate to this one.

When adding a new event, add it here first. Playbooks that reference an
event not in this registry should fail validation.

---

## Repository events

### `repo.initialized`
First time the skill runs in a repo (no `.workflow/` folder present).
Triggers bootstrap mode.
- Payload: `{ repo, default_branch, detected_languages, detected_ci, contributors }`
- Provider mapping: synthetic; emitted by the CLI on first run.

### `repo.config_changed`
`.workflow/config.yml` was modified.
- Payload: `{ before, after, diff, actor }`
- Provider mapping: derived from `push` event when `.workflow/config.yml` is in changed files.

### `repo.profiles_changed`
Profile enable/disable changed in config.
- Payload: `{ added, removed, lifecycle_recomposed }`
- Provider mapping: derived from `repo.config_changed`.

### `repo.schema_migrated`
Schema version bumped, migration applied.
- Payload: `{ from_version, to_version, migration_id }`
- Provider mapping: synthetic; emitted by the migrator.

---

## Code events

### `push`
Commits pushed to any branch.
- Payload: `{ branch, commits, before_sha, after_sha, actor }`
- Provider mapping: GitHub `push`.

### `push.protected_branch`
Push to a protected branch (typically `main`).
- Payload: as `push`, plus `branch_is_default: true`.
- Provider mapping: GitHub `push` with branch == default.

### `branch.created`
New branch created.
- Payload: `{ branch, sha, actor }`
- Provider mapping: GitHub `create` with `ref_type: branch`.

### `branch.deleted`
Branch deleted.
- Payload: `{ branch, actor }`
- Provider mapping: GitHub `delete` with `ref_type: branch`.

### `tag.created`
Tag pushed (used as release trigger).
- Payload: `{ tag, sha, actor }`
- Provider mapping: GitHub `create` with `ref_type: tag`.

---

## Pull request events

### `pull_request.opened`
- Payload: `{ pr_number, title, body, author, base, head, files, draft }`
- Provider mapping: GitHub `pull_request` with `action: opened`.

### `pull_request.synchronized`
New commits pushed to PR head.
- Payload: `{ pr_number, before_sha, after_sha }`
- Provider mapping: GitHub `pull_request` with `action: synchronize`.

### `pull_request.ready_for_review`
PR moved out of draft state.
- Payload: `{ pr_number, author }`
- Provider mapping: GitHub `pull_request` with `action: ready_for_review`.

### `pull_request.review_requested`
- Payload: `{ pr_number, requested_reviewer }`
- Provider mapping: GitHub `pull_request` with `action: review_requested`.

### `pull_request.review_submitted`
A review was submitted (any state).
- Payload: `{ pr_number, reviewer, state }` where `state` ∈ approved | changes_requested | commented.
- Provider mapping: GitHub `pull_request_review` with `action: submitted`.

### `pull_request.approved`
- Payload: `{ pr_number, reviewer }`
- Provider mapping: derived from `pull_request.review_submitted` with state == approved.

### `pull_request.changes_requested`
- Payload: `{ pr_number, reviewer, body }`
- Provider mapping: derived from `pull_request.review_submitted` with state == changes_requested.

### `pull_request.closed`
PR closed without merge.
- Payload: `{ pr_number, actor }`
- Provider mapping: GitHub `pull_request` with `action: closed` and `merged: false`.

### `pull_request.merged`
PR merged.
- Payload: `{ pr_number, merge_commit_sha, base }`
- Provider mapping: GitHub `pull_request` with `action: closed` and `merged: true`.

### `pull_request.reopened`
- Payload: `{ pr_number, actor }`
- Provider mapping: GitHub `pull_request` with `action: reopened`.

### `pull_request.labeled` / `pull_request.unlabeled`
Label added/removed on PR.
- Payload: `{ pr_number, label, actor }`
- Provider mapping: GitHub `pull_request` with `action: labeled` / `unlabeled`.

### `pull_request.assigned` / `pull_request.unassigned`
- Payload: `{ pr_number, assignee, actor }`
- Provider mapping: GitHub `pull_request` with `action: assigned` / `unassigned`.

### `pull_request.title_changed` / `pull_request.body_changed`
PR metadata edited (relevant because spec linkage lives in the body).
- Payload: `{ pr_number, before, after, actor }`
- Provider mapping: GitHub `pull_request` with `action: edited` and changes to `title` or `body`.

---

## Issue events

### `issue.opened`
- Payload: `{ issue_number, title, body, author, labels }`
- Provider mapping: GitHub `issues` with `action: opened`.

### `issue.closed`
- Payload: `{ issue_number, actor, state_reason }`
- Provider mapping: GitHub `issues` with `action: closed`.

### `issue.reopened`
- Payload: `{ issue_number, actor }`
- Provider mapping: GitHub `issues` with `action: reopened`.

### `issue.labeled` / `issue.unlabeled`
- Payload: `{ issue_number, label, actor }`
- Provider mapping: GitHub `issues` with `action: labeled` / `unlabeled`.

### `issue.assigned` / `issue.unassigned`
- Payload: `{ issue_number, assignee, actor }`
- Provider mapping: GitHub `issues` with `action: assigned` / `unassigned`.

---

## Comment events

### `comment.created`
Comment on a PR or issue.
- Payload: `{ parent_type: pr|issue, parent_number, body, author, comment_id }`
- Provider mapping: GitHub `issue_comment` with `action: created`.

### `comment.edited`
- Payload: `{ parent_type, parent_number, body, before_body, author, comment_id }`
- Provider mapping: GitHub `issue_comment` with `action: edited`.

### `comment.slash_command`
Derived: a `comment.created` whose body matches `/{command}` syntax.
- Payload: `{ parent_type, parent_number, command, args, author, comment_id }`
- Provider mapping: derived in the transport normalization layer.

---

## Review events

### `review.thread.created`
- Payload: `{ pr_number, thread_id, file, line, body, author }`
- Provider mapping: GitHub `pull_request_review_comment` with `action: created`.

### `review.thread.resolved`
- Payload: `{ pr_number, thread_id, actor }`
- Provider mapping: GitHub GraphQL — not in REST webhooks, polled via API.

### `review.thread.unresolved`
- Payload: `{ pr_number, thread_id, actor }`
- Provider mapping: as `review.thread.resolved`, derived from polling.

---

## Artifact events (skill-derived)

These are not direct provider events. The reconcile loop emits them when it
detects artifact-level changes by hashing files and comparing to sidecars.

### `artifact.created`
A new spec, ADR, impl-plan, or other tracked artifact was added.
- Payload: `{ artifact_type, id, path, hash, author }`

### `artifact.modified`
Content hash differs from sidecar's recorded hash.
- Payload: `{ artifact_type, id, path, before_hash, after_hash, author }`

### `artifact.classified`
Change classification was computed.
- Payload: `{ artifact_type, id, classification }` where classification ∈ editorial | substantive | structural.

### `artifact.state_changed`
Sidecar state field updated (e.g., `draft` → `in-review`).
- Payload: `{ artifact_type, id, before_state, after_state, actor }`

### `artifact.superseded`
- Payload: `{ artifact_type, old_id, new_id }`

### `artifact.linked` / `artifact.unlinked`
Link between artifact and PR/issue created/removed.
- Payload: `{ artifact_type, id, link_type: pr|issue, link_target, actor }`

---

## Lifecycle events (skill-derived)

### `lifecycle.stage_entered`
- Payload: `{ item_type: pr|issue, item_id, stage }`

### `lifecycle.stage_exited`
- Payload: `{ item_type, item_id, stage }`

### `lifecycle.gate_evaluated`
- Payload: `{ item_type, item_id, stage, gate, result, reason }`

### `lifecycle.gate_failed` / `lifecycle.gate_passed`
- Payload: as `lifecycle.gate_evaluated` with explicit pass/fail.

### `lifecycle.cascade_triggered`
- Payload: `{ source_type, source_id, classification, affected: [...] }`

### `lifecycle.in_flight_conflict_detected`
A cascade would have disrupted an in-progress item.
- Payload: `{ source, conflict_with, resolution: notify_only|reverted|labeled }`

---

## Release events

### `release.created`
- Payload: `{ tag, name, body, author }`
- Provider mapping: GitHub `release` with `action: created`.

### `release.published`
- Payload: as `release.created`.
- Provider mapping: GitHub `release` with `action: published`.

### `release.validation_window_opened`
Skill-derived; emitted on `release.published` when observability profile is active.
- Payload: `{ release_tag, window_days, validation_targets }`

### `release.validation_window_closed`
- Payload: `{ release_tag, outcome: validated|expired|rolled_back }`

### `release.validated`
- Payload: `{ release_tag, validator, evidence_summary }`

### `release.rolled_back`
- Payload: `{ release_tag, reason, actor }`

---

## Schedule events

### `schedule.daily`
For stale-spec checks, report rollups, drift reconciliation.
- Payload: `{ scheduled_at }`
- Provider mapping: GitHub Actions `schedule` cron trigger.

### `schedule.weekly`
For archive threshold checks, retention sweeps.
- Payload: `{ scheduled_at }`

### `schedule.on_demand`
Manual reconcile invocation.
- Payload: `{ actor, intent: reconcile|status|report|... }`
- Provider mapping: GitHub `workflow_dispatch` or local CLI invocation.

---

## Adding a new event

1. Add an entry here with name, payload, and provider mapping.
2. Update the transport normalization layer (`scripts/helpers/transport/normalize.py`)
   to translate the provider event into the abstract one.
3. Add or update playbooks that should react to it.
4. Add a fixture in `tests/fixtures/events/` for testing.
