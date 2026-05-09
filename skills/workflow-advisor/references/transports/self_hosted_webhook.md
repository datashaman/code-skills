# Transport: self-hosted webhook

Production-grade transport. The team runs an HTTPS endpoint that GitHub
sends webhooks to. Lowest latency, full control, real ops cost.

## When to use

- High-volume repos where Actions minute consumption matters.
- Teams that need sub-second response time.
- Multi-repo setups where one webhook receiver serves many repos.

## When *not* to use

- Teams without ops capacity to maintain a service.
- Behind-firewall enterprises with restricted inbound — use polling.

## Architecture

```
GitHub → HTTPS POST → your endpoint → verify secret → queue → worker → reconcile
```

The endpoint can be:
- **Cloudflare Worker** — serverless, scales automatically, free tier
  often sufficient.
- **Fly.io / Railway** — simple container deploy.
- **AWS Lambda + API Gateway** — if already in AWS.
- **A small VPS with nginx + the receiver process** — lowest cost.

The receiver's job is small: verify, queue, return 200 fast. The actual
reconcile work happens asynchronously.

## What bootstrap stage 3 generates

For this transport:

- `.workflow/transport/cloudflare-worker.toml` — example Cloudflare
  config.
- `.workflow/transport/Dockerfile` — example container build.
- `.workflow/transport/fly.toml` — example Fly.io config.
- `.workflow/transport/README.md` — deployment guide with the variants.

The team picks one and deploys; the skill doesn't dictate which. The
receiver code itself ships in `scripts/transport/receiver.py` (FastAPI
app handling webhook verification and queuing).

## Required environment

- `WEBHOOK_SECRET` — for HMAC verification.
- `ANTHROPIC_API_KEY` — for LLM calls during classification.
- `GITHUB_TOKEN` (or app credentials) — for API calls back to GitHub.
- `WORKFLOW_REPO_PATH` — where the receiver clones the repo for
  reconcile (or path to a mounted volume).

## Auth model

The receiver makes commits under a configured bot identity (e.g., a
GitHub App installation token, or a PAT for a bot account). This is
preferable to running under a real developer's identity.

## Webhook registration

Bootstrap stage 4 includes a step to register the webhook against the
deployed endpoint. The user provides:
- Endpoint URL.
- Webhook secret.

The skill calls `gh api` to register the webhook with the right events.
This is a one-time per-repo step.

## Idempotency and retries

GitHub retries webhook deliveries that don't return 200 within 10s. The
receiver:
- Returns 200 immediately on receipt (after secret verification).
- Records the `X-GitHub-Delivery` UUID in
  `.workflow/state/processed_events.yml` (with TTL).
- Skips duplicates.

This keeps the webhook responsive while making reconcile robust.

## Failure modes

| Failure | Behavior |
|---|---|
| Receiver down | GitHub retries; events queue at GitHub for ~24h. After that, lost. Polling fallback as belt-and-braces. |
| Secret mismatch | Receiver rejects; emits metric. |
| Reconcile crash | Logged; next event re-evaluates cleanly. |
| Disk full / queue full | Receiver returns 500; GitHub retries. Alert on monitoring. |

## See also

- `references/transports/github_actions.md` — simpler default.
- `references/transports/polling.md` — for behind-firewall setups.
