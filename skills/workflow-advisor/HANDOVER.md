# Handover: workflow-advisor skill

## What this is

A Claude skill that interviews a team about their dev process, generates
a `.workflow/` config, and acts as an ongoing advisor responding to
GitHub events. SDD-versant, with first-class support for testability,
observability, role-based documentation, security, accessibility, and
compliance.

The skill was designed and skeleton-drafted in chat sessions across two
days (~12 rounds of design discussion, then drafting). It began as a
coherent skeleton with most reference docs real, vocabulary registries
complete, and Python helpers as working stubs. A follow-up hardening pass
has closed the first-use blockers listed below and added smoke coverage.

## Current hardening status

Completed since the original handover:

- Checkpoint public API now has a compatibility entry point and smoke coverage.
- Provider actions are queued, listed, flushed, dry-run capable, and executable for
  labels, comments, reviewers, review requests, review dismissals, and draft/ready
  transitions.
- Marker comments are idempotent: apply mode looks up existing marker comments
  before deciding between PATCH and POST.
- Push normalization uses commit file lists and emits protected-branch events with
  an overlap-safe polling cursor.
- Dispatch references now point at existing playbooks for the originally missing
  PR/review/label/protected-branch flows.
- Lifecycle gates cover the configured profile gates used by the smoke suite,
  including testability and observability gates.
- Cascade dependency coverage includes test plans, observability plans, threat
  models, and audience docs.
- Audience templates exist for architect, developer, end_user, legal, operator,
  product, security, sre, and support.
- Bootstrap writes a usable `.workflow/` skeleton: config, schema version,
  README, `.gitignore`, and copied templates.
- Package metadata and console entry point exist, with package smoke coverage.
- Reports now render JSON correctly and include useful role-load, documentation,
  and observability summaries.
- The smoke suite covers CLI matrix, package install, provider actions, lifecycle
  gates, cascade dependents, state I/O, polling, checkpointing, bootstrap,
  config validation, templates, reports, and reconcile idempotency.

Known remaining hardening areas:

- Run against a real repository with GitHub credentials and review the queued
  provider actions before enabling `provider_actions.mode: apply`.
- Add realistic event fixtures for review, label, close/merge, and protected-push
  flows beyond the current smoke matrix.
- Move the LLM model string out of `helpers/llm.py` into config when LLM-backed
  classification is exercised.

## Layout

```
workflow-advisor/
├── SKILL.md                          # 250-line top-level router
├── README.md                         # User-facing overview
├── references/
│   ├── bootstrap.md                  # Multi-stage bootstrap walkthrough
│   ├── interview.md                  # Progressive question bank
│   ├── reconcile.md                  # Core engine semantics
│   ├── config-schema.yml             # Annotated canonical config
│   ├── vocabulary/                   # API contract — events, actions, commands, labels, roles
│   ├── profiles/                     # 7 profile files + composition.md
│   ├── playbooks/                    # event playbooks + _dispatch.md
│   ├── transports/                   # 6 transport modes
│   ├── providers/github.md           # GitHub provider abstraction
│   └── templates/                    # spec, adr, impl-plan, test-plan, obs-plan, runbook, etc.
└── scripts/
    ├── cli.py                        # Single entry point
    └── helpers/
        ├── config_io.py              # Load/save/validate config
        ├── detect.py                 # Repo inference for bootstrap
        ├── lifecycle.py              # Composition + gate evaluation
        ├── role_resolver.py          # Role → concrete members
        ├── labels.py                 # Taxonomy sync, mutex enforcement
        ├── artifact_store.py         # Sidecar I/O
        ├── lifecycle_store.py        # Lifecycle sidecar I/O
        ├── template.py               # Lightweight template rendering
        ├── diff.py                   # Unified diffs
        ├── llm.py                    # Anthropic API wrapper
        ├── doctor.py                 # Config + folder consistency checks
        ├── interview.py              # Progressive question runner
        ├── reconcile/                # observe / classify / apply / cascade / log / checkpoint
        ├── transport/                # normalize / poll / receiver
        ├── metrics/                  # Report computation
        └── migrations/               # Schema migrations
```

## Operating model (essential context)

**Two execution contexts** sharing state via `.workflow/` (committed):

- **Reactive (CI):** GitHub Actions runs the skill on event triggers.
- **Interactive (local):** Developer invokes via Claude or CLI.

Both pass through the same **reconcile loop**: observe → classify →
apply → cascade → log. Idempotent. Each pass produces at most one
git commit scoped to `.workflow/`, reversible via `git revert`.

**Trust model:**
- Free in CI; checkpointed git commit.
- Suggest-then-apply for semantic / provider-config / branch-protection changes.
- Branch protection: never auto-applied (one-way door).
- Self-loop guard at three layers: commit message prefix, author identity, path scope.

**Vocabulary is the API contract.** Playbooks dispatch by name from
`references/vocabulary/{events,actions,commands,labels,roles}.md`.
Adding behavior means: add to the registry, then implement.

## Foundational decisions (don't overturn without thought)

These were debated and decided in earlier sessions:

1. **GitHub-only single-repo for v1.** Provider abstraction is in place
   (see `helpers/transport/normalize.py` and `references/providers/github.md`)
   so other providers can be added later.
2. **Hidden `.workflow/` folder, committed.** Source of truth for
   process definition. Sidecars mirror artifact state.
3. **Reconcile loop is the only write path.** Every state change goes
   through it. No bespoke "apply this label" code paths.
4. **Profiles compose declaratively.** Each profile contributes
   artifacts, gates, labels, roles, slash commands, lifecycle stages.
   `helpers/lifecycle.py:compose()` runs the composition.
5. **TDD/observability as methodology profiles too** — the skill's own
   features are testable and observable.
6. **Mechanical-first classification, LLM for ambiguous.** Per
   `config.ai_usage.classification`. Spec amendments are
   `always_llm` because the judgment matters.
7. **In-flight protection is on by default.** Cascades label-and-notify
   rather than silently revert when downstream is mid-flight.
8. **Empty roles route to tech_lead with a flag.** Don't silently skip
   gates; don't hard-block on missing assignments.
9. **Transports are pluggable; github_actions is default.** `gh` CLI
   preferred for API calls.
10. **Templates use a tiny placeholder syntax**, not Jinja, to keep
    runtime deps minimal.

## Original gap checklist

This section preserves the original handover checklist for auditability. Most
items are now closed; use **Current hardening status** above for the live state.

### Closed

1. **Checkpoint public API verified.** `reconcile_with_checkpoint` exists as a
   compatibility entry point and has smoke coverage.
2. **Provider actions wired.** Labels, comments, reviewers, review requests,
   review dismissals, and draft/ready transitions are queued and executable.
3. **Push normalization fixed.** Push file lists come from commit file changes,
   and protected-branch handling is covered.
4. **Dispatch table aligned.** Referenced PR/review/label/protected-branch
   playbooks exist or route to operational playbooks.
5. **Lifecycle gate coverage expanded.** The configured profile gates used by
   current smoke coverage are implemented.
6. **Cascade dependents expanded.** Test plans, observability plans, threat
   models, active PRs, ADRs, and audience docs are covered.
7. **Audience templates added.** Architect, developer, end_user, legal,
   operator, product, security, sre, and support templates exist.
8. **Bootstrap skeleton added.** Bootstrap writes config, schema version,
   README, `.gitignore`, and copied templates.
9. **Tests added.** Smoke coverage exists for helper modules, CLI behavior,
   packaging, and reconcile idempotency.
10. **Examples added.** Bootstrap, event trace, and reconcile pass examples live
    under `references/examples/`.
11. **Package metadata added.** `pyproject.toml` defines the package and console
    script.
12. **Doc references resolved.** `references/cascade.md`,
    `references/reconfigure.md`, and `references/metrics.md` exist.
13. **Polling overlap added.** Polling uses an overlap window for missed-event
    recovery.

### Still Open

1. **LLM model config.** `helpers/llm.py` still hardcodes the model string; move
   it to config when LLM-backed classification is exercised.
2. **Richer event fixtures.** Add realistic fixtures for review submitted,
   label changes, close/merge, and protected-branch push flows.
3. **Real-repository validation.** Run against a real repo with GitHub
   credentials before enabling automatic provider-action apply mode.

## How to verify changes

After any non-trivial change:

```bash
cd workflow-advisor
python3 -c "
import ast, os
for root, _, files in os.walk('scripts'):
    for f in files:
        if f.endswith('.py'):
            with open(os.path.join(root, f)) as fp:
                ast.parse(fp.read())
print('OK')
"
```

For end-to-end testing once Tier 1 is closed:

```bash
# Validate config schema
python3 -m scripts.cli doctor

# Dry-run a bootstrap
python3 -m scripts.cli interview --scope bootstrap

# Dry-run an event
python3 -m scripts.cli simulate fixtures/events/pr_opened.json
```

For packaging:

```bash
# From the skill-creator skill location
python3 -m scripts.package_skill /path/to/workflow-advisor /path/to/output-dir
```

## What NOT to do

- Don't change the reconcile loop's five-step contract (observe →
  classify → apply → cascade → log). Other helpers depend on this.
- Don't add new top-level config keys without updating
  `config-schema.yml` and `helpers/config_io.py:validate`.
- Don't add new actions, events, or commands without registering them
  in `references/vocabulary/`. The vocabulary is the contract.
- Don't write to user code paths (`src/`). Only `.workflow/` and
  proposed `.github/` files.
- Don't auto-apply branch protection. Suggest only.
- Don't add MUSTs in instructional text where context would be clearer
  (per skill-creator guidance — the writing style is theory-of-mind,
  not heavy-handed).

## Related references for the next agent

- `/mnt/skills/examples/skill-creator/SKILL.md` — guidance for editing
  skills, packaging, evals.
- The skill's own `references/profiles/composition.md` — how profiles
  compose; useful when adding gates or stages.
- `references/reconcile.md` — the engine you'll be wiring most into.

## Last known good state

- 78 files, ~12,900 lines, all Python parses cleanly.
- Packaged successfully via `package_skill.py`.
- SKILL.md frontmatter validates as YAML.
- Has not been run end-to-end; no tests have been executed.

## Suggested first session in Claude Code

1. Read `SKILL.md`, then `references/reconcile.md`, then
   `scripts/helpers/reconcile/checkpoint.py` end-to-end.
2. Verify the public API contract between checkpoint.py and the other
   reconcile helpers; fix any mismatch.
3. Close Tier 1 #2 (provider actions) — that's the largest functional
   gap.
4. Add minimal unit tests as you go.
5. Try running `workflow-advisor doctor` against this skill's own repo
   and see what surfaces.
