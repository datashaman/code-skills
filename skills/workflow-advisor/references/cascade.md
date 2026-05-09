# Cascade

Cascade rules describe what happens when a source artifact changes and other
work depends on it. The current v1 focus is spec changes affecting implementation
plans, active PRs, ADRs, and audience docs.

Every cascade pass follows the reconcile loop:

1. Observe changed artifacts and dependent lifecycle items.
2. Classify the source change as editorial, substantive, or structural.
3. Compute dependent actions from `.workflow/config.yml`.
4. Apply folder changes and queue provider actions.
5. Log decisions and metrics.

## Default Spec Rules

- Editorial spec changes do not reset dependent artifacts. Open PRs may get a
  notification.
- Substantive spec changes revert implementation plans to draft, send open PRs
  back to architecture review, and flag related ADRs.
- Structural spec changes archive superseded plans, link open PRs to the new
  spec, and append supersession notes to related ADRs.

## In-Flight Protection

When `preserve_in_flight` is enabled, active review or merge-ready work is not
silently rewound. The skill labels and notifies instead, then asks the relevant
role to choose whether to rebase, split, or override.

Provider effects should be implemented via provider actions, not directly in
cascade helpers.
