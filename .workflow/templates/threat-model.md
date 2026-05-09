---
# Threat model template (security profile).
#
# Required for changes touching auth, payments, PII, network-facing,
# security_sensitive. Approved by `security` role.
#
id:
title:
state: draft                           # draft | in-review | approved
spec_id:
classification: standard               # standard | high-sensitivity

# Skill-managed:
revision: 1
content_hash: null
---

# Threat model: {{ title }}

> Spec: [{{ spec_id }}](../specs/{{ spec_id }}.md)

## System under threat

What's being protected? Data, capabilities, surfaces.

## Trust boundaries

Where does trust change? Where do user inputs cross into trusted code?

| Boundary | Outside | Inside | Crossing controls |
|---|---|---|---|
| ... | ... | ... | ... |

## Threats

For each threat, describe and rate.

| ID | Threat | STRIDE | Likelihood | Impact | Mitigation |
|---|---|---|---|---|---|
| T1 | ... | spoofing / tampering / repudiation / info-disclosure / DoS / elevation | low / med / high | low / med / high | ... |

## Mitigations and residual risk

For each threat above, what does the mitigation cover and what's left?

## Out of scope

Threats this model doesn't cover (and where they're handled instead).

## Open questions

- ...

## Approvals

- [ ] security
