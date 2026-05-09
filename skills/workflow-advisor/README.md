# workflow-advisor

A Claude skill that helps software teams adopt and run process — spec-driven
development, with first-class support for testability, observability,
role-based documentation, security, accessibility, and compliance —
through a progressive interview, a versioned configuration, and an
ongoing advisor that responds to GitHub events.

The skill is **versant in SDD** but does not assume it. The interview
adapts to the team's chosen profiles. Bootstrap can be lightweight (one
profile, six questions) or thorough (six profiles, role assignments,
audience documentation, post-release validation).

## What this skill does

- **Interviews** the team progressively about how they want to work,
  inferring from the repo where it can.
- **Generates** a `.workflow/` folder in the repo with config, artifact
  sidecars, lifecycle state, and starter tests.
- **Proposes** GitHub workflow files, label taxonomy, and PR/issue
  templates — applied only on confirmation.
- **Reconciles** repo state, provider state, and team-decided state on
  every event, producing one git commit per pass.
- **Cascades** changes — when a spec is amended, dependent impl-plans
  and PRs are flagged or reverted with in-flight protection.
- **Reports** on cycle times, gate friction, role load, and process
  health — with privacy-respecting defaults.
- **Adapts** as the team adds profiles, assigns roles, or changes
  cascade rules.

## Entry points

- **`SKILL.md`** — the top-level router. Read first to understand how
  the skill decides what to do.
- **`references/bootstrap.md`** — what happens on first run.
- **`references/reconcile.md`** — the core engine that runs on every
  event.
- **`references/config-schema.yml`** — the canonical config shape.
- **`scripts/cli.py`** — the `workflow-advisor` CLI entry point.

## CLI Quickstart

Bootstrap a repo-local `.workflow/` skeleton:

```bash
workflow-advisor interview --write-default --repo owner/repo
```

Inspect and validate state:

```bash
workflow-advisor doctor
workflow-advisor status
workflow-advisor lifecycle validate
```

Dry-run and apply reconcile passes:

```bash
workflow-advisor reconcile --dry-run --event-name pull_request --event-payload event.json
workflow-advisor reconcile --event-name pull_request --event-payload event.json
```

Inspect provider actions before mutating GitHub:

```bash
workflow-advisor provider-actions list
workflow-advisor provider-actions flush
workflow-advisor provider-actions flush --apply
```

Generate reports:

```bash
workflow-advisor report process
workflow-advisor report role-load
workflow-advisor report observability --format json
```

## Folder structure

```
workflow-advisor/
  SKILL.md                              # router
  README.md                             # this file

  references/
    bootstrap.md                        # first-run flow
    reconcile.md                        # core engine
    interview.md                        # progressive question bank
    config-schema.yml                   # canonical config shape

    vocabulary/                         # the skill's API
      events.md                         # 50 canonical events
      actions.md                        # ~75 actions playbooks dispatch
      commands.md                       # ~25 slash commands with auth
      labels.md                         # label taxonomy & mutual-exclusion groups
      roles.md                          # delivery + audience roles

    profiles/                           # methodology dimensions
      spec-driven.md
      testability.md
      observability.md
      documentation.md
      security.md
      accessibility.md
      compliance.md
      composition.md                    # interaction rules

    playbooks/                          # event handlers
      _dispatch.md                      # routing table
      pull_request.opened.md
      pull_request.synchronized.md
      push.md
      release.md
      issues.md
      comments.md
      comment.slash_command.md
      spec_change.md                    # upsert + cascade for artifacts
      status.md                         # read-only status rendering
      operational.md                    # /workflow-help, /workflow-reconcile, etc.

    transports/                         # how events reach the skill
      github_actions.md                 # default v1 transport
      gh_forward.md                     # local development transport

    templates/                          # artifact templates
      spec.md                           # canonical spec structure

  scripts/
    cli.py                              # workflow-advisor CLI
    helpers/
      reconcile/
        checkpoint.py                   # git-based safety net

  tests/
    smoke.sh                            # full local verification suite
    cli_matrix.sh                       # CLI command coverage
    package_smoke.sh                    # package install and console script
    *_smoke.py                          # focused helper smoke tests
```

## Reading order

For someone new to the skill, this is the recommended path:

1. **`SKILL.md`** to understand the operating model and routing.
2. **`references/bootstrap.md`** to understand the first-run experience.
3. **`references/reconcile.md`** to understand the core engine.
4. **`references/config-schema.yml`** to see the data model.
5. One profile of interest (e.g., `references/profiles/spec-driven.md`).
6. One playbook (e.g., `references/playbooks/pull_request.opened.md`).
7. **`references/vocabulary/`** as reference material — read sections
   when you need them.

For a contributor adding functionality:

1. Decide whether your change is a new event, action, command, label,
   profile, or playbook.
2. Add to the appropriate vocabulary file first.
3. If a new playbook: add to `references/playbooks/_dispatch.md` table.
4. If a new profile: add to `references/profiles/composition.md`
   interaction rules.
5. Add tests under `tests/` (skill tests, not user-repo process tests).

## Testing

Run the full verification suite from the repository root:

```bash
skills/workflow-advisor/tests/smoke.sh
```

The suite covers CLI routing, package install, provider actions, lifecycle
gates, cascade dependents, state I/O, polling, checkpointing, bootstrap, config
validation, templates, reports, and reconcile idempotency. For fast focused
checks, run the individual files under `skills/workflow-advisor/tests/`.

## Key design decisions

These are documented in detail across the references; brief summary
here:

- **`.workflow/` folder is committed to the repo.** Source of truth for
  team-decided state. Source of truth for *operational* state remains the
  provider; reconcile is the negotiation.
- **Reconcile loop is the core engine.** Five phases: observe, classify,
  apply, cascade, log. Idempotent. Every state-changing operation passes
  through it.
- **Git checkpointing for reversibility.** Each reconcile pass produces
  at most one commit, scoped to `.workflow/`. `git revert` unwinds.
- **Suggest-then-apply for writes outside `.workflow/`.** The skill
  proposes provider config changes and API actions; the user confirms.
- **Profiles compose.** Seven methodology dimensions, each contributing
  artifacts, gates, labels, roles, slash commands, lifecycle stages,
  metrics. Profiles can declare dependencies and ordering; the active
  lifecycle is rendered from enabled profiles.
- **Role-based documentation.** Documentation profile produces docs for
  every audience role that needs them: developer, operator, sre, support,
  security, product, end_user, legal_compliance, architect.
- **TDD and observability are first-class.** Both for the skill itself
  (unit tests, integration tests, simulator) and for the team's
  workflow (process tests in `.workflow/tests/`, cycle-time metrics,
  before/after comparison).
- **Privacy-respecting defaults.** Decisions log gitignored by default;
  metrics events gitignored by default; rolled-up reports committable.
  Actor attribution configurable per repo (`roles` | `names` | `hybrid`).
- **Transport-agnostic.** GitHub Actions is the v1 default; the design
  supports `gh_forward` (local development), self-hosted webhooks,
  polling, and on-demand-only modes.

## What v1 does not do

- **Multi-repo coordination.** Single repo only. Composing configs
  across repos in an org is v2.
- **Issue trackers other than GitHub.** Linear and Jira integration are
  v2.
- **GitHub Apps.** v1 ships as Actions + CLI, not as a registered App.
- **Branch protection enforcement without confirmation.** The skill
  suggests but never auto-applies.
- **Outcome metrics.** The skill measures process (cycle time, gate
  triggers, role load), not outcomes (defects, incidents). Reports
  delineate clearly.

## Status

This is a hardened draft. The foundations are documented, the surface area is
enumerated, helper coverage exists for the first-use workflows, and smoke tests
exercise bootstrap, reports, provider action queues, lifecycle gates, cascade
dependents, polling, checkpointing, package install, and reconcile idempotency.

Still missing before treating it as production-ready:

- Real-repository exercise with GitHub credentials.
- Richer event fixtures for review, label, close/merge, and protected-push flows.
- LLM-backed classification exercised against ambiguous spec-change cases.
- More user-facing examples as new workflows are validated.

Examples:

- [`references/examples/bootstrap-walkthrough.md`](references/examples/bootstrap-walkthrough.md)
- [`references/examples/event-trace.md`](references/examples/event-trace.md)
- [`references/examples/reconcile-pass.md`](references/examples/reconcile-pass.md)

## Contributing

When adding to the skill:

- **Stay inside the vocabulary.** If a playbook needs a new action,
  add it to `references/vocabulary/actions.md` first.
- **Update the dispatch table.** If you add a new event handler, the
  routing in `references/playbooks/_dispatch.md` needs to know.
- **Document profile contributions.** If your profile adds artifacts,
  gates, labels, roles, or commands, declare them in the profile file
  and update `references/profiles/composition.md`.
- **Test the reconcile path.** Any change to apply, cascade, or
  classification needs golden-file tests so behavior changes are
  visible in diffs.

## License

(To be determined.)
