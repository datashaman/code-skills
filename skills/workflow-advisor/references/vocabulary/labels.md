# Labels Vocabulary

The label taxonomy is the projection of folder state into the provider's UI.
Labels are organized by **namespace** (the prefix before the colon) and grouped
into **mutual exclusion sets** where only one label per group can be applied
at once (e.g., one `stage:*` per item).

Naming convention: `{namespace}:{value}`. Colon as separator. Lowercase.
Hyphens for multi-word values.

Color discipline: stages on a temperature gradient (cool → warm → green),
blockers in red, types in distinct hues. Colors are deterministic if not
specified — same taxonomy yields the same colors across repos.

---

## Stage labels (mutually exclusive group)

Lifecycle position. Exactly one applied per item with active lifecycle tracking.

- `stage:spec` — Drafting specification
- `stage:arch-review` — Architecture review in progress
- `stage:impl-plan` — Implementation plan being drafted
- `stage:test-plan` — Test plan being drafted (testability profile)
- `stage:obs-plan` — Observability plan being drafted (observability profile)
- `stage:implementation` — Code being written
- `stage:review` — Code review in progress
- `stage:merge-ready` — Approved, all gates pass
- `stage:released` — Deployed, in validation window (observability profile)
- `stage:validated` — Post-release validated (observability profile)

---

## Type labels (mutually exclusive group)

What kind of change this is. Drives which gates apply.

- `type:feature`
- `type:bugfix`
- `type:breaking`
- `type:refactor`
- `type:docs`
- `type:dependency`
- `type:chore`

---

## Area labels (multi-applicable)

What part of the system this touches. Drives role routing.

- `area:auth`
- `area:payments`
- `area:pii`
- `area:api`
- `area:ui`
- `area:infrastructure`
- `area:performance-sensitive`
- `area:security-sensitive`
- `area:user-facing`

Teams add their own area labels via config; `classification.area_triggers`
maps file patterns to area labels.

---

## Artifact state labels (one group per artifact type)

Each artifact type has its own mutually exclusive state group. Mirror the
sidecar `state` field.

Spec states: `spec:draft`, `spec:in-review`, `spec:approved`, `spec:superseded`.
ADR states: `adr:draft`, `adr:in-review`, `adr:approved`, `adr:superseded`.
Impl-plan states: `impl-plan:draft`, `impl-plan:in-review`, `impl-plan:approved`.
Test-plan states: `test-plan:draft`, `test-plan:in-review`, `test-plan:approved`.
Obs-plan states: `obs-plan:draft`, `obs-plan:in-review`, `obs-plan:approved`.
Threat-model states (security profile): `threat-model:draft`, `threat-model:in-review`, `threat-model:approved`.

---

## Needs labels (multi-applicable)

What's missing for the item to advance. Auto-applied on gate failure;
auto-removed on resolution.

- `needs:spec`
- `needs:adr`
- `needs:impl-plan`
- `needs:test-plan`
- `needs:obs-plan`
- `needs:test-evidence`
- `needs:instrumentation`
- `needs:threat-model` (security profile)
- `needs:a11y-plan` (accessibility profile)
- `needs:compliance-assessment` (compliance profile)
- `needs:attestation` (compliance profile)
- `needs:doc:{audience}` (documentation profile, one per missing audience)
- `needs:role-assignment:{role}` — empty role; gates routed to tech_lead

---

## Block labels (multi-applicable)

Process-state blockers. Visible reasons something can't move.

- `blocked:awaiting-spec-approval`
- `blocked:awaiting-arch-review`
- `blocked:in-flight-conflict`
- `blocked:by-issue` (with issue reference in comments)

---

## Review-routing labels (multi-applicable)

Signals which role's attention is needed. Translated to assignees by
`role.assign_reviewers`.

- `review:architect`
- `review:tech-lead`
- `review:test-lead`
- `review:sre`
- `review:security` (security profile)
- `review:accessibility` (accessibility profile)

---

## Audience-doc labels (documentation profile)

Per-audience doc state. Multiple audiences may have docs in flight at once.

- `doc:developer:{state}`
- `doc:operator:{state}`
- `doc:sre:{state}`
- `doc:support:{state}`
- `doc:product:{state}`
- `doc:end_user:{state}`
- `doc:security:{state}`
- `doc:legal:{state}`

`{state}` ∈ `draft | in-review | approved`. Per-audience these form
mutually exclusive groups.

---

## Decision labels (compliance / records)

Used on issues representing decisions (e.g., ADR-tracking issues).

- `decision:accepted`
- `decision:rejected`
- `decision:deferred`
- `decision:superseded-by-#N`

---

## Audit labels (compliance profile)

- `compliance:assessed`
- `compliance:attested`
- `audit:retained`

---

## Mutual exclusion groups (summary)

The skill enforces these exclusivity rules via `labels.swap_in_group`:

| Group | Labels |
|---|---|
| stage | all `stage:*` |
| type | all `type:*` |
| spec-state | all `spec:*` (except superseded which can co-exist briefly during transition) |
| adr-state, impl-plan-state, etc. | analogous per artifact |
| doc:{audience}-state | per audience |

All other label namespaces are multi-applicable (an item can have multiple
`area:*`, `needs:*`, `blocked:*`, `review:*` labels at once).

---

## Existing-label aliasing

Teams often have pre-existing labels that map to canonical taxonomy values.
The bootstrap interview handles aliasing; ongoing aliases live in
`config.yml` under `labels.aliases`. The skill treats aliased labels as if
they were canonical when reading; on writing, it always writes canonical.

Example:
```yaml
labels:
  aliases:
    bug: type:bugfix
    enhancement: type:feature
```

A PR labeled `bug` is treated as `type:bugfix` for gate evaluation; the
skill won't add `type:bugfix` (avoiding duplication) and won't remove `bug`
(respecting the team's existing labels).
