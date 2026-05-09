# Pull Request Ready For Review

Handles `pull_request.ready_for_review`.

## Flow

1. Load the active PR lifecycle sidecar, creating it if needed.
2. Clear draft-only markers.
3. Re-evaluate gates that were skipped or delayed while the PR was draft.
4. Resolve reviewers from roles and CODEOWNERS.
5. Queue provider actions for reviewer requests and status comments.
6. Log gate results and any role fallback warnings.

If the sidecar is missing or stale, run the relevant subset of
`pull_request.opened.md` first.
