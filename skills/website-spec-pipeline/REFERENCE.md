# Website Spec Pipeline Reference

## Purpose

This skill formalizes website design as a multi-stage pipeline. Each stage takes a bounded input, produces a structured output, and hands that output to the next stage. The goal is to make website planning auditable, reusable, and generation-friendly.

The load-bearing artifact is the page specification. Later outputs should derive from it instead of reinventing structure in each prompt.

Content-first here means more than hierarchy. Before UX or visual design work starts, the workflow should consider what content types each page depends on, how that content is presented, what inputs need to be captured, and any editorial constraints that affect those choices.

## Repository invariant

This workflow assumes the user is operating inside a local git repository.

The repository is where the staged artifacts should live:

- discovery outputs
- sitemap and navigation contracts
- page specs
- responsive matrices
- wireframes
- review findings
- downstream implementation artifacts

If no git repository exists yet, do not continue generating the pipeline as if chat were the artifact store. First create or select the repository, then place the workflow outputs there.

## Artifact storage

The outputs of this workflow must be persisted as repository files. They must not exist only as conversational output.

Recommended layout:

```text
docs/website/
  discovery.json
  information-architecture.json
  page-plans.json
  ux-structures.json
  design-system.json
  responsive-matrix.json
  wireframes/
    home.md
    services.md
  reviews/
    review-01.json
  pages/
    home.page-spec.json
    services.page-spec.json
```

Rules:

- each stage writes a file before the next stage starts
- page-level specs get their own files once pages become independently actionable
- revisions should update the file history rather than leaving superseded decisions only in chat
- chat responses should summarize changes and point to file paths

If the repo already has a better-established planning folder, reuse it rather than forcing this exact layout.

## Stage model

### 1. Discovery

Purpose: understand the business, audience, competitors, and desired outcomes.

Inputs:

- business description
- target audience
- competitors or analogs
- primary goals such as lead generation, ecommerce, support, education, or hiring
- constraints such as brand, stack, approvals, legal, or timeline

Required output:

```json
{
  "business_summary": "",
  "personas": [
    {
      "name": "",
      "description": "",
      "jobs_to_be_done": [],
      "pain_points": [],
      "decision_triggers": []
    }
  ],
  "user_goals": [],
  "business_goals": [],
  "primary_cta": "",
  "secondary_cta": "",
  "success_metrics": [],
  "constraints": [],
  "assumptions": []
}
```

Exit criteria:

- personas exist
- business and user goals are distinct
- at least one primary CTA is explicit
- success metrics can be measured
- the discovery artifact is written to a repository file

### 2. Information Architecture

Purpose: define the pages, navigation, and content hierarchy.

Inputs:

- discovery contract

Required output:

```json
{
  "sitemap": [
    {
      "slug": "",
      "title": "",
      "parent": null,
      "goal": "",
      "audiences": [],
      "priority": "high"
    }
  ],
  "primary_navigation": [],
  "secondary_navigation": [],
  "user_tasks": [],
  "content_hierarchy_notes": [],
  "open_questions": []
}
```

Rules:

- use content-first design
- reflect user task analysis
- prefer simple navigation over stakeholder wishlists
- note where card sorting would likely change grouping
- identify where page structure depends on distinct content types or reusable content modules
- note where pages need specific content presentation patterns or input capture requirements

Exit criteria:

- every top-level page has a purpose
- navigation matches primary user tasks
- hierarchy does not depend on visual design to make sense
- the IA artifact is written to a repository file

### 3. Page Planning

Purpose: define the purpose and section inventory for every page before layout or styling.

Inputs:

- IA contract
- discovery contract

Required output:

```json
{
  "pages": [
    {
      "page": "",
      "goal": "",
      "audiences": [],
      "messages": [],
      "sections": [
        {
          "id": "",
          "type": "",
          "purpose": "",
          "content_type": "",
          "presentation_notes": [],
          "input_capture_notes": [],
          "content_constraints": []
        }
      ],
      "primary_cta": "",
      "secondary_cta": "",
      "dependencies": []
    }
  ]
}
```

Rules:

- do not propose visuals here
- sections must support the page goal
- CTA choice must trace back to discovery
- each section should note the content type it depends on
- call out when a section requires specific input capture or structured presentation

Exit criteria:

- every page has a goal
- every section earns its place
- the page can be understood as a content outline
- the page can be understood as a content and input requirement outline
- the page planning artifact is written to a repository file

### 4. UX Structure

Purpose: turn page sections into interaction and information blocks.

Inputs:

- page planning contract

Required output:

```json
{
  "page_structures": [
    {
      "page": "",
      "hero": {
        "headline": "",
        "supporting_copy": "",
        "primary_cta": ""
      },
      "content_blocks": [
        {
          "type": "",
          "purpose": "",
          "content_requirements": [],
          "interaction_notes": []
        }
      ],
      "trust_signals": [],
      "conversion_elements": [],
      "accessibility_notes": []
    }
  ]
}
```

Rules:

- use Nielsen heuristics as a review lens
- include error, empty, and success states where relevant
- favor scannable structures and obvious actions
- let content types and input needs inform layout choices rather than forcing them into preselected UI patterns

Exit criteria:

- the user can find the main action quickly
- trust and comprehension gaps are addressed
- accessibility notes exist for meaningful interactions
- the UX structure artifact is written to a repository file

### 5. Design System

Purpose: define reusable tokens and components after structure is known.

Inputs:

- UX structure contract
- brand constraints if available

Required output:

```json
{
  "tokens": {
    "spacing": {},
    "typography": {},
    "colors": {},
    "radius": {},
    "shadow": {}
  },
  "components": [
    {
      "name": "",
      "states": [],
      "variants": [],
      "content_rules": [],
      "accessibility_requirements": []
    }
  ],
  "layout_primitives": [],
  "motion_principles": []
}
```

Rules:

- do not invent components not justified by page structures
- define states explicitly, especially disabled, error, loading, and success
- accessibility belongs in the component contract
- write the design system artifact to a repository file
- do not define components that assume unrealistic content brevity or uniformity

### 6. Responsive Matrix

Purpose: define how each component and section behaves across breakpoints.

Inputs:

- design system contract
- UX structure contract

Required output:

```json
{
  "breakpoints": ["mobile", "tablet", "desktop"],
  "components": [
    {
      "name": "",
      "mobile": {
        "layout": "",
        "visibility": [],
        "interaction_changes": []
      },
      "tablet": {
        "layout": "",
        "visibility": [],
        "interaction_changes": []
      },
      "desktop": {
        "layout": "",
        "visibility": [],
        "interaction_changes": []
      }
    }
  ]
}
```

Rules:

- mobile-first by default
- note any content hidden at smaller sizes and why
- do not let desktop layouts define the structure retroactively
- write the responsive matrix artifact to a repository file

### 7. Wireframes

Purpose: produce low-fidelity layout representations driven by the contracts above.

Inputs:

- page planning contract
- UX structure contract
- responsive matrix contract

Required output:

- structured wireframe notes per page
- optional ASCII or block wireframes
- explicit mapping from wireframe areas to page sections

Suggested format:

```text
+----------------------------------+
| LOGO                 MENU        |
+----------------------------------+
| HEADLINE                         |
| SUBHEAD                          |
| [PRIMARY CTA]                    |
+----------------------------------+
| BENEFITS / TRUST / CONTENT       |
+----------------------------------+
| FAQ                              |
+----------------------------------+
| FOOTER CTA                        |
+----------------------------------+
```

Rules:

- no polished visual design here
- annotate content priority and CTA placement
- wireframes should be explainable directly from the page spec
- persist wireframes as files, ideally one file per page

### 8. Review

Purpose: critique the system without silently redesigning it.

Inputs:

- all earlier contracts

Required output:

```json
{
  "issues": [
    {
      "severity": "high",
      "stage": "ux_structure",
      "page": "services",
      "issue": "",
      "why_it_matters": "",
      "recommended_fix": ""
    }
  ],
  "checks": {
    "accessibility": "",
    "seo": "",
    "performance": "",
    "content_hierarchy": "",
    "mobile_first": "",
    "conversion": ""
  }
}
```

Rules:

- produce findings, not alternative designs
- trace each issue to a specific contract or missing dependency
- persist review findings as a repository file

## Canonical page specification

This is the artifact downstream generators should consume.

```json
{
  "page": "services",
  "page_title": "Services",
  "goal": "lead_generation",
  "audiences": ["buyer", "technical_evaluator"],
  "messages": [
    "Explain the service clearly",
    "Build trust quickly",
    "Reduce uncertainty before contact"
  ],
  "primary_cta": "Book a consultation",
  "secondary_cta": "Download brochure",
  "sections": [
    {
      "id": "hero",
      "type": "hero",
      "purpose": "orient_and_convert",
      "content_requirements": ["headline", "subhead", "primary_cta"],
      "content_type": "marketing_copy",
      "presentation_notes": ["short_headline_plus_supporting_copy"],
      "input_capture_notes": [],
      "content_constraints": ["headline_under_10_words", "no_unverifiable_claims"],
      "components": ["button", "badge"],
      "responsive_rules": {
        "mobile": "stacked_text_only",
        "tablet": "stacked_with_media",
        "desktop": "two_column"
      }
    },
    {
      "id": "benefits",
      "type": "feature_grid",
      "purpose": "clarify_value",
      "content_requirements": ["3_to_6_benefits"],
      "content_type": "benefit_list",
      "presentation_notes": ["repeatable_card_collection"],
      "input_capture_notes": [],
      "components": ["card"]
    },
    {
      "id": "faq",
      "type": "accordion",
      "purpose": "remove_objections",
      "content_requirements": ["questions", "answers"],
      "content_type": "faq_entries",
      "presentation_notes": ["repeatable_question_answer_pairs"],
      "input_capture_notes": [],
      "components": ["accordion"]
    },
    {
      "id": "cta",
      "type": "cta_band",
      "purpose": "convert",
      "content_requirements": ["cta_copy", "button_label"],
      "content_type": "conversion_prompt",
      "presentation_notes": ["short_conversion_prompt"],
      "input_capture_notes": ["lead_form_or_contact_route_if_applicable"],
      "components": ["button"]
    }
  ],
  "seo": {
    "intent": "commercial_investigation",
    "primary_keyword": "",
    "supporting_keywords": [],
    "internal_links": [],
    "meta_requirements": []
  },
  "accessibility": {
    "landmarks": [],
    "heading_strategy": [],
    "media_requirements": [],
    "form_requirements": []
  },
  "analytics": {
    "primary_conversion": "consultation_submit",
    "secondary_conversions": ["brochure_download"],
    "events": []
  },
  "dependencies": [],
  "assumptions": []
}
```

## Contract invariants

- The workflow runs inside a git repository, not as chat-only planning.
- Every stage artifact is persisted to files before the workflow advances.
- Later stages cannot contradict earlier goals without calling out the change.
- Every page needs a measurable goal.
- Every section needs a purpose.
- Important sections note the content type they depend on and any unusual input capture needs.
- Every CTA must trace back to discovery.
- Every interactive component must carry accessibility requirements.
- Every responsive rule must describe what changes and why.
- Review findings must point to a stage, page, or contract field.

## Anti-patterns

Reject or revise outputs with these smells:

- the user is not in a git repository and the workflow continues anyway
- one or more stage outputs exist only in chat
- content types and input capture needs are ignored until visual design
- the workflow jumps to mockups before page goals exist
- navigation is produced before user tasks are identified
- page sections are visual cliches instead of goal-driven content blocks
- design tokens exist but component states do not
- responsive behavior is implied rather than specified
- review feedback silently redesigns instead of diagnosing issues
- implementation code is generated from prose when a page spec could have been the source

## Downstream generation

Use the canonical page spec as the source for:

- wireframes
- design mockups
- React, Vue, Blade, Twig, or static HTML components
- CMS content models
- analytics event plans
- SEO metadata templates

If implementation starts without a page spec, note that the process has collapsed back into prompt-driven design and will be harder to audit.
