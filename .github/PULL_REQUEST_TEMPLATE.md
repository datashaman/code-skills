<!--
PR template installed by workflow-advisor.

The skill reads this PR's body for `Spec:`, `Test plan:`, `Observability plan:`
links to populate the lifecycle sidecar. Keep these lines if your team's
config uses `linkage.spec: body_line` (the default).

The lifecycle checklist below is for the human filling the PR; the skill
ignores it. The actual gate evaluation happens against the skill's
sidecar state, not the checkbox state.
-->

## Summary

A few sentences on what this PR changes and why.

## Linked artifacts

<!-- Edit these as you fill them in. The skill reads the file paths to
maintain bidirectional links. -->

- Spec: docs/specs/...
- Implementation plan: docs/impl-plans/...
- Test plan: docs/test-plans/...
- Observability plan: docs/observability/...
- Threat model: docs/security/threat-models/... (if security-sensitive)
- Issues: closes #...

## Type of change

<!-- Apply the matching `type:*` label, or let the skill auto-classify. -->

- [ ] feature
- [ ] bugfix
- [ ] breaking
- [ ] refactor
- [ ] docs
- [ ] dependency
- [ ] chore

## Lifecycle checklist

<!-- For the author's reference; the skill enforces gates separately. -->

- [ ] Spec drafted (if feature/breaking)
- [ ] Spec approved (if feature/breaking)
- [ ] Implementation plan approved (if feature/breaking)
- [ ] Test plan approved (if feature/breaking)
- [ ] Tests added/updated; coverage threshold met
- [ ] Observability plan approved (if feature/breaking)
- [ ] Instrumentation present (if obs plan requires it)
- [ ] Audience docs drafted (per documentation profile)
- [ ] Threat model approved (if security-sensitive)
- [ ] Accessibility evidence (if UI change)
- [ ] Compliance assessment approved (if PII / payments / regulated)

## Notes for reviewers

Anything reviewers should pay particular attention to.

---

<sub>Workflow status will be posted as a sticky comment shortly. Run `/workflow-help` for available commands.</sub>
