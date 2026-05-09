# Transport: GitHub Actions

The default and recommended transport for v1. Events arrive as Actions
workflow triggers; the skill runs in a fresh Ubuntu runner per event,
reads the event payload from `$GITHUB_EVENT_PATH`, executes the
reconcile loop, and commits any `.workflow/` changes back to the repo
under a bot identity.

## When to use this transport

- Most teams. Zero external infrastructure, zero ops.
- Auth is solved by `GITHUB_TOKEN` (provided automatically per run).
- `gh` CLI is pre-installed on Actions runners.
- Concurrency control is built-in.

## When *not* to use it

- High-event-volume repos where Actions minute consumption matters —
  consider `self_hosted_webhook` instead.
- Sub-second-latency requirements — Actions cold start is ~30s.
- Behind-firewall enterprise where outbound API calls are restricted —
  consider `polling` or `on_demand_only`.

## What bootstrap stage 3 generates

A single workflow file at `.github/workflows/workflow-advisor.yml`. The
skill's bootstrap proposes this; the user reviews and approves before
it's committed.

```yaml
name: workflow-advisor

on:
  pull_request:
    types: [opened, synchronize, ready_for_review, closed, reopened,
            labeled, unlabeled, assigned, unassigned, review_requested,
            review_request_removed]
  pull_request_review:
    types: [submitted, edited, dismissed]
  pull_request_review_comment:
    types: [created, edited]
  issues:
    types: [opened, closed, reopened, labeled, unlabeled, assigned, unassigned]
  issue_comment:
    types: [created, edited]
  push:
    branches: [main]
  schedule:
    - cron: "0 2 * * *"          # daily reconcile at 02:00 UTC
  workflow_dispatch:              # manual invocation
    inputs:
      operation:
        description: "Operation to run"
        required: true
        default: reconcile
        type: choice
        options:
          - reconcile
          - report
          - simulate

concurrency:
  group: workflow-advisor-${{ github.repository }}
  cancel-in-progress: false       # critical — preserve in-flight work

permissions:
  contents: write                 # commit to .workflow/
  pull-requests: write            # labels, comments, assignees
  issues: write                   # labels, comments, assignees
  actions: read                   # observability over own runs

jobs:
  reconcile:
    # Skip pushes by the bot itself to prevent self-loop
    if: github.actor != 'workflow-advisor[bot]' && github.actor != 'github-actions[bot]'
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0          # full history for git checkpointing
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install workflow-advisor
        run: |
          pip install --quiet workflow-advisor
          # During bootstrap or development, the skill may be vendored
          # into .workflow/scripts/ instead. The CLI checks both.

      - name: Run reconcile
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          EVENT_NAME: ${{ github.event_name }}
          EVENT_ACTION: ${{ github.event.action || 'none' }}
        run: |
          workflow-advisor reconcile \
            --event-name "$EVENT_NAME" \
            --event-action "$EVENT_ACTION" \
            --event-payload "$GITHUB_EVENT_PATH" \
            --transport github_actions

      - name: Commit .workflow/ changes
        run: |
          if [[ -n "$(git status --porcelain .workflow/)" ]]; then
            git config user.name "workflow-advisor[bot]"
            git config user.email "workflow-advisor@users.noreply.github.com"
            git add .workflow/
            git commit -F .workflow/state/last_commit_message
            git push
          fi
```

## Pre-requirements

Before this workflow can run, the repo needs:

1. **`ANTHROPIC_API_KEY` repository secret.** Settings → Secrets and
   variables → Actions → New repository secret.
   - The skill's bootstrap stage 3 surfaces this as required and waits
     for confirmation that it's been added.
   - Org-level secret also works; check `Settings → Secrets → Actions`
     at the org for shared keys.

2. **Bot identity.** No setup needed — `workflow-advisor[bot]` is the
   conventional name committed by `actions/checkout@v4` with the
   provided `GITHUB_TOKEN`. The bot's commits are attributed to the
   action, with the triggering human actor recorded in the decision log.

3. **Workflow permissions allowed.** Some org settings restrict workflow
   permissions. Confirm at `Settings → Actions → General → Workflow
   permissions` that read/write is allowed, or that `permissions:`
   declarations in workflow files are honored.

## Self-loop prevention

The workflow filters out runs triggered by the bot itself via the `if:`
condition on the job. Without this, every `.workflow/` commit would
trigger another `push` event and another run.

A secondary safeguard: bot commit messages can include `[skip ci]` to
stop downstream workflows entirely (other repo workflows that trigger on
push). The skill does **not** add `[skip ci]` to its commits by default
because most other workflows should still run on `.workflow/` changes
(e.g., a status-check workflow may verify the workflow folder is valid).

## Event payload normalization

GitHub event payloads vary in shape per event type. The skill's
`scripts/helpers/transport/normalize.py` translates each GitHub event
into one of the canonical events from `references/vocabulary/events.md`:

| GitHub event | Action | Canonical event |
|---|---|---|
| `pull_request` | `opened` | `pull_request.opened` |
| `pull_request` | `synchronize` | `pull_request.synchronized` |
| `pull_request` | `closed` w/ `merged: true` | `pull_request.merged` |
| `pull_request` | `closed` w/ `merged: false` | `pull_request.closed` |
| `pull_request_review` | `submitted` | `review.submitted` |
| `issue_comment` | `created` w/ body matching `/cmd` | `comment.slash_command` |
| `issue_comment` | `created` (otherwise) | `comment.created` |
| `push` (to default branch) | n/a | `push.protected_branch` |
| `push` (other branches) | n/a | `push` |
| `schedule` | n/a | `schedule.daily` (or `weekly`, parsed from cron) |
| `workflow_dispatch` | n/a | `schedule.on_demand` |

Playbooks consume the canonical events. Provider-specific quirks are
contained at the normalize boundary.

## Concurrency semantics

The `concurrency:` block ensures only one workflow-advisor run is
active per repo at a time. New events queue rather than starting in
parallel.

Critically, `cancel-in-progress: false` means a new event does **not**
cancel a currently-running reconcile. This is the foundation's
"preserve in-flight" rule expressed at the transport layer. Cancelling
an in-flight reconcile would risk leaving `.workflow/` in an
inconsistent state (apply phase complete, cascade phase aborted).

## Idempotency at the transport layer

Each workflow run records its `X-GitHub-Delivery` equivalent (here, the
`github.run_id`) into `.workflow/state/processed_events.yml` after
successful reconcile. On subsequent runs, the skill checks whether this
event ID has already been processed and no-ops if so. This handles
GitHub's at-least-once delivery semantics for retries.

```yaml
# .workflow/state/processed_events.yml
processed:
  - { id: "12345678", ts: "2026-05-09T10:23:00Z", event: "pull_request.opened" }
  - { id: "12345679", ts: "2026-05-09T10:24:00Z", event: "comment.created" }
# Entries older than 7 days are pruned on schedule.daily.
```

## Cost considerations

Each reconcile run consumes Actions minutes (free tier: 2000/month for
private repos; unlimited for public). A typical event run is 1–3
minutes. For a busy repo (50 events/day), that's roughly 75–150 minutes
per day, or 2250–4500 minutes per month — over the free tier.

To bound cost:

- **Skip trivial events at workflow level.** The `if:` conditions can
  filter (e.g., skip `synchronize` events on draft PRs, skip
  `issue_comment` that doesn't start with `/`).
- **Keep AI usage to `mechanical_first_then_llm`.** The default. Most
  events resolve mechanically without LLM calls.
- **Batch via schedule.** Some teams prefer reactive only on critical
  events (`opened`, `closed`, slash commands), with daily reconcile
  catching everything else. Configurable.

The `ai_usage` config controls API spending; the workflow `if:`
conditions control Actions minute spending. Neither cap is hard, but
both are visible in metrics reports.

## Local debugging

To debug what the workflow would do without running it in CI:

```bash
# Dry-run a real event payload
workflow-advisor reconcile \
  --event-name pull_request \
  --event-action opened \
  --event-payload ./fixtures/pr_opened.json \
  --transport github_actions \
  --dry-run

# Replay an already-processed event from the metrics log
workflow-advisor simulate replay --run-id 12345678
```

## Switching away from this transport

If the team migrates to `self_hosted_webhook` or `polling`:

1. Update `transport.mode` in `.workflow/config.yml`.
2. The skill detects the mode change, proposes removing
   `.github/workflows/workflow-advisor.yml`, and proposes the new
   transport's artifacts.
3. The user confirms; the change is committed.

The skill never silently disables a transport — switching is an
explicit, reviewed change.

## See also

- `references/transports/gh_forward.md` — local development transport.
- `references/transports/self_hosted_webhook.md` — production webhook
  receiver pattern.
- `references/transports/polling.md` — for environments without inbound
  webhooks.
- `references/transports/on_demand_only.md` — advisory-only mode.
