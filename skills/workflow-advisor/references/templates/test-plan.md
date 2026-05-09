---
# Test plan template (testability profile).
#
# Approved by test_lead. Approval gates entry to `stage:implementation`
# (or earlier, depending on lifecycle composition).
#
id:                                    # matches spec id
title:
state: draft                           # draft | in-review | approved
spec_id:

# Test levels covered (the skill verifies these match the required
# levels for the change type via `test_plan.verify_levels_present`):
levels:
  unit: planned
  integration: planned
  contract: not_required
  e2e: planned
  performance: not_required
  security: not_required

# Skill-managed:
revision: 1
content_hash: null
last_observed: null
---

# Test plan: {{ title }}

> Spec: [{{ spec_id }}](../specs/{{ spec_id }}.md)

## Critical paths to cover

For each behavior the spec promises, name the test that verifies it.

| Spec section / behavior | Test | Level | Notes |
|---|---|---|---|
| ... | ... | unit / integration / e2e / ... | ... |

## Unit

What's covered at the function/class level? Edge cases, error paths.

## Integration

Where do components meet that this change affects? Database, queue,
external API, etc.

## Contract

(if api_change or breaking) What contract tests guarantee compatibility?

## End-to-end

What user-visible flows must keep working? Smoke tests for the new flow
plus regressions for adjacent flows.

## Performance

(if performance_sensitive) What load profile? What thresholds?

## Security

(if auth/payments/pii) What attacks are tested for? Reference the threat
model if one exists.

## Evidence

Where will the evidence land?

- Coverage report: ...
- Test run output: ...
- Performance report: ...

## Approvals

- [ ] test_lead
