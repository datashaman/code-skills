---
# Accessibility plan template (accessibility profile).
#
# Required for UI changes. Approved by `accessibility_lead`.
#
id:
title:
state: draft                           # draft | in-review | approved
spec_id:

# WCAG target (mirrors config default but can be overridden per spec):
standard:
  target: wcag_2_2_aa

# Skill-managed:
revision: 1
content_hash: null
---

# Accessibility plan: {{ title }}

> Spec: [{{ spec_id }}](../specs/{{ spec_id }}.md)

## Scope

What UI surfaces are affected?

## Standard target

{{ standard.target }}

## Plan by area

### Keyboard navigation

- Tab order: ...
- Focus indicators: ...
- Trapping concerns: ...

### Screen reader

- ARIA roles: ...
- Live regions: ...
- Labels and descriptions: ...

### Color and contrast

- Min contrast ratios met: ...
- Color-only signals: ...

### Reduced motion

- ...

### Forms and errors

- Error messaging strategy: ...
- Field labels: ...

## Evidence required for sign-off

- [ ] Automated scan output (axe / similar)
- [ ] Keyboard-only walkthrough recording or notes
- [ ] Screen reader walkthrough notes (NVDA / VoiceOver / JAWS)
- [ ] Contrast check results

## Out of scope

What's deliberately not covered (with reason).

## Approvals

- [ ] accessibility_lead
