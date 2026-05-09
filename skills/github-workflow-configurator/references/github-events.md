# GitHub Events And Automation

Use the smallest event surface that supports the workflow.

## Common Events

### `workflow_dispatch`

Manual trigger.

Use when:

- automation should be deliberate
- the team is still dogfooding
- permissions are sensitive

Strengths: safe, explicit, easy to test.

Weaknesses: less ergonomic for conversational workflows.

### `issue_comment`

Runs when a comment is created or edited on an issue or PR.

Use when:

- comments are command triggers
- solo product acceptance uses `Product review:` comments
- agents should react to `/agent ...` commands

Guardrails:

- check `github.event.issue.pull_request` before treating the comment as a PR comment
- require exact prefixes, such as `/agent implement`, `Product review:`, or `Architecture review:`
- check commenter permissions before write actions
- ignore comments from bots unless explicitly allowed

### `pull_request_review`

Runs when a PR review is submitted, edited, or dismissed.

Use when:

- independent human gates should trigger automation
- `Product review:` or `Architecture review:` review bodies are canonical gate evidence

Guardrails:

- check review state: `approved`, `changes_requested`, or `commented`
- inspect review body prefix when the workflow multiplexes product and architecture gates
- do not treat review comments as equivalent to an approval unless configured

### `pull_request`

Runs for PR lifecycle changes.

Useful actions:

- `opened`
- `ready_for_review`
- `synchronize`
- `reopened`
- `closed`

Use when:

- validation should run on every PR update
- ready-for-review should route a queue
- merge/close should update cleanup or reporting

Guardrails:

- avoid mutating code on every `synchronize`
- do not infer human approval from ready-for-review

### `issues`

Runs for issue lifecycle changes.

Use when:

- new issues should be converted into change branches or planning artifacts
- labels are queue signals
- issue close should trigger cleanup

Guardrails:

- avoid creating duplicate PRs from edited issues
- use idempotency markers such as issue comments, branch names, or config state

## Permissions

Start least-privilege:

```yaml
permissions:
  contents: read
  issues: read
  pull-requests: read
```

Add only when needed:

```yaml
permissions:
  contents: write
  issues: write
  pull-requests: write
  actions: read
```

Avoid broad write permissions for workflows that only observe or comment.

## Command Comment Pattern

Recommended command shape:

```text
/agent <verb> [target]
```

Examples:

```text
/agent create-change
/agent move architecture-review
/agent implement next-task
/agent summarize
```

For gates, use explicit prefixes:

```text
Product review: accepted.
Architecture review: approved for implementation.
```

## Idempotency

Automation should be safe to rerun.

Use one or more:

- branch naming convention
- PR link in issue comments
- workflow config file
- checked task boxes
- hidden HTML comment marker in bot comments
- state file transition record

Do not rely only on chronological GitHub timeline events.
