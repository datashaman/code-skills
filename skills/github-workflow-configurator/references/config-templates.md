# Configuration Templates

Adapt these templates to the repository. Do not copy blindly.

## Workflow Policy

Path: `.github/sdlc-agent-workflow.yml`

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
  authority: "comment-only"
  command_prefix: "/agent"
  allowed_comment_prefixes:
    - "/agent"
    - "Product review:"
    - "Architecture review:"

github:
  branch_policy: "draft-pr-first"
  labels: "sparse"
  required_checks: []
```

## Issue Template

Path: `.github/ISSUE_TEMPLATE/change.yml`

```yaml
name: Change
description: Request a workflow change
title: "[Change]: "
labels: []
body:
  - type: textarea
    id: problem
    attributes:
      label: Problem
      description: What problem should this change solve?
    validations:
      required: true
  - type: textarea
    id: desired-outcome
    attributes:
      label: Desired outcome
      description: What should be true when this is done?
    validations:
      required: true
  - type: textarea
    id: acceptance
    attributes:
      label: Acceptance criteria
      description: Checklist or scenarios for acceptance.
    validations:
      required: true
```

## PR Template

Path: `.github/pull_request_template.md`

```markdown
## Issue

Closes #

## Summary

## Workflow

- Change folder:
- Current state:
- Product review evidence:
- Architecture review evidence:

## Validation
```

## Comment Event Workflow

Path: `.github/workflows/sdlc-agent-events.yml`

```yaml
name: SDLC Agent Events

on:
  issue_comment:
    types: [created]
  pull_request_review:
    types: [submitted]
  workflow_dispatch:
    inputs:
      command:
        description: "Agent command"
        required: true
        type: string

permissions:
  contents: read
  issues: write
  pull-requests: write

jobs:
  route:
    runs-on: ubuntu-latest
    steps:
      - name: Route event
        run: |
          echo "Event: ${{ github.event_name }}"
          echo "Actor: ${{ github.actor }}"
```

Before adding write steps, decide:

- which actors are allowed
- which command prefixes are accepted
- whether the workflow can push commits
- how idempotency is recorded

## Sparse Labels

Recommended labels:

- `implementing`: implementation work is active
- `needs-product-input`: blocked on product clarification

Avoid duplicating native GitHub state with labels for draft, ready, approved, merged, closed, or product review.
