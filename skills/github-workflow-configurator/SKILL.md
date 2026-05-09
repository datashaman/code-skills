---
name: github-workflow-configurator
description: |
  Interview a user about team composition, review gates, GitHub automation preferences,
  and agent execution style, then configure a repo-specific GitHub workflow approach.
  Use when asked to set up GitHub Actions/events, comment-triggered automation,
  PR review gates, solo-vs-team review modes, branch/label policy, or agent workflow automation.
---

# GitHub Workflow Configurator

> **WIP — not ready for use.** This skill is under active development and is not yet stable. Do not install it on a setup you care about.

Design and configure a GitHub-based workflow for agent-assisted delivery.

The skill adapts to how the user actually works: solo, with another PO, with an architect, with remote agents, or with a broader engineering team. Do not assume one universal workflow.

## Core Rule

Interview first, configure second.

If the repo already has workflow docs or automation, inspect them before asking questions. If the user's desired mode is already clear, ask only for missing decisions.

## Inputs To Inspect

Prefer local repo context when available:

- `.github/workflows/`
- `.github/ISSUE_TEMPLATE/`
- `.github/pull_request_template.md`
- `.github/CODEOWNERS`
- repo docs mentioning issues, PRs, agents, state, labels, reviews, or automation
- existing workflow config files such as `.github/sdlc-agent-workflow.yml`
- current branch, open PR, and issue context when relevant

Use `gh` or a GitHub connector when current remote settings, labels, branch protection, PR metadata, or Actions runs matter. Verify before editing.

## Interview

Ask concise questions. Prefer one pass with defaults the user can correct.

Required decisions:

- Team composition: `solo`, `two-po`, `po-architect`, `full-team`, or custom.
- Product review mode: `peer-po-review` or `self-comment-acceptance`.
- Architecture review mode: `architect-review`, `architect-comment-acceptance`, or `none`.
- Agent execution: `local`, `remote`, or `hybrid`.
- Automation trigger style: `workflow_dispatch`, `issue_comment`, `pull_request_review`, `pull_request`, or mixed.
- Automation authority: `observe-only`, `comment-only`, `commit-to-branch`, or `open-pr`.
- Gate strictness: `lightweight`, `standard`, or `strict`.

Useful follow-ups:

- Should comments trigger automation? If yes, what exact command phrases?
- Can automation push commits to PR branches?
- Should draft PRs be used before product review?
- Should labels be sparse queue signals or full state labels?
- Are branch protection rules already enforced?
- Which humans must remain in the approval loop?

## Configuration Output

Produce a short recommendation first, then implement if asked or if the user clearly requested configuration.

Recommended config shape:

```yaml
workflow:
  team_composition: "solo"
  agent_execution: "hybrid"
  gate_strictness: "standard"

reviews:
  product_review_mode: "self-comment-acceptance"
  architecture_review_mode: "architect-review"

automation:
  trigger_style: "issue_comment"
  authority: "commit-to-branch"
  command_prefix: "/agent"

github:
  branch_policy: "draft-pr-first"
  labels: "sparse"
  required_checks: []
```

If writing files, prefer:

- `.github/sdlc-agent-workflow.yml` for policy/configuration.
- `.github/workflows/sdlc-agent-events.yml` for Actions event routing.
- `.github/ISSUE_TEMPLATE/change.yml` for change requests.
- `.github/pull_request_template.md` for PR handoff context.
- docs updates that explain the chosen mode and event triggers.

## Decision Rules

- Preserve GitHub native state where possible: PR draft/ready, reviews, merged PRs, and closed issues should not be duplicated with labels.
- Use comments as event triggers only when the command phrases are explicit and auditable.
- Use PR reviews for human gates when possible.
- Use `Product review:` PR comments as an accepted fallback when the PR author cannot approve their own PR or no peer PO is available.
- Keep labels sparse unless the team explicitly wants labels as a queueing surface.
- Do not let automation merge code unless branch protection and required checks make that safe.
- Do not let automation change product intent silently. Require an explicit comment, review, issue update, or config change.

## Reference Loading

Load only what is needed:

- `references/review-modes.md` for solo vs team review-mode configuration.
- `references/github-events.md` for Actions events, permissions, and trigger patterns.
- `references/config-templates.md` for example config, issue templates, PR templates, and workflow snippets.

## Implementation Checklist

When configuring a repo:

- [ ] Inspect existing GitHub workflow files and docs.
- [ ] Interview for missing decisions.
- [ ] Propose a concrete mode and explain tradeoffs.
- [ ] Add or update config/docs/templates.
- [ ] Add or update GitHub Actions only when automation is requested.
- [ ] Keep permissions least-privilege.
- [ ] Validate YAML syntax where possible.
- [ ] Summarize chosen modes, files changed, and manual GitHub settings still needed.

## Manual Settings

Some settings may require GitHub UI or API access:

- branch protection rules
- required checks
- GitHub App installation permissions
- repository Actions permissions
- rulesets
- labels

If you cannot apply these directly, output exact settings for the user to apply.
