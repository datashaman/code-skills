---
# Runbook template.
#
# Owned by observability profile (operational instructions for SRE),
# also referenced by the documentation profile's `sre` audience.
#
id:
title:
state: draft                           # draft | in-review | approved
spec_id:                               # optional — runbooks may stand alone
service:                               # the service this covers
on_call_team:                          # which team's pager this rings

# Skill-managed:
revision: 1
content_hash: null
last_observed: null
---

# Runbook: {{ title }}

**Service:** {{ service }}
**On-call:** {{ on_call_team }}

## Overview

What is this service / feature? What does it do? Audience: an SRE
paged at 3am who's never touched this before.

## Health check

How do you tell if it's working?

- Dashboard: ...
- Health endpoint: ...
- Key metrics: ...

## Common alerts and responses

For each alert in the obs plan, give the response.

### Alert: {{ alert_name }}

**Symptom:** What does the alert text say?
**Likely cause:** ...
**Diagnosis:**
1. Check ...
2. Look at ...

**Mitigation:**
- Quick fix: ...
- Full fix: ...

**Escalation:** When to wake up the team lead.

## Operational tasks

How do you do common tasks?

### Restart the service

```
...
```

### Roll back a deployment

```
...
```

### Drain traffic

```
...
```

## Known issues

Things we know about that aren't auto-recoverable yet.

- ...

## Contacts

- Owning team: ...
- Adjacent teams: ...
- External vendor support: ...

## Approvals

- [ ] sre
