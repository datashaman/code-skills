# Profile: documentation

The role-aware documentation profile. Every feature produces docs for
every audience role that needs them. This profile takes the position
that "documentation = developer docs" is wrong — operators, support,
end users, security, product, and others all consume features and need
docs targeted at them.

## The audience model

```yaml
documentation:
  audiences:
    developer:
      docs: [api_reference, integration_guide, code_comments]
      required_for: [feature, breaking, api_change]
    operator:
      docs: [runbook, deployment_guide, configuration_reference]
      required_for: [feature, breaking, infrastructure_change]
    sre:
      docs: [runbook, alert_response_guide]
      required_for: [feature, breaking]
    support:
      docs: [troubleshooting_guide, faq, known_issues]
      required_for: [user_facing]
    security:
      docs: [threat_model_summary, data_handling_notes]
      required_for: [auth, payments, pii, security_sensitive]
    product:
      docs: [feature_overview, positioning_brief, rollout_plan]
      required_for: [feature, user_facing]
    end_user:
      docs: [user_guide, release_notes, migration_guide]
      required_for: [user_facing, breaking]
    architect:
      docs: [architecture_notes]            # often the spec/ADR; cross-reference
      required_for: [feature, breaking]
    legal_compliance:
      docs: [compliance_impact_note]
      required_for: [pii, payments, regulated]
```

For a given PR, `docs.identify_required_audiences` computes the set of
required docs by intersecting the PR's classification (type + areas)
with each audience's `required_for`. A `type:feature, area:auth, area:pii`
PR needs docs for: developer, operator, sre, support, security, product,
end_user, architect, legal_compliance.

## Cross-referencing, not duplication

Some docs are already produced by other profiles:
- `architect`'s `architecture_notes` → the spec is usually this; just
  cross-reference.
- `sre`'s `runbook` → produced by observability profile.
- `security`'s `threat_model_summary` → produced by security profile.

The skill detects these cases and does not require a duplicate. A
spec link satisfies the architect's audience doc; the observability
profile's runbook satisfies sre's runbook; etc.

`docs.cross_reference_check` walks the artifact graph and surfaces
missing bidirectional links.

## AI-drafted vs human-drafted

Some docs the skill can draft from existing artifacts:

```yaml
documentation:
  generation:
    release_notes:
      mode: ai_drafted_human_approved   # skill drafts; product reviews
    api_reference:
      mode: extracted_from_code         # auto-generated; validated for completeness
    others:
      mode: human_drafted_from_template
```

`docs.draft_release_notes` reads merged PRs in the release range, the
specs they link to, and produces a release notes draft. The draft requires
`product` approval (`/approve-doc product`) before it's marked approved.

## Per-audience labels and gates

Each audience has its own state machine projected to labels:

- `doc:operator:draft` → `doc:operator:in-review` → `doc:operator:approved`
- `doc:support:draft` → ...
- (one set per audience)

Mutual exclusion within each audience's group.

Gates contributed:
| Stage transition | Gate |
|---|---|
| impl-plan → implementation | `required_audience_docs_drafted` |
| review → merge-ready | `required_audience_docs_approved` |
| merge-ready → released | `release_notes_published` |

## Stale doc detection

`docs.detect_stale` runs on `schedule.daily` and on substantive spec
changes. For each approved audience doc, it checks:
- Has the linked spec changed (revision bumped) since the doc was approved?
- Has any other artifact the doc depends on changed?

If yes: apply `needs:doc-update` to the audience doc, revert state to
`in-review`, notify the audience role.

## Slash commands

- `/approve-doc [audience]` — auth: the audience role.
- `/skip-doc [audience] --reason "..."` — auth: tech_lead + audience role.
  Loudly logged.
- `/draft-release-notes` — any role; output requires product approval.

## Audience role specifics

Audience roles often don't have GitHub accounts (support team uses Slack;
product manager uses email; legal works in a different tracker). Members
of audience roles are mixed:

```yaml
roles:
  support:
    members:
      - { type: github, handle: charlie }
      - { type: external, name: "Sam Patel", contact: "sam@company.com" }
```

When the skill needs `support` approval but only external members exist,
a maintainer can record approval via `/attest doc:support:0042 --by sam@company.com`
which writes a recorded attestation to the decision log.

## Process tests starter pack

```yaml
# tests/feature_user_facing_needs_user_guide.yml
name: user-facing features need an end_user user guide
given:
  pr:
    type: feature
    areas: [user-facing]
when: pull_request.opened
then:
  labels_added: [needs:doc:end_user]
```

```yaml
# tests/skip_doc_logged_loudly.yml
name: skipping a doc requires reason and logs prominently
given:
  pr: { type: feature, areas: [user-facing] }
  comment:
    body: "/skip-doc support --reason internal-only feature"
    author: tech_lead_member
when: comment.slash_command
then:
  decision_log_contains: ".*SKIPPED.*support.*reason.*internal-only.*"
  labels_removed: [needs:doc:support]
```
