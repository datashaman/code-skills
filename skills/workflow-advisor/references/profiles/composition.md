# Profile Composition

Profiles compose; the active lifecycle, label taxonomy, role list, and
gate set are computed from enabled profiles. This file documents the
interaction rules.

## Composition algorithm

`scripts/helpers/lifecycle.py` runs at config-write time and on profile
changes:

1. Read `config.profiles` to get the enabled set.
2. For each enabled profile, read its contributions (stages, gates,
   labels, roles, artifacts, slash commands).
3. Apply ordering rules (below) to compose the lifecycle sequence.
4. Apply dependency rules: profiles can declare `depends_on` and
   `gate_position`.
5. Resolve overlaps: when two profiles want the same artifact, share it
   (don't duplicate).
6. Write the composed view to `.workflow/lifecycle/composed.yml` for
   reference and debugging.

## Lifecycle stage ordering

Profile-contributed stages are slotted into a canonical sequence:

```
spec → arch-review → [planning] → implementation → review → merge-ready → [post-merge]
```

The `[planning]` slot is where `impl-plan`, `test-plan`, and `obs-plan`
land. By default, all planning stages run **in parallel** — they all
need to reach approved before `implementation` opens. Teams can switch
to sequential via:

```yaml
lifecycle:
  composition:
    planning_arrangement: parallel    # parallel | sequential
```

The `[post-merge]` slot is occupied by observability profile's `released`
and `validated` stages. Other profiles may add to this slot in the future.

## Dependency declarations

Each profile file declares dependencies in front-matter:

```yaml
---
profile: documentation
depends_on: [spec-driven]
gate_position:
  required_audience_docs_drafted:  after: spec_approved
  required_audience_docs_approved: after: impl_plan_approved
---
```

The composer respects these when slotting gates into the lifecycle. A
gate cannot be placed before its declared dependency is satisfied.

## Shared artifacts

When two profiles produce overlapping artifacts:

| Artifact | Profiles | Resolution |
|---|---|---|
| runbook | observability, documentation (sre audience) | observability profile owns the artifact; documentation profile cross-references |
| threat_model | security, documentation (security audience) | security profile owns; documentation cross-references |
| architecture_notes | documentation (architect audience) | satisfied by spec-driven's spec/ADR; documentation profile only requires the cross-reference |
| release_notes | documentation (end_user audience) | documentation profile owns; can be ai-drafted from spec-driven artifacts |

`scripts/helpers/artifact_store.py` includes a `resolve_artifact_ownership`
function that maps audience requirements to actual artifacts.

## Label namespace ownership

Label namespaces are owned by profiles to avoid collisions. When a
profile is disabled, its label namespace is not enforced (existing
labels with that prefix are preserved but no skill action targets them).

| Namespace | Owner profile |
|---|---|
| `stage:` | spec-driven (others contribute stages but namespace is shared) |
| `type:` | spec-driven |
| `area:` | spec-driven (with extensions from security/accessibility classification triggers) |
| `spec:`, `adr:`, `impl-plan:` | spec-driven |
| `test-plan:` | testability |
| `obs-plan:` | observability |
| `threat-model:` | security |
| `doc:{audience}:` | documentation |
| `compliance:`, `audit:` | compliance |
| `needs:`, `blocked:`, `review:` | shared (any profile contributes; values are scoped) |

## Role consolidation

When the same person plays multiple roles (common on small teams), the
role resolver de-duplicates. A reviewer assignment that requests both
`architect` and `tech_lead` returns a single member if marlin holds both
roles, with a note that the assignment satisfies both.

When two profiles both require a role to approve a single artifact, the
artifact's `approval_required_from` lists both roles; the gate fails
until both have approved.

Empty role fallback: when a profile-required role is empty, the gate
routes to `tech_lead` with a `needs:role-assignment:{role}` flag. This
applies per-profile; multiple empty roles can produce multiple flags
on a single PR.

## Compliance overrides

Compliance is unique in that enabling it changes defaults from other
profiles:

| Default | Without compliance | With compliance + audit framework |
|---|---|---|
| `decisions/` in gitignore | yes | no |
| `metrics/events.jsonl` in gitignore | yes | no |
| `archive.retention` | forever (default) | forever (forced) |
| Release attestations | not required | required |
| `auditor` role | not present | added with read_only access |

The bootstrap walkthrough surfaces these changes prominently at the
moment compliance is enabled. The user must acknowledge before bootstrap
proceeds.

## Lifecycle composition examples

### All seven profiles enabled
```
spec → arch-review → [impl-plan, test-plan, obs-plan] → implementation → review → merge-ready → released → validated
```
Plus audience-doc gates running in parallel during implementation/review;
plus security/a11y/compliance gates conditional on classification.

### Spec-driven only
```
spec → arch-review → impl-plan → implementation → review → merge-ready
```

### Spec-driven + testability + observability (default bootstrap)
```
spec → arch-review → [impl-plan, test-plan, obs-plan] → implementation → review → merge-ready → released → validated
```

### Compliance + spec-driven (regulated minimum)
```
spec → arch-review → impl-plan → implementation → review → merge-ready → released → validated
```
With compliance gates layered onto each transition; attestation required
at merge-ready and at release.

## Adding a new profile

When extending the skill with a new profile:

1. Create `references/profiles/{name}.md` with front-matter declaring
   `depends_on` and `gate_position`.
2. List its contributions: artifacts, stages, gates, labels, roles,
   slash commands.
3. Document any defaults this profile flips (use compliance as the
   pattern).
4. Add starter process tests.
5. Add to the profile table in `SKILL.md`.
6. Add to the composition rules above if it interacts with shared
   artifacts or label namespaces.
7. Add to `config-schema.yml` profiles list.
