# Transport: on-demand only

No reactive automation. The skill runs only when invoked locally —
either via Claude Code, the CLI directly, or chat. Pure advisory mode.

## When to use

- Teams evaluating the skill before committing to reactive automation.
- Solo developers who don't need bot automation.
- Compliance environments where any automated state change requires
  human review.
- Air-gapped or high-security environments.

## When *not* to use

- Teams that want gates enforced reactively. With on-demand, gates only
  apply when someone runs the skill; in between, they're advisory only.

## How it works

There is no transport. The skill runs only when invoked. Each invocation:
1. Fetches current GitHub state via `gh api`.
2. Reconciles against `.workflow/`.
3. Applies suggested changes (with confirmation in interactive mode).
4. Returns control.

Common invocation patterns:

```bash
# Check status of a specific PR
workflow-advisor status --pr 127

# Run reconcile on everything
workflow-advisor reconcile

# Simulate an event
workflow-advisor simulate --event-fixture pr-opened.json
```

Or inside Claude Code / chat:

> "Show me the workflow status of PR 127"
> "Reconcile the workflow folder against the current repo state"

## What bootstrap stage 3 generates

Nothing in `.github/workflows/`. Just a note in `.workflow/README.md`
explaining that reactive mode is off and how to invoke manually.

## Slash commands

Slash commands work but only when someone runs `workflow-advisor poll-comments`
manually, or when a developer runs `workflow-advisor reconcile --pr 127`
which observes new comments since the last reconcile.

This is acceptable for low-volume teams; lossy for active teams.

## Limitations

- **No reactive enforcement.** Gates that block PRs only block when
  someone runs reconcile.
- **Manual cadence.** Up to the team to run regularly. Bootstrap can
  add a calendar reminder or a git hook prompt.
- **Slash command latency.** As above — only when reconcile runs.

## Graduating to a reactive transport

This is often the starting point. When a team is ready, they update
`config.transport.mode` to one of the reactive modes; bootstrap stage 3
runs again, generating the appropriate provider configs.

The transition is non-destructive — the skill simply starts being
reactive in addition to on-demand.

## See also

- `references/transports/github_actions.md` — for graduating to default
  reactive mode.
- `references/transports/polling.md` — for half-reactive mode.
