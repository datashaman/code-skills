# Transport: gh webhook forward

Local development transport. Uses `gh webhook forward` from the GitHub
CLI to receive events on a developer machine. Designed for dogfooding,
debugging, or single-maintainer setups.

## When to use

- Developing the skill itself.
- Testing config changes against a real repo before committing.
- Single-maintainer hobbyist setups where the maintainer is always at
  their machine.

## When *not* to use

- Production. The forwarding session is bound to one developer's
  workstation and `gh auth`.
- Teams. Only one user can run the forward at a time per repo.

## Setup

### 1. Authenticate `gh`

```bash
gh auth login
gh auth refresh -h github.com -s admin:repo_hook
```

The `admin:repo_hook` scope is needed to register the webhook.

### 2. Run the forwarder

```bash
gh webhook forward \
  --repo=marlin/yuvee-backend \
  --events=pull_request,issues,issue_comment,push,release \
  --url=http://localhost:8080/webhooks
```

This:
- Registers a temporary webhook on the repo.
- Streams events to the developer's local URL.
- Cleans up the webhook on exit.

### 3. Run the skill's local receiver

```bash
workflow-advisor serve --port 8080
```

The receiver:
- Listens on `:8080/webhooks`.
- Verifies the `gh`-provided secret (passed via env var).
- Parses each event payload and invokes `workflow-advisor reconcile`
  with the normalized form.

## What bootstrap stage 3 generates

For this transport, no `.github/workflows/` file. Instead:

- `.workflow/transport/gh-forward.sh` — convenience script wrapping the
  `gh webhook forward` command above.
- `.workflow/transport/README.md` — instructions for running the
  forward and the receiver.

## Auth model

`gh webhook forward` uses the developer's `gh` auth. Commits made by
reconcile run under that developer's GitHub identity (not a bot
identity). This is acceptable for solo development; for shared use,
prefer `github_actions` or `self_hosted_webhook`.

## Limitations

- The forwarding session must stay running.
- `gh` rate limits apply.
- Restarts of `gh webhook forward` re-register the webhook.
- No persistence — if the developer is offline, events are lost.
- Slash commands work (events forward as expected) but only when the
  receiver is up.

## See also

- `references/transports/github_actions.md` — for the production default.
- `references/transports/self_hosted_webhook.md` — for production
  webhook deployments.
