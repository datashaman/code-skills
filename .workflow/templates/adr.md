---
# ADR template for workflow-advisor.
#
# ADRs (Architecture Decision Records) capture decisions and their context.
# They differ from specs: specs describe what to build; ADRs describe why
# a design choice was made and what alternatives were considered.
#
# Required fields:
id:                                    # zero-padded integer, e.g. "0009"
title:                                 # short title, e.g. "Use JWT for session tokens"
state: proposed                        # proposed | accepted | superseded | deprecated
deciders:                              # list of GitHub handles or roles who made this decision
  - architect

# Optional but recommended:
date:                                  # ISO 8601 date when decision was made
related_specs: []                      # specs this decision affects
related_adrs: []                       # related ADRs (e.g., this builds on ADR-0003)
supersedes: []                         # ADR ids this replaces
superseded_by: null                    # set if this is later superseded
context_tags: []                       # e.g. ["security", "performance", "api"]

# Skill-managed:
revision: 1
content_hash: null
last_observed: null
---

# ADR-{{ id }}: {{ title }}

**Status:** {{ state }} ({{ date }})
**Deciders:** {{ deciders | from sidecar }}

## Context

What problem are we solving? What forces are at play? Include enough for
a future reader (or future you) to understand why this decision was on
the table at all.

## Decision

What did we decide? State it clearly enough that a reader can act on it
without reading the rest of the document.

## Alternatives considered

For each alternative, briefly state what it was and why we didn't pick
it.

### Alternative A: ...

### Alternative B: ...

## Consequences

What follows from this decision? Both positive and negative.

- Positive: ...
- Negative: ...
- Risks to monitor: ...

## Related

- Spec: ...
- Linked PRs: ...
- Linked issues: ...
