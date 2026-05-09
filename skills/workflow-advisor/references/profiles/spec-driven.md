# Profile: spec-driven

The foundation profile. Defines the spec / arch-review / impl-plan
artifact lifecycle and the roles that drive it. Almost always enabled
for SDD-versant teams.

## What this profile contributes

### Artifacts

| Type | Required for | Approval from | Lives in |
|---|---|---|---|
| spec | feature, breaking, api_change | architect | docs/specs/ |
| adr | architectural_decision, breaking | architect, tech_lead | docs/adr/ |
| impl_plan | feature, breaking | tech_lead | docs/impl-plans/ |

### Lifecycle stages contributed

```
spec → arch-review → impl-plan → implementation → review → merge-ready
```

### Roles introduced

- `spec_author` (default: any)
- `architect`
- `tech_lead`
- `reviewer`
- `maintainer`

See [`../vocabulary/roles.md`](../vocabulary/roles.md) for full role
definitions.

### Labels introduced

- Stage labels: `stage:spec`, `stage:arch-review`, `stage:impl-plan`,
  `stage:implementation`, `stage:review`, `stage:merge-ready`
- Type labels: full set (`type:feature`, `type:bugfix`,
  `type:breaking`, `type:refactor`, `type:docs`, `type:dependency`,
  `type:chore`)
- Artifact-state labels: `spec:*`, `adr:*`, `impl-plan:*`
- Need labels: `needs:spec`, `needs:adr`, `needs:impl-plan`
- Block labels: `blocked:awaiting-spec-approval`,
  `blocked:awaiting-arch-review`, `blocked:in-flight-conflict`

### Slash commands introduced

- `/approve-spec`
- `/request-arch-review`
- `/sign-off`
- `/reclassify [editorial|substantive|structural]`
- `/supersede #N`
- `/override-gate [gate-name] --reason "..."`
- `/skip-stage [stage] --reason "..."`

### Gates contributed

| Stage transition | Gate | Owner |
|---|---|---|
| spec → arch-review | `spec_drafted`, `spec_approved_by_architect` (when type ∈ feature/breaking) | architect |
| arch-review → impl-plan | always passes if no architect review needed; otherwise architect approval | architect |
| impl-plan → implementation | `impl_plan_approved` | tech_lead |
| implementation → review | `linked_to_spec_when_required` | (mechanical) |
| review → merge-ready | `min_approvals_met`, `codeowners_approved`, `no_unresolved_review_threads`, `no_open_blockers` | (mechanical) |

## Cascade rules

When a spec changes substantively:
- `impl_plan` linked to it → revert to `draft` state.
- Open PRs implementing it → revert from `review` to `arch-review` (if
  `preserve_in_flight: false`); otherwise label `needs:spec-reapproval`
  and remain at current stage with notification.
- Related ADRs → flag for review (no auto-revert; ADRs are historical).

When a spec is editorial:
- No state changes downstream.
- Notify spec author and linked PR authors with a heads-up comment.

When a spec is superseded:
- Old impl_plan → archive.
- Open PRs → label `superseded-by:#N`, comment with new spec link, ask
  author to redirect.
- Related ADRs → append a supersession note.

## Configuration

Profile-specific config block in `config.yml`:

```yaml
spec_driven:
  artifacts:
    spec:
      required_for: [feature, breaking, api_change]
      template: .workflow/templates/spec.md
      lives_in: docs/specs/
      sidecar: .workflow/artifacts/specs/
      approval_required_from: [architect]
      front_matter_sync: true
    adr:
      required_for: [architectural_decision, breaking]
      template: .workflow/templates/adr.md
      lives_in: docs/adr/
      approval_required_from: [architect, tech_lead]
    impl_plan:
      required_for: [feature, breaking]
      template: .workflow/templates/impl-plan.md
      lives_in: docs/impl-plans/
      approval_required_from: [tech_lead]
  cascade:
    spec_substantive_change: ...        # see top-level cascade config
    spec_editorial_change: ...
    spec_supersession: ...
```

## Auto-classification triggers

This profile relies on `classification.type_triggers` to decide which PRs
need a spec. Without `type:feature` or `type:breaking` labels, no spec
gate fires. Triggers can be:

- Title keyword (e.g., "feat:", "feature:")
- Branch prefix (e.g., `feat/`)
- File patterns (e.g., new file in `src/api/`)
- Manual label

Configure in `classification.type_triggers` at config root.

## Spec linkage convention

PRs link to their spec via one of:
- **Body line** (default): `Spec: docs/specs/0042-user-auth.md` somewhere
  in the PR body.
- **Commit trailer**: `Spec-Id: 0042` in any commit message in the PR.
- **Label**: an explicit label like `spec:0042`.

The convention is set in `config.linkage.spec` and is enforced by the
`pr.link_artifacts` action which writes the resolved link into the PR's
lifecycle sidecar.

When linkage is required (PR is `type:feature` or `type:breaking`) and
missing:
- Apply `needs:spec` label.
- Comment with the convention and a link to draft a spec.
- Hold at `stage:spec` (don't advance).

## Sidecar shape

```yaml
# .workflow/artifacts/specs/0042-user-auth.yml
id: 0042
title: User auth flow
file: docs/specs/0042-user-auth.md
revision: 7
content_hash: sha256:a3f2...
last_observed: 2026-05-09T10:23:00Z
state: in-review
created: 2026-05-01
author: marlin
last_change_classification: substantive
approvals:
  required_from: [architect]
  received: []
  history:
    - { actor: bob, role: architect, at: 2026-05-04, state_before: in-review, state_after: approved }
    - { actor: skill, kind: cascade_revert, at: 2026-05-09, reason: "substantive amendment", state_before: approved, state_after: in-review }
linked_issues: [89]
linked_prs: [127]
supersedes: []
superseded_by: null
```

The history array makes the sidecar a self-contained audit trail per
artifact. Combined with git history of the sidecar file, every state
transition is reconstructable.

## Front-matter sync

The markdown spec file carries minimal front-matter mirrored from the
sidecar:

```yaml
---
id: 0042
title: User auth flow
state: in-review
last_updated: 2026-05-09
---
```

Front-matter is a *projection* of the sidecar, not the source of truth.
On reconcile:
- If front-matter and sidecar agree: no-op.
- If sidecar is newer (most common case): write front-matter from sidecar.
- If front-matter is newer (someone edited the markdown directly): treat
  as a manual edit per the upsert semantics — re-classify the change,
  update sidecar, run cascade.

## Process tests starter pack

When this profile is enabled, bootstrap creates these process tests:

```yaml
# .workflow/tests/feature_pr_requires_approved_spec.yml
name: feature PRs require an approved spec
given:
  pr:
    type: feature
    files: [src/auth.py]
    body: ""        # no spec link
when: pull_request.opened
then:
  labels_added: [needs:spec, type:feature]
  stage: spec
  comments_match: ".*spec.*required.*"
```

```yaml
# .workflow/tests/breaking_change_needs_adr.yml
name: breaking change needs ADR
given:
  pr:
    type: breaking
    files: [src/api/v2.py]
    body: "Spec: docs/specs/0042.md"
when: pull_request.opened
then:
  labels_added: [needs:adr]
```

```yaml
# .workflow/tests/bugfix_skips_spec_gate.yml
name: bugfix PRs skip the spec gate
given:
  pr:
    type: bugfix
    files: [src/auth.py]
when: pull_request.opened
then:
  labels_not_added: [needs:spec]
  stage: implementation       # bugfixes start at implementation
```

These run on every change to `.workflow/config.yml` as a CI check.

## Profile interactions

This profile is the foundation; others compose with it. Notably:

- **testability** adds `test_plan` artifact gates parallel to (or
  sequential after) `impl_plan`. Composition file controls the order.
- **observability** adds `obs_plan` artifact and post-merge stages.
- **documentation** adds audience-doc gates that reference the spec for
  cross-linking.
- **security** classifies PRs by file paths matching auth/payments/pii;
  reuses `architect` role's review for non-security-sensitive arch
  decisions.

See [`composition.md`](composition.md) for the full interaction matrix.
