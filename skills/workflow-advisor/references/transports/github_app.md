# Transport: GitHub App (v2 — deferred)

A formal GitHub App registration with a hosted backend. For multi-repo,
multi-org production deployments. **Deferred to v2.**

## Why deferred

- The current skill targets single-repo, single-team use.
- App-based deployment requires Anthropic (or another publisher) to
  host the App and maintain it as a service.
- App identity, rate limits, and installation-token management add
  complexity that's not needed for the v1 audience.

## What v2 adds (planned)

- Formal `marketplace.github.com` listing (or distribution path).
- App-identity commits (skill commits attributed to "workflow-advisor[bot]").
- Per-installation auth (no shared `GITHUB_TOKEN`).
- Multi-repo orchestration: one App installation manages many repos
  with shared roles and policies.
- Higher rate limits (App installations get 5000 req/hour per
  installation).

## Migration path from v1 self-hosted

Users on `self_hosted_webhook` can migrate to App-based:
1. Skill detects available App and prompts.
2. App installation auth replaces the bot PAT.
3. Webhook secret rotation is automatic.
4. Existing `.workflow/` is unchanged.

## What this means for the skill design now

The skill is built to be transport-agnostic. The `gh api` calls and the
reconcile loop don't care whether the auth is a `GITHUB_TOKEN`, a PAT,
or an App installation token. Adding the App transport in v2 is an
auth-layer change, not a core change.

## See also

- `references/transports/github_actions.md` — current default.
- `references/transports/self_hosted_webhook.md` — closest to App
  semantics in v1.
