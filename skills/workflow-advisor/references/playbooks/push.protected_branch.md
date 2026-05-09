# Protected Branch Push

Handles `push.protected_branch`, emitted when a push lands on the default branch.

## Flow

1. Apply the normal `push.md` checks.
2. Detect whether the push corresponds to a merged PR, release commit, or direct
   default-branch push.
3. For direct pushes, log a decision and surface a warning unless the repo
   explicitly allows them.
4. If release artifacts changed, route to `release.md`.
5. If `.workflow/config.yml` changed, route to `operational.md` reconfigure
   handling.

This playbook is intentionally stricter than non-default branch push handling,
but branch protection changes remain suggest-only.
