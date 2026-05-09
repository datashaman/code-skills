# Slash Commands Vocabulary

Slash commands are comments matching `/command [args]` posted on a PR or
issue. The `comment.slash_command` event carries the parsed command and
args. Each command maps to one or more actions, with auth checks via
`role.check_authority` against the `slash_commands` config block.

Format conventions:
- Commands are kebab-case: `/approve-spec`, not `/approve_spec`.
- Args after the command name; quote multi-word args.
- Free-form rationale via `--reason "..."` flag for override-style commands.

Each command entry below: name, what it does, default authorized roles,
and the action(s) it dispatches.

---

## Lifecycle commands

### `/approve-spec [spec-id?]`
Approve the linked spec (or one specified by ID).
Auth default: `[architect]`.
Dispatches: `artifact.update_state(spec, approved)` → `cascade.compute` if cascade rules apply.

### `/request-arch-review`
Move the item to `stage:arch-review`.
Auth default: `any`.
Dispatches: `stage.set(arch-review)` → `role.notify(architect)`.

### `/sign-off`
Mark a PR ready for merge if all gates pass.
Auth default: `[tech_lead, maintainer]`.
Dispatches: `gate.evaluate` → `stage.set(merge-ready)` if pass, otherwise `comment.post` with reasons.

### `/reclassify [editorial|substantive|structural]`
Override the classification of a spec amendment.
Auth default: `[architect, spec_author]`.
Dispatches: `artifact.classify_change` with override → `cascade.compute` (re-cascade).

### `/supersede #N`
Mark this artifact as superseding artifact #N.
Auth default: `[spec_author]` of the new artifact.
Dispatches: `artifact.supersede(old=#N, new=current)`.

### `/override-gate [gate-name] --reason "..."`
Mark a specific gate as satisfied despite mechanical failure.
Auth default: per-gate override policy in config.
Dispatches: `gate.override` → loud `decision.append`.

### `/skip-stage [stage] --reason "..."`
Skip a stage entirely. Loudly logged.
Auth default: `[tech_lead, maintainer]`.
Dispatches: `stage.skip` → loud `decision.append`.

---

## Testability commands

### `/approve-test-plan`
Auth default: `[test_lead]`.
Dispatches: `artifact.update_state(test_plan, approved)`.

### `/sign-off-tests`
Confirm test evidence is sufficient.
Auth default: `[test_lead, tech_lead]`.
Dispatches: `test_plan.check_evidence` → `gate.override(test_evidence_present)` if pass.

---

## Observability commands

### `/approve-obs-plan`
Auth default: `[sre]`.
Dispatches: `artifact.update_state(obs_plan, approved)`.

### `/sign-off-instrumentation`
Confirm instrumentation matches the plan.
Auth default: `[sre]`.
Dispatches: `obs.detect_instrumentation` → `gate.override(instrumentation_present)` if pass.

### `/post-release-validated`
Mark a release as post-release validated.
Auth default: `[sre]`.
Dispatches: `release.validated` event → `stage.set(validated)`.

### `/rollback-release [tag] --reason "..."`
Trigger rollback workflow.
Auth default: `[sre, maintainer]`.
Dispatches: `release.rolled_back` event → cascade.

---

## Documentation commands (documentation profile)

### `/approve-doc [audience]`
Approve the audience doc for the named audience.
Auth default: the audience role itself (e.g., `support` for `/approve-doc support`).
Dispatches: `artifact.update_state({audience}_doc, approved)`.

### `/skip-doc [audience] --reason "..."`
Skip the requirement for an audience doc.
Auth default: `[tech_lead]` plus the audience role.
Dispatches: `gate.override` → loud `decision.append`.

### `/draft-release-notes`
Trigger AI drafting of release notes.
Auth default: `any`.
Dispatches: `docs.draft_release_notes` → product approval still required.

---

## Security commands (security profile)

### `/approve-threat-model`
Auth default: `[security]`.
Dispatches: `artifact.update_state(threat_model, approved)`.

### `/sign-off-security`
Auth default: `[security]`.
Dispatches: `gate.override(security_review_approved)`.

### `/triage-finding [id] [severity]`
Auth default: `[security]`.
Dispatches: `security.classify_findings`.

---

## Accessibility commands (accessibility profile)

### `/approve-a11y-plan`
Auth default: `[accessibility_lead]`.

### `/sign-off-a11y`
Auth default: `[accessibility_lead]`.
Dispatches: `gate.override(a11y_evidence_present)`.

---

## Compliance commands (compliance profile)

### `/approve-compliance`
Auth default: `[legal_compliance]`.

### `/attest [artifact-id]`
Records a named attestation.
Auth default: per the artifact's required attesters.
Dispatches: `compliance.collect_attestations`.

### `/audit-export [range]`
Auth default: `[auditor, legal_compliance]`.
Dispatches: `compliance.export_audit_trail`.

---

## Operational commands (any role)

### `/workflow-status`
Comment with current stage, gates, missing items.
Dispatches: `gate.evaluate` → `comment.post`.

### `/workflow-reconcile`
Trigger a reconcile pass on the current item.
Dispatches: `reconcile.apply` scoped to item.

### `/workflow-help`
List available commands and the caller's authority.
Dispatches: `role.check_authority` per command → `comment.post`.

### `/workflow-explain [decision-id]`
Quote relevant decision log entry.
Dispatches: `decision.lookup` → `comment.post`.

### `/assign-role [role] [@user|external:contact]`
Assign a member to a role at runtime. Surfaces in next reconcile to clear
`needs:role-assignment:{role}` flags.
Auth default: `[maintainer]`.
Dispatches: `repo.config_changed` event after writing config.

---

## Adding a new command

1. Add an entry here with auth and dispatches.
2. Add to `slash_commands` in config-schema.yml with default auth.
3. Update transport normalization layer to recognize the command name.
4. Add a unit test for auth and dispatch.
