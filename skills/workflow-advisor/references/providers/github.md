# Provider: GitHub

The provider abstraction layer. Maps GitHub-specific concepts (events,
API endpoints, auth, identity) to the skill's abstract vocabulary.

For v1, GitHub is the only supported provider. The abstraction exists
so other providers (GitLab, Bitbucket) can be added later without
touching playbooks.

## Event mapping

GitHub event → skill event. Implemented in
`scripts/helpers/transport/normalize.py`.

| GitHub webhook event | GitHub `action` | Skill event |
|---|---|---|
| `pull_request` | `opened` | `pull_request.opened` |
| `pull_request` | `synchronize` | `pull_request.synchronized` |
| `pull_request` | `ready_for_review` | `pull_request.ready_for_review` |
| `pull_request` | `closed` (merged: false) | `pull_request.closed` |
| `pull_request` | `closed` (merged: true) | `pull_request.merged` |
| `pull_request` | `reopened` | `pull_request.reopened` |
| `pull_request` | `labeled` | `pull_request.labeled` |
| `pull_request` | `unlabeled` | `pull_request.unlabeled` |
| `pull_request` | `assigned` | `pull_request.assigned` |
| `pull_request` | `unassigned` | `pull_request.unassigned` |
| `pull_request` | `edited` | `pull_request.title_changed` or `pull_request.body_changed` (computed from `changes` field) |
| `pull_request` | `review_requested` | `pull_request.review_requested` |
| `pull_request_review` | `submitted` | `pull_request.review_submitted` (further classified to `.approved` / `.changes_requested`) |
| `pull_request_review_comment` | `created` | `review.thread.created` |
| `issues` | `opened`, etc. | `issue.opened`, etc. |
| `issue_comment` | `created` | `comment.created` (further classified to `comment.slash_command` if body matches `/command`) |
| `issue_comment` | `edited` | `comment.edited` |
| `push` | (no action) | `push` (with `protected_branch` flag if branch == default) |
| `create` (ref_type: branch) | — | `branch.created` |
| `create` (ref_type: tag) | — | `tag.created` |
| `delete` (ref_type: branch) | — | `branch.deleted` |
| `release` | `created` | `release.created` |
| `release` | `published` | `release.published` |
| `schedule` (cron) | — | `schedule.daily` or `schedule.weekly` (based on cron) |
| `workflow_dispatch` | — | `schedule.on_demand` |

Some events are *derived* — not present in GitHub but computed by the
normalization layer:

- `comment.slash_command` from `comment.created` with body matching
  `/command` regex.
- `pull_request.approved` from `pull_request.review_submitted` with state
  == approved.
- `pull_request.title_changed` / `body_changed` from `edited` action's
  `changes` field.

## API call patterns

The skill prefers `gh api` for GitHub API calls because:
- It handles auth automatically (`gh auth` in interactive contexts;
  `GITHUB_TOKEN` in Actions).
- It handles pagination.
- Output is JSON-friendly.
- It's pre-installed on Actions runners.

When `gh` isn't available (rare), fall back to direct HTTP with
`requests`.

Common patterns:

```bash
# Read PR
gh api repos/{owner}/{repo}/pulls/{number}

# List PRs since a cursor
gh api "repos/{owner}/{repo}/pulls?state=all&sort=updated&since=2026-05-09T00:00:00Z"

# Apply labels (idempotent — checks current first)
gh api repos/{owner}/{repo}/issues/{number}/labels --input - <<< '{"labels":["type:feature"]}'

# Post a comment
gh api repos/{owner}/{repo}/issues/{number}/comments -f body="..."

# Update a comment
gh api repos/{owner}/{repo}/issues/comments/{comment_id} -X PATCH -f body="..."

# Create a label
gh api repos/{owner}/{repo}/labels -f name=type:feature -f color=0e8a16 -f description="..."

# Resolve review threads (GraphQL only)
gh api graphql -f query='...'
```

## Auth modes

| Context | Auth |
|---|---|
| GitHub Actions | `GITHUB_TOKEN` (provided automatically) |
| Local development | User's `gh auth login` |
| Self-hosted webhook | PAT in `GITHUB_TOKEN` env, OR App installation token |
| Polling (Actions) | `GITHUB_TOKEN` |
| Polling (external cron) | PAT or App installation token |
| GitHub App (v2) | Installation token via App credentials |

Different auth modes have different rate limits and identity. The skill
uses whichever is provided.

## Identity for commits

When the skill commits to `.workflow/`:

| Auth mode | Commit author |
|---|---|
| `GITHUB_TOKEN` (Actions) | `github-actions[bot] <github-actions[bot]@users.noreply.github.com>` |
| User PAT | The PAT's user |
| Bot PAT | The bot account |
| App installation | `your-app-name[bot] <your-app-name[bot]@users.noreply.github.com>` |

Always prefer bot identity over real user identity. Configure via:

```yaml
# .workflow/config.yml
transport:
  github_actions:
    bot_identity:
      name: workflow-advisor[bot]
      email: workflow-advisor[bot]@users.noreply.github.com
```

## Self-loop guard

Critical for any reactive transport: the skill must not respond to its
own commits, or it'll loop indefinitely.

Defenses (in order):
1. **Commit-message guard.** Skill commits start with `workflow:`;
   playbooks check the prefix and skip.
2. **Author-identity guard.** Skip if `github.actor` matches the bot
   identity.
3. **Path scope guard.** A push that touches only `.workflow/` and
   matches the bot author is skipped entirely.

All three must hold for an event to be processed. Defense in depth.

## Branch protection

Branch protection rules are managed by GitHub, not the skill. The skill:
- **Does not** set or modify branch protection automatically (one-way
  door).
- **Does** suggest rules via comment in bootstrap stage 4.
- **Does** detect when rules conflict with skill gates and surface the
  mismatch (e.g., the skill requires `tests_pass` but no required
  status check is configured for tests).

## CODEOWNERS

The skill reads `.github/CODEOWNERS` to:
- Inform `reviewer` role resolution (intersect with paths).
- Validate `codeowners_approved` gate.

It does not write to CODEOWNERS — that's a team decision the skill
respects.

## Limitations

- **No GraphQL polling for review thread resolution in webhooks.**
  GitHub doesn't fire webhook events for thread resolve/unresolve.
  The skill polls via GraphQL on `schedule.daily`.
- **`pull_request.synchronize`** can fire frequently on rebase-heavy
  workflows. The cheap re-classification check (in the synchronized
  playbook) avoids most expensive work.
- **Rate limits** — visible in API response headers; the skill backs
  off when approaching limits.
