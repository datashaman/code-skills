# Playbook: push

Runs on every `push` event. The catch-all for non-PR commit activity.
Often a no-op for the skill, but sometimes triggers cascades (when
spec/ADR/etc. changes land directly on a branch, or when `.workflow/`
itself is edited).

## Inputs

- `event_payload` — `{ branch, commits, before_sha, after_sha, actor, files_changed }`

## Steps

### 1. Determine push scope

Based on which paths changed:

- **Only code paths** (not in `.workflow/`, not in artifact lives_in
  paths): no-op for the skill. Don't even commit.
- **Artifact paths** (specs, ADRs, plans, audience docs): dispatch to
  `spec_change` (or analogous artifact-change handler).
- **`.workflow/config.yml`**: dispatch to `repo.config_changed` handler
  (re-validate config, recompose lifecycle, run process tests).
- **`.workflow/` (other files)**: treat as manual edit; reconcile to
  detect drift.
- **`.github/workflows/workflow-advisor.yml`**: detect drift; if the
  user manually edited the bootstrap-generated workflow, surface and
  ask before reconciling.

Multiple paths can be in the same push. Run dispatches independently.

### 2. Default branch handling

If `branch == default_branch`:
- Resolve any merge of a PR (look up PR metadata via `gh api` for the
  merge commit's PR number).
- For merged PRs: dispatch to `pull_request.merged` (the explicit event
  may already have fired; this is fallback for environments where it
  didn't).
- For direct pushes to default (uncommon but allowed): treat as
  unreviewed change; depending on config, may post a notice comment on
  any related issues, or flag in metrics as policy violation.

### 3. Bot-self-loop guard

If `actor` matches the bot identity that the skill itself uses for
commits (e.g., `workflow-advisor[bot]`, `github-actions[bot]`):
- Stop. The skill must not respond to its own commits or it'll loop
  indefinitely.
- This is also enforced at the transport level (`if: github.actor !=
  'workflow-advisor[bot]'` in the workflow file), but defense in depth.

### 4. Branch-creation triggers

If this is the first push to a new branch:
- Optionally apply branch-naming convention checks (configurable).
- No state changes by default.

## Idempotency

Strongly idempotent. Re-running on the same SHA is a no-op everywhere.

## Failure modes

| Failure | Behavior |
|---|---|
| Path detection fails | Default to no-op; log warning. |
| Cascade dispatch fails | Continue with remaining; queue failed for retry. |
| Bot-self-loop misdetected | Worst case: one extra reconcile cycle that finds no work. Acceptable. |
