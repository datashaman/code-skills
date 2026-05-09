# Profile: security

Threat models and security review as gated artifacts. Auto-classification
flags PRs touching auth, payments, PII, or other sensitive paths.

## Contributions

**Artifacts.**
- `threat_model` — required for auth, payments, pii, network_facing,
  security_sensitive. Approval from `security`.
- `security_review` — required for auth, payments, pii. Approval from
  `security`.

**Roles.** `security`.

**Labels.** `threat-model:*`, `needs:threat-model`, `needs:security-review`,
`security:findings-open`.

**Slash commands.** `/approve-threat-model`, `/sign-off-security`,
`/triage-finding [id] [severity]`.

**Evidence requirements.**
```yaml
security:
  evidence:
    sast_scan:           required_for: [feature, breaking]
    dependency_audit:    required_for: [dependency_change]
    secret_scan:         required
    pen_test_findings:   required_for: [auth, payments, regulated]
```

**Gates.**
| Stage transition | Gate |
|---|---|
| spec → impl-plan | `threat_model_drafted_if_required` |
| impl-plan → review | `threat_model_approved_if_required` |
| review → merge-ready | `sast_clean`, `no_high_findings`, `security_review_approved_if_required` |

## Auto-classification

```yaml
security:
  classification_triggers:
    paths: [src/auth/**, src/payments/**, "**/crypto.*", "**/secrets.*"]
    keywords_in_diff: [password, token, secret, api_key, encrypt]
```

A PR touching any of these gets `area:security-sensitive` automatically,
which triggers the threat model requirement. Reduces "we forgot to flag
this for security review" failures.

## Findings triage

When a SAST or dependency scan reports findings:
- Each finding is recorded as a sub-item with severity.
- `/triage-finding {id} {severity}` updates severity (e.g., downgrade a
  false positive).
- `no_high_findings` gate fails if any finding remains at high or
  critical after triage.

## Process tests starter pack

```yaml
# tests/auth_pr_needs_threat_model.yml
name: PRs touching auth files need a threat model
given:
  pr: { files: [src/auth/login.py] }
when: pull_request.opened
then:
  labels_added: [area:security-sensitive, needs:threat-model]
```
