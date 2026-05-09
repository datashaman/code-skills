# Roles Vocabulary

Roles are how the skill routes review, notification, and approval. Two
broad categories:

- **Delivery roles** — drive the development process: spec_author,
  architect, tech_lead, reviewer, maintainer, test_lead, sre, security,
  accessibility_lead.
- **Audience roles** — primarily approve their audience's documentation
  and consume system output: support, product, end_user_advocate,
  legal_compliance, auditor.

Roles can be played by:
- A GitHub handle (`{ type: github, handle: marlin }`)
- An external contact (`{ type: external, name: "Sam", contact: "sam@..." }`)
- A combination of both
- `any` (open to anyone with repo access — used for `spec_author` typically)
- Empty (gates route to `tech_lead` with `needs:role-assignment:{role}` flag)

A single person can hold multiple roles. The role resolver
(`scripts/helpers/role_resolver.py`) returns concrete members on demand,
de-duplicating when the same person plays multiple roles relevant to a
given gate.

---

## Delivery roles

### `spec_author`
**Responsibilities:** Draft specs and gather requirements.
**Default:** `any`. The role of spec author isn't gatekept — anyone can
draft. Approval is what gates entry to arch-review.
**Profiles:** spec-driven.

### `architect`
**Responsibilities:** Approve specs (when type triggers spec gate),
define interfaces, review architectural changes, sign off on ADRs.
**Default:** Empty until assigned in interview.
**Profiles:** spec-driven.
**Common alias names:** `design_lead`, `chief_engineer`.

### `tech_lead`
**Responsibilities:** Approve implementation plans, sign off breaking
changes, fallback for empty profile roles.
**Default:** Empty until assigned.
**Profiles:** spec-driven.

### `reviewer`
**Responsibilities:** General code review.
**Default:** Empty; often inferred from CODEOWNERS or recent contributors
during bootstrap.
**Profiles:** spec-driven.

### `maintainer`
**Responsibilities:** Releases, merges to default branch, branch protection
overrides.
**Default:** Empty until assigned; bootstrap infers from merge activity to
default branch.
**Profiles:** spec-driven.

### `test_lead`
**Responsibilities:** Approve test plans, sign off test evidence.
**Default:** Empty.
**Profiles:** testability.
**Common alias names:** `qa_lead`.

### `sre`
**Responsibilities:** Approve observability plans, validate
instrumentation, own alerts, conduct post-release validation.
**Default:** Empty.
**Profiles:** observability.
**Common alias names:** `devops`, `platform`.

### `security`
**Responsibilities:** Approve threat models, sign off security reviews,
triage findings.
**Default:** Empty.
**Profiles:** security.

### `accessibility_lead`
**Responsibilities:** Approve a11y plans, validate evidence, sign off
on user-facing changes.
**Default:** Empty.
**Profiles:** accessibility.

---

## Audience roles

These roles primarily approve their audience's documentation. Often held
by people without GitHub accounts; external members listed by name and
contact.

### `support`
**Responsibilities:** Approve troubleshooting guides, FAQs, known-issue
docs. Provide input on user-facing changes.
**Profiles:** documentation.

### `product`
**Responsibilities:** Approve feature overviews, positioning briefs,
release notes, rollout plans.
**Profiles:** documentation.

### `end_user_advocate`
**Responsibilities:** Approve user guides, migration guides, end-user
release notes.
**Profiles:** documentation.

### `legal_compliance`
**Responsibilities:** Approve compliance assessments, attest to releases,
review data-handling docs.
**Profiles:** compliance.

### `auditor`
**Responsibilities:** Read-only audit access. Consume audit trail; do not
approve.
**Access mode:** `read_only` (cannot dispatch state-changing actions).
**Profiles:** compliance.

---

## Role resolution rules

The resolver is called as `role.resolve(role_name, context)` where
`context` is optional and may include the changed paths (for area-aware
resolution).

Resolution algorithm:

1. **Aliases first.** If the role name is in `config.roles.aliases`, follow
   the alias to the canonical role.
2. **Members lookup.** Read `config.roles.{role}.members`.
3. **Special values.**
   - `any` → return repo collaborators (looked up via provider API).
   - Empty list → return `[]` and signal the empty-role fallback.
4. **CODEOWNERS overlay (for `reviewer`).** When resolving `reviewer` for a
   PR, intersect with CODEOWNERS patterns matching the PR's changed paths.
5. **Area-aware resolution.** If a role's members are scoped per area in
   config (e.g., `members.auth: [...], members.payments: [...]`), the
   resolver picks based on the PR's `area:*` labels.
6. **De-duplication.** Multiple roles requested in one gate (e.g., both
   `architect` and `tech_lead`) return distinct members across roles.

---

## Empty-role fallback

When a profile is enabled but a required role has no members, the gate
that would have required that role's approval routes to `tech_lead` with
a `needs:role-assignment:{role}` flag applied as a label.

Example: `obs-plan_approved` requires `sre` approval. If `sre.members` is
empty, the gate accepts approval from `tech_lead` for now, but the PR
remains labeled `needs:role-assignment:sre` until someone is assigned.
The skill will surface this in `/workflow-status` and in
`bootstrap_followup.md`.

This avoids two failure modes:
- **Silent skipping:** the gate just doesn't apply (loses safety).
- **Hard blocking:** the team can't merge anything because no one is
  assigned (loses momentum).

The fallback keeps the team moving while keeping the gap visible.

---

## External members

For audience roles particularly (support, product), members may not have
GitHub accounts. External members are formatted as:

```yaml
roles:
  support:
    members:
      - { type: github, handle: charlie }
      - { type: external, name: "Sam Patel", contact: "sam@company.com" }
      - { type: external, name: "Slack: #support-team", contact: "slack://channel/support-team" }
```

When `role.notify(support, ...)` runs:
- GitHub members get `@charlie` mentions in the comment.
- External members are listed by name with their contact in the comment
  body, so a teammate can route the message via the appropriate channel.

External members cannot dispatch slash commands (no GitHub identity), but
their approval can be recorded by a maintainer using `/attest` (compliance)
or by a tech_lead acknowledging "approved externally — see attached email"
in a comment that the skill records to the decision log.

---

## Adding a new role

1. Add to this file with responsibilities, profiles, common aliases.
2. Add to the `roles` section of config-schema.yml.
3. Update the relevant profile file (`references/profiles/{name}.md`) to
   declare which gates this role approves.
4. If the role uses area-aware resolution, document the area scopes here.
