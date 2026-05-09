# Transport: polling

Periodic GitHub API polls instead of webhooks. Works in environments
where inbound webhooks aren't viable (firewalled enterprises, GitHub
Enterprise behind VPN, no public-facing endpoint).

## When to use

- Behind-firewall environments.
- GitHub Enterprise with restricted inbound.
- Low-event-rate repos where polling latency is acceptable.
- Teams that don't want webhook complexity.

## When *not* to use

- High-event-rate repos where polling rate-limits you.
- Workflows requiring near-realtime response (slash commands feel laggy
  with poll intervals > 5 minutes).

## How it works

The skill runs on a schedule (every N minutes) and:
1. Reads `.workflow/state/poll_cursor.yml` for the last-processed time
   per resource type.
2. Calls `gh api` for each resource type with `since={cursor}`:
   - Issues
   - PRs
   - Comments
   - Pushes (commits to default branch since cursor)
3. For each new event observed, dispatches the appropriate playbook.
4. Updates the cursor on success.

## What bootstrap stage 3 generates

For polling transport, a workflow file with cron trigger only (no event
triggers):

```yaml
name: workflow-advisor (polling)

on:
  schedule:
    - cron: "*/15 * * * *"   # every 15 minutes
  workflow_dispatch: {}

permissions:
  contents: write
  pull-requests: write
  issues: write

jobs:
  poll:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install workflow-advisor
      - run: workflow-advisor poll
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

Alternatively, the polling can run on the team's infrastructure (a
cron job, a systemd timer, a Cloudflare Cron Trigger).

## The poll cursor

`.workflow/state/poll_cursor.yml`:

```yaml
issues:        2026-05-09T08:23:00Z
pull_requests: 2026-05-09T08:23:00Z
comments:      2026-05-09T08:23:00Z
pushes:        2026-05-09T08:23:00Z
```

Updated on each successful poll. Initialized at bootstrap to "now"
(skip historical backfill by default; the user can override).

## Polling intervals

Configurable per resource:

```yaml
transport:
  polling:
    interval_minutes: 15            # default
    per_resource:
      pull_requests: 5              # poll PRs more often
      issues: 30                    # poll issues less
      comments: 5                   # for slash command latency
```

Lower intervals → better latency, more rate-limit consumption.
Higher intervals → less rate-limit, worse latency.

## Rate limit handling

GitHub allows 5000 requests/hour for authenticated calls. A single
poll uses 1-N calls per resource type depending on activity. Daily
budget of (5000 × 24) = 120,000 calls is plenty for typical repos.

The poller uses the rate-limit-aware client (`gh api` handles this) and
backs off if approaching limits.

## Limitations

- **Latency = poll interval / 2 on average.** A 15-minute interval
  means slash commands take ~7.5 min on average to dispatch.
- **No real-time feedback.** Users may double-comment thinking the
  first didn't take effect.
- **Missed events possible** if the cursor advances past an event due
  to clock skew or pagination edge cases — defensively re-poll a small
  overlap (1 minute) and dedupe via event IDs.

## Failure modes

| Failure | Behavior |
|---|---|
| Single poll fails | Don't advance cursor; retry on next interval. |
| Rate limit hit | Back off; reduce polling frequency temporarily. |
| Cursor file corrupted | Reset to "now" (lose any unprocessed; surface in metrics). |
| Long outage | On recovery, the cursor catches up; many events processed in one batch. Reconcile handles this idempotently. |

## See also

- `references/transports/github_actions.md` — for the default (webhooks
  built in).
- `references/transports/on_demand_only.md` — for fully advisory mode.
