# Review Submitted

Handles `pull_request.review_submitted`, `pull_request.approved`, and
`pull_request.changes_requested`.

## Flow

1. Update the PR lifecycle sidecar with the reviewer, state, and timestamp.
2. Recompute `min_approvals_met`.
3. If changes were requested, add `blocked:changes-requested`.
4. If an approval replaces a prior change request from the same reviewer, remove
   the stale blocker if no other request remains.
5. Re-evaluate merge-ready gates.
6. Queue a concise status comment only when gate state changed.

Provider mutations are queued through provider actions.
