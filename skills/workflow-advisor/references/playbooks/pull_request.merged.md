# Pull Request Merged

Handles `pull_request.merged`.

## Flow

1. Load the PR lifecycle sidecar and linked artifacts.
2. Mark implementation/review artifacts as accepted where applicable.
3. If observability is enabled, advance to `released`; otherwise archive as
   merged.
4. Open a validation window when configured.
5. Route release tags or release notes changes to `release.md`.
6. Log cycle-time metrics.

Do not retroactively change approval decisions; preserve the historical gate log.
