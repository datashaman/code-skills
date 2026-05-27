---
name: plan-website
description: |
  Creates a Work Breakdown Structure for planning and executing a website
  build from scratch or as a migration/overhaul. Organizes repository setup,
  planning artifacts, implementation slices, QA gates, and launch work into
  deliverables, work packages, and tasks, with phase checklists as supporting
  artifacts. Use when the user
  mentions building, launching, or overhauling a website: redesigns, CMS
  migrations, new site builds, or multi-team web projects. Triggers on phrases
  like "website build", "site launch", "web project checklist", "website
  redesign", "launching a site", "new website", or "website planning". Also
  use when the user wants to know what documents or deliverables a web project
  needs, or is coordinating design, dev, content, and SEO teams on a site.
user-invocable: true
---

# Plan Website - WBS-led website delivery planning

A website build (not just a redesign — if structure, content types, or CMS change, it's a build) is a multi-month, cross-team project. This skill creates a Work Breakdown Structure (WBS) that carries the project from repository foundation through planning artifacts, implementation slices, verification, and launch.

**Important distinction:** A *redesign* only re-skins an existing site. If content types, URL structure, database, or CMS change at all, it's a **build** — treat it accordingly.

## Phase order

Always walk through phases in this order. Each phase is a dependency for the next.

0. Discovery
1. Sitemap
2. Content Strategy
3. Wireframes
4. Designs
5. Analytics Implementation Plan
6. SEO Implementation Plan
7. Development
8. QA & Launch

## How to use this skill

When a user comes with a website build question:

1. **Identify the project type and current phase** in the dependency sequence.
2. **Create or preserve the WBS** as the source of truth for build plans, delivery plans, roadmaps, Growth projects, Jira epic lists, or implementation checklists.
3. **Surface the right questions** for the current phase (see per-phase sections below).
4. **Flag missing dependencies** — if they're in Phase 4 but have no signed-off wireframes, flag it.
5. **Attach supporting artifacts** to WBS items — checklists, template lists, brief outlines, review criteria, entry criteria, exit criteria, and sign-off gates.
6. **Don't let teams skip delivery work** — gently push back if the plan can reach QA or launch without a repository, implementation tasks, checks, deployments, and runnable behavior.

When the user explicitly asks what documents are needed before development, a document-only planning answer is allowed. When the user asks for a build plan, delivery plan, roadmap, Growth project, Jira epic list, WBS, or implementation checklist, create a WBS first and attach checklists to the relevant WBS items.

## Primary Output

The primary output is a Work Breakdown Structure.

Use checklists as supporting artifacts for specific phases, entry criteria, exit criteria, reviews, QA, and launch. Do not let checklists become the plan.

When the user asks for a website build plan, create a WBS first. Then attach phase checklists, review criteria, and sign-off gates to the relevant WBS items.

## Delivery Invariant

The primary output of this skill is a WBS, not a checklist. If the user asks for a project plan, roadmap, Growth project, Jira epic list, delivery plan, or implementation checklist, produce or preserve a WBS as the source of truth.

Never produce a WBS where discovery, sitemap, content, wireframes, designs, analytics plans, SEO plans, QA, and launch are the only work items. Those are supporting artifacts. They are not the whole build.

A valid WBS must include:

- an upfront repository creation/foundation task before substantial planning artifacts are generated
- deliverables, work packages, and tasks
- implementation work packages for each major user-facing capability
- tasks that produce code, configuration, migrations, tests, integrations, deployed environments, or runnable behavior
- QA/launch gates that depend on completed implementation work
- explicit rejection of launch readiness if no runnable site/app exists

## Work Breakdown Structure

For delivery planning, always create a WBS. A phase checklist is not enough and must not be presented as the plan.

The WBS must include:

- root deliverables tied to working increments or launch gates
- work packages under each deliverable
- implementation tasks under build work packages
- repository/artifact setup as the first foundation work package
- QA/launch tasks that depend on implemented software

The WBS must make it impossible to complete the project by finishing documents alone. If most WBS leaves are documents, specs, reviews, or checklists, revise it before presenting it.

## Repository Foundation

For any build, migration, CMS implementation, or redesign that changes code, templates, infrastructure, integrations, or deployment behavior, the plan must create or select the repository upfront, before generating substantial project artifacts.

Do not wait until a late "Development" phase to create the repo. The repository is the project memory from day one: discovery notes, sitemaps, content models, wireframes, design specs, analytics plans, SEO plans, ADRs, implementation plans, and QA runbooks should live there as versioned artifacts. Later, the same repository becomes the source of implementation evidence through commits, PRs, checks, deployments, and review history.

The repository foundation work item should cover:

- create or select the source repository
- establish the documentation/artifact folder structure
- commit initial project README and planning artifact index
- choose initial stack/framework/CMS structure
- add local development commands
- add baseline CI checks
- add environment/configuration strategy
- add first deployable/staging path where applicable

## Anti-Patterns To Prevent

Reject or revise any plan with these smells:

- There is no WBS.
- The WBS is only a flat phase checklist.
- The WBS leaf tasks are mostly documents, specs, reviews, or sign-offs.
- There is no upfront "create/select repository" task before docs/specs are produced.
- Planning artifacts are assumed to live only in chat, shared drives, or external docs with no versioned project home.
- Phase 7 is a single "Development" placeholder.
- QA/Launch has detailed checklists but development has no child work.
- Most tasks are named "define," "document," "plan," "specify," or "review."
- The plan can reach launch readiness without commits, PRs, checks, deployments, or runnable staging behavior.
- Evidence is treated as manually attaching links rather than producing real implementation artifacts.

## Phase 0: Discovery

**What it is:** The alignment phase before any artifact is produced — defining why the site exists, who it serves, and how success is measured.

**Why it matters:** Decisions made here cascade through every later phase. KPIs defined now drive the analytics plan (Phase 5); personas and journeys shape the sitemap (Phase 1) and content strategy (Phase 2). Skipping discovery is how a build ends up beautifully executed but aimed at the wrong target.

**Common deliverables:**

- Project brief / scope document / SOW
- Stakeholder map and RACI
- Competitor / market audit
- Personas and user journeys
- Brand guidelines / brand book
- Success metrics and KPIs

**Questions to ask:**

- What is the primary goal of this site, and how will you know it worked?
- Who are the main audiences, and what do they come to do?
- Who are the decision-makers and sign-off owners?
- Do brand guidelines already exist, or are they part of this project?

## Phase 1: Sitemap

**What it is:** A document listing every URL — existing and new — involved in the project.

**Why it matters:** Gives the dev team early visibility into content types, the scale of restructuring, and potential refactoring work — especially critical for migrations.

**Must include:**

- All existing URLs in scope
- All new URLs
- New URL structure if it's changing
- Clear indication of what's being kept, redirected, or removed

**Questions to ask:**

- Is this a new site or a migration from an existing one?
- Do you have an existing sitemap or URL inventory?
- Is the URL structure changing?

## Phase 2: Content Strategy

**What it is:** A plan that defines what content exists, what changes, and how content and site structure work together.

**Why it matters:** Content teams and UX/design must work in parallel — content shapes the most prominent components on the site. Starting dev without a content plan leads to placeholder hell and late-stage rework.

**Common deliverables:**

- Content audit (what to rewrite, redirect, or retire)
- New hub page outlines and copy
- Service/product page rewrites
- Character limits on hero and CTA copy
- CTA button copy guidelines

**Questions to ask:**

- Is there existing content to audit, or is this greenfield?
- Are there keyword or SEO targets driving the content structure?
- Who owns content creation — internal team or agency?

## Phase 3: Wireframes

**What it is:** The blueprints of the website. The single most important document type in a website build.

**Why it matters:** Wireframes are the contract between design, dev, and stakeholders. Incomplete or vague wireframes are the leading cause of feature creep, missed deadlines, and developer pain.

### Universal requirements (every wireframe)

- Define header level for every heading (H1, H2, H3, etc.)
- Define image aspect ratios for every image placeholder
- No color — white, black, and grays only
- Consider the critical path for every template
- Avoid real content (use placeholder text)
- Create mobile, tablet, and desktop versions for every template

### Required templates

A separate wireframe is needed for each unique template:

- Homepage
- Service/product hub page
- Individual service/product page
- General/default page (About, Careers, Privacy, etc.)
- Blog hub
- Blog post/single
- Blog category (if visually distinct from hub)
- 404 page

### Navigation wireframes

Navigation is its own mini-application. Cover all states:

- Default (top of page)
- Sticky (scrolled below fold)
- Mobile/tablet menu open
- Second/third level menu open (if applicable)
- Scroll-up sticky behavior (if applicable)
- Search form open/closed

### Form wireframes

For every custom form (skip if using embedded CRO tools like HubSpot/Pardot):

- Default/empty state
- Validation errors
- Successful submission
- Pagination (if multi-step)

### Component briefs

Each component and functional element should have a short written brief covering:

- Purpose and best use
- Rules and constraints
- Any flexible sizing behavior (e.g., "logo drops 10% into the hero")

### Best practices

- **Build mobile wireframes first** — mobile is the hardest and most constrained; work outward.
- **Use aspect ratios for images** — allows consistent sizing across devices (common: 1:1, 3:2, 4:3, 16:9).
- **All teams must review and sign off** — dev especially must flag issues before designs begin.
- Nothing proceeds to design until wireframes are finalized and approved.

## Phase 4: Designs

**What it is:** The visual layer applied to the wireframe scaffolding.

**Why it matters:** Designs should introduce zero new structure or functionality — only visual treatment. Surprises at the design stage mean the wireframes were incomplete.

**Preferred approach:** Component-based design system (see Brad Frost's Atomic Design). Avoid one-off page comps, which increase inconsistency and confusion.

**Design must define:**

- Design system: fonts, brand colors, header styles, button styles
- Zero edge cases — all colors, typefaces, and weights follow consistent rules
- Baseline HTML element styles:
  - H1–H6, Strong, Em, Blockquote, Quote
  - Links (default, hover, focus, active, visited)
  - Buttons (form submission, app actions)
  - Form fields (select, radio, checkbox)
  - Captions, paragraphs
- Every component in three states: ideal content, too little content, too much content
- Real approved copy examples in components

**Sign-off requirement:** All internal and external teams must review before development begins.

## Phase 5: Analytics Implementation Plan

**What it is:** A plan formalizing all analytics and tracking requirements — delivered to dev *before* development starts.

**Why it matters:** Some tracking requires dev work (custom events, data layer pushes). Springing these on devs mid-build causes delays.

**Common requirements:**

- Google Tag Manager installation
- Third-party analytics platforms
- CRO tool integration (Hotjar, Optimizely, etc.)
- Closed-loop / CRM integration
- Custom form tracking events
- Marketing funnel / conversion event tracking

## Phase 6: SEO Implementation Plan

**What it is:** A plan from the SEO team covering all technical SEO requirements — also delivered to dev before development starts.

**Common requirements:**

- 301 redirect map (critical for migrations)
- Schema markup requirements
- URL structure requirements
- robots.txt definitions
- Canonical tag strategy
- XML sitemap requirements

## Phase 7: Development

**What it is:** The build workstream where plans become runnable software, configuration, migrations, integrations, tests, and deployable environments.

**Why it matters:** Development is not one checkbox and not "assemble prior plans." For a build project, implementation work must be decomposed into vertical slices that produce working increments. QA and launch cannot verify documents in place of runnable behavior.

When generating a project plan, break development into vertical implementation slices such as:

- project foundation: repository, framework, environments, CI, deployment
- content model/CMS schema implementation
- template/page implementation
- navigation/search/forms implementation
- migration/import scripts
- analytics and SEO technical implementation
- integrations
- accessibility/performance hardening
- content publishing workflow
- production deployment

Each slice must have acceptance criteria based on runnable behavior:

- code exists
- tests/checks run where practical
- staging or local demo can exercise the feature
- QA can verify it against the relevant plan

**Development entry checklist:**

- [ ] Repository exists and contains the project README, artifact index, and planning history
- [ ] Sitemap finalized and signed off
- [ ] Content strategy complete; content either ready or on a firm schedule
- [ ] Wireframes complete for all templates, all breakpoints, signed off by all teams
- [ ] Designs complete, component-based, signed off by all teams
- [ ] Analytics plan delivered to dev
- [ ] SEO plan delivered to dev (including redirect map)
- [ ] All implementation slices are represented in the WBS with acceptance criteria
- [ ] All open questions resolved or explicitly tracked as blockers

## Phase 8: QA & Launch

**What it is:** The phase that takes a built site from "done on staging" to "live and verified in production."

**Why it matters:** Launch day is where the cost of every earlier shortcut comes due. A missing redirect tanks SEO rankings; an untested form silently drops leads; no rollback plan turns a small bug into an outage. Treat go-live as a deliberate, checklisted event — not the moment dev happens to finish.

Phase 8 cannot start unless:

- a repository exists and contains both the planning artifact history and implementation history
- the WBS includes completed implementation work packages for in-scope features
- a runnable staging or production-candidate environment exists
- all in-scope templates/features have implementation work items
- forms, redirects, analytics, CMS editing, and public pages are implemented
- QA is testing software behavior, not documents

Explicitly reject launch readiness if no runnable site/app exists.

**Common deliverables:**

- QA / test plan and cross-browser + device matrix
- Redirect testing (verifies the Phase 6 301 map against the Phase 1 sitemap)
- Analytics verification (events fire, goals record) against the Phase 5 plan
- Go-live runbook and rollback plan
- Post-launch monitoring plan (uptime, errors, Core Web Vitals)
- CMS training docs / client handover

**Launch checklist:**

- [ ] All templates QA'd across the supported browser/device matrix
- [ ] 301 redirects tested — every retired URL resolves to its replacement
- [ ] Analytics and conversion tracking verified firing in production
- [ ] XML sitemap submitted; robots.txt and canonicals confirmed
- [ ] Forms tested end-to-end (submission, validation, notifications)
- [ ] Rollback plan documented and the team knows who triggers it
- [ ] Post-launch monitoring live; owner assigned for the first 48 hours
- [ ] Stakeholders trained on the CMS and handover docs delivered

**Questions to ask:**

- What browsers and devices must be supported?
- Who owns the go/no-go decision on launch day?
- Is there a maintenance window, or is this a zero-downtime cutover?
- Who monitors the site immediately after launch, and for how long?
