---
# Implementation plan template.
#
# An impl-plan turns an approved spec into a sequenced delivery plan:
# what gets built, in what order, with what risk areas flagged. Approved
# by tech_lead. Approval is what gates entry to `stage:implementation`.
#
# Required fields:
id:                                    # matches spec id; e.g. "0042"
title:                                 # usually mirrors the spec title
state: draft                           # draft | in-review | approved
spec_id:                               # the spec this plan implements

# Optional:
estimated_effort:                      # team's preferred estimation unit (days, weeks, t-shirt)
risk_level: medium                     # low | medium | high
linked_prs: []                         # skill maintains this

# Skill-managed:
revision: 1
content_hash: null
last_observed: null
---

# Implementation plan: {{ title }}

> Spec: [{{ spec_id }}](../specs/{{ spec_id }}.md)

## Approach

How will we build this? State the design in implementation terms — what
modules change, what gets added, what the integration surface looks like.
Reference the spec for *what* to build; use this section for *how*.

## Sequence

Order the work into stages, each shippable independently if possible.

### Stage 1: ...

- Files to add/change: ...
- Dependencies: ...
- Acceptance: ...

### Stage 2: ...

## Risk areas

What might bite us? Highlight assumptions, untested integration points,
data migration concerns, perf cliffs.

## Out of scope

What the spec implies but this plan explicitly defers.

## Roll-out

How will this ship? Feature flag? Phased? All at once?

## Approvals

- [ ] tech_lead
