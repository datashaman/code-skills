# Profile: accessibility

Activates for UI changes only. Auto-detects via UI file paths.

## Contributions

**Artifact.** `a11y_plan` — required for user_facing / ui_change.
Approval from `accessibility_lead`.

**Role.** `accessibility_lead`.

**Labels.** `needs:a11y-plan`, `area:ui`.

**Slash commands.** `/approve-a11y-plan`, `/sign-off-a11y`.

**Evidence requirements.**
```yaml
accessibility:
  evidence:
    automated_a11y_scan:    required
    keyboard_nav_tested:    required_for: [interactive_ui]
    screen_reader_tested:   required_for: [interactive_ui, content_change]
    color_contrast_checked: required_for: [visual_change]
  standards:
    target: wcag_2_2_aa
    enforcement: warn
```

**Gates.**
| Stage transition | Gate |
|---|---|
| impl-plan → implementation | `a11y_plan_drafted_if_ui` |
| review → merge-ready | `a11y_evidence_present`, `no_blockers` |

## Auto-classification

```yaml
classification:
  area_triggers:
    ui:
      paths: ["**/*.tsx", "**/*.jsx", "**/*.vue", "src/components/**"]
```

Backend-only PRs skip this profile entirely. The auto-classification
matters — without it, accessibility gates would create friction on
unrelated work.

## Process tests starter pack

```yaml
# tests/ui_change_needs_a11y_plan.yml
name: UI changes need an a11y plan
given:
  pr: { files: [src/components/Button.tsx] }
when: pull_request.opened
then:
  labels_added: [area:ui, needs:a11y-plan]
```

```yaml
# tests/backend_pr_skips_a11y.yml
name: backend PRs skip a11y gates
given:
  pr: { files: [src/db/migrations.py] }
when: pull_request.opened
then:
  labels_not_added: [area:ui, needs:a11y-plan]
```
