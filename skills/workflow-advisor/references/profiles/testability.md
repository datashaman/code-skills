# Profile: testability

Adds test plan as a first-class artifact, gates on test levels and
coverage thresholds, introduces the `test_lead` role.

## Contributions

**Artifacts.** `test_plan` — required for feature/breaking. Approval from
`test_lead`. Lives in `docs/test-plans/`. Sidecar at
`.workflow/artifacts/test-plans/{id}.yml`.

**Lifecycle stages.** Adds `test-plan` stage. Default position: parallel
with `impl-plan`. Configurable via `lifecycle.composition` to be
sequential after `impl-plan` for stricter teams.

**Roles.** `test_lead` (default empty; falls back to `tech_lead`).

**Labels.** `stage:test-plan`, `test-plan:draft|in-review|approved`,
`needs:test-plan`, `needs:test-evidence`.

**Slash commands.** `/approve-test-plan`, `/sign-off-tests`.

**Gates.**
| Stage transition | Gate |
|---|---|
| spec → impl-plan | `test_plan_drafted` |
| impl-plan → review | `test_plan_approved` |
| review → merge-ready | `tests_pass`, `coverage_threshold_met`, `required_test_levels_present` |

## Test levels

Configurable per change type. Defaults:

```yaml
testability:
  levels:
    unit:        required
    integration: required
    contract:    required_for: [api_change, breaking]
    e2e:         required_for: [feature, breaking]
    performance: required_for: [breaking, performance_sensitive]
    security:    required_for: [auth, payments, pii]
```

The test plan must address each required level for the PR's classification.
The `test_plan.verify_levels_present` action checks the plan structure
(via headings or front-matter level list).

## Coverage thresholds

```yaml
testability:
  thresholds:
    coverage:
      lines: 80
      branches: 70
      enforcement: warn   # warn | block
```

`warn` posts a comment but doesn't block merge. `block` adds
`needs:test-evidence` and holds at `stage:review`. The skill reads
coverage from a configurable evidence path (e.g., `coverage/coverage.json`
attached to the PR via Actions artifact).

## Test plan template

Bootstrap installs `templates/test-plan.md`:

```markdown
---
id: {{ id }}
spec_id: {{ spec_id }}
state: draft
---

# Test Plan: {{ title }}

## Levels
- [ ] Unit
- [ ] Integration
- [ ] Contract
- [ ] E2E
- [ ] Performance
- [ ] Security

## Critical paths to cover
...

## Evidence
- Coverage report: ...
- Test run results: ...
```

The skill can scaffold this from a spec via `test_plan.scaffold(spec_id)`.

## Process tests starter pack

```yaml
# tests/feature_needs_test_plan.yml
name: feature PRs need an approved test plan to enter review
given:
  pr:
    type: feature
    spec_state: approved
    test_plan_state: null
when: pull_request.opened
then:
  labels_added: [needs:test-plan]
  stage: test-plan
```

```yaml
# tests/coverage_threshold_warns.yml
name: coverage below threshold warns but doesn't block (warn mode)
given:
  pr:
    type: feature
    coverage: { lines: 65, branches: 55 }
when: pull_request.synchronized
then:
  comments_match: ".*coverage.*below.*threshold.*"
  labels_not_added: [needs:test-evidence]   # warn mode
```
