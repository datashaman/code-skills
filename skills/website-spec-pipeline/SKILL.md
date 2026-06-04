---
name: website-spec-pipeline
description: Build a multi-stage website specification pipeline that moves from discovery through IA, page planning, UX structure, design system, responsive rules, wireframes, and review using JSON contracts between stages. Use when the user wants to design a website through agent handoffs, create auditable page specifications, generate downstream UI from structured artifacts, or avoid burying site architecture inside prompts.
user-invocable: true
---

# Website Spec Pipeline

Use this skill when the user wants to build a website through staged agent outputs rather than a single "design me a website" prompt.

## What this skill produces

The primary output is a chain of structured artifacts. The core artifact is the page specification, which downstream agents can use to generate wireframes, designs, components, views, or CMS models.

## Repository requirement

Run this skill from inside a local git repository. The repository is the natural home for discovery notes, IA contracts, page specs, wireframes, review findings, and later implementation artifacts.

If the user is not in a git repository, stop and say so plainly. Do not generate substantial artifacts into chat as a substitute for a project home. Treat repository selection or creation as the first prerequisite.

## Artifact persistence

The output of each stage must be stored as files in the repository. Do not let discovery notes, IA decisions, page specs, wireframes, or review findings exist only in chat.

Chat is for:

- explaining what was created
- calling out assumptions or blockers
- linking to the files that now hold the source of truth

Chat is not the artifact store.

## Stage order

Always work in this order:

1. Discovery
2. Information Architecture
3. Page Planning
4. UX Structure
5. Design System
6. Responsive Matrix
7. Wireframes
8. Review

Do not skip forward unless the user explicitly wants only a later-stage artifact. If a prerequisite is missing, flag the gap and state which earlier artifact is required.

## Operating rules

- Treat each stage output as the contract for the next stage.
- Prefer JSON for machine-readable artifacts; use Markdown only for commentary around the contract.
- Keep content and structure decisions ahead of visual styling.
- Consider content types, how they are presented, and how inputs are captured before making UX or visual design decisions.
- Make page goals, CTAs, and success metrics explicit before proposing sections or UI.
- Require responsive behavior, accessibility, and review criteria as first-class artifacts, not afterthoughts.
- Keep outputs auditable: if a later decision cannot be traced to an earlier artifact, call it out.
- Write each stage output to a stable file path before moving to the next stage.

## How to run it

1. Confirm the current folder is a git repository; if not, block on repository setup.
2. Identify the user's current stage and missing upstream inputs.
3. Produce the next contract in sequence.
4. Write that contract to the repository.
5. Validate the contract against the stage checklist in [REFERENCE.md](REFERENCE.md).
6. If the user wants implementation, generate from the page spec rather than from freeform prose.

## Core reference

See [REFERENCE.md](REFERENCE.md) for:

- the stage-by-stage workflow
- required inputs and outputs
- JSON contract shapes
- the canonical page-spec schema
- review criteria and anti-patterns
