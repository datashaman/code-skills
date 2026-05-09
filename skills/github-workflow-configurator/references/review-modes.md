# Review Modes

Use review modes to adapt one workflow to different team shapes.

## Product Review

### `peer-po-review`

Use when another PO can review.

- PO Agent prepares product artifacts.
- PR is marked ready for product review.
- Another PO submits a GitHub PR review with a body starting `Product review:`.
- Workflow state links to the PR review.
- The workflow moves from product draft/preparation to architecture review.

Best for teams where product acceptance must be independent of the PR author.

### `self-comment-acceptance`

Use when working alone or when GitHub blocks self-approval.

- PO Agent prepares product artifacts.
- PR is marked ready for product review.
- The PO posts a PR comment starting `Product review:`.
- The comment can trigger automation.
- Workflow state links to the comment and explains why comment acceptance was used.
- The workflow moves from product draft/preparation to architecture review.

Best for solo workflows and dogfooding. It is weaker than peer review, but explicit and auditable.

## Architecture Review

### `architect-review`

Use when a human architect or tech lead can approve.

- Architect Agent prepares architecture/task artifacts.
- Architect submits a GitHub PR review with a body starting `Architecture review:`.
- Workflow state links to the PR review.
- Work moves to implementation or technical approval.

### `architect-comment-acceptance`

Use when a solo operator is also acting as architect.

- Architect decision is recorded with an `Architecture review:` PR comment.
- The comment can trigger automation.
- Workflow state links to the comment.

Use this only when independent technical approval is unavailable.

### `none`

Use for low-risk repos or experiments.

- No separate architecture gate.
- Product acceptance can move directly to implementation.
- Automation should still require explicit command comments before commits or merges.

## Gate Strictness

### `lightweight`

- Comment acceptance is allowed.
- Automation can react to explicit comments.
- Few required checks.
- Useful for solo exploration and workflow design.

### `standard`

- PR reviews preferred for gates.
- Comment fallback allowed only when documented.
- Required checks run before merge.
- Useful for small teams.

### `strict`

- Independent PR reviews required.
- Comment fallback disabled.
- Branch protection and required checks enforced.
- Automation cannot merge and may only push to branches under clear command.

Useful for production repositories.
