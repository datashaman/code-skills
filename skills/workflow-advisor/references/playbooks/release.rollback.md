# Release Rollback

Handles `release.rolled_back`.

## Flow

1. Link the rollback to the release, PRs, and artifacts that introduced it.
2. Notify maintainer, SRE, and relevant feature roles.
3. Open or update follow-up lifecycle items.
4. Mark affected validation gates as failed.
5. Surface rollback counts in metrics reports.
