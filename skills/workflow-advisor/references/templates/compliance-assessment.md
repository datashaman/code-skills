---
# Compliance assessment template (compliance profile).
#
# Required for changes touching pii, payments, regulated systems.
# Approved by `legal_compliance`. With audit-requiring frameworks
# enabled, this artifact's history is committed and never gitignored.
#
id:
title:
state: draft                           # draft | in-review | approved
spec_id:

# Frameworks this assessment addresses (from config.compliance.frameworks):
frameworks:
  - soc2

# Skill-managed:
revision: 1
content_hash: null
---

# Compliance assessment: {{ title }}

> Spec: [{{ spec_id }}](../specs/{{ spec_id }}.md)
> Frameworks: {{ frameworks }}

## Summary

In one paragraph: what changes, what controls are affected, and the
overall determination.

## Data flow impact

What data moves, where to, and what category does it fall under?

| Data | Category | Source | Destination | Encryption (transit / rest) | Retention |
|---|---|---|---|---|---|
| ... | PII / financial / health / general | ... | ... | ... | ... |

## Control mapping

For each applicable framework, which controls are touched?

### SOC2

| Control | Requirement | How this change addresses it | Evidence |
|---|---|---|---|
| CC6.1 | Logical access controls | ... | ... |

(Repeat per framework.)

## Residual risk

What risk remains after this change ships? Who accepts it?

## Attestation requirements

What attestations are required for release?

- [ ] legal_compliance attestation on release
- [ ] security attestation on release (if security-sensitive)

## Audit trail

The skill maintains an immutable audit trail entry for this assessment.
See `.workflow/artifacts/compliance/audit-trail/`.

## Approvals

- [ ] legal_compliance
- [ ] security (if applicable)
