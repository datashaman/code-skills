# Pull Request Closed

Handles `pull_request.closed` when the PR was not merged.

## Flow

1. Load the PR lifecycle sidecar.
2. Mark the stage as `closed`.
3. Archive the sidecar with close metadata.
4. Do not cascade artifact state unless the close event explicitly supersedes or
   abandons a linked artifact.
5. Log metrics for cycle-time and abandoned-work reporting.
