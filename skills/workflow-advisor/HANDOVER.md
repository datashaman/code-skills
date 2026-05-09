# Handover: workflow-advisor skill

## What this is

A Claude skill that interviews a team about their dev process, generates
a `.workflow/` config, and acts as an ongoing advisor responding to
GitHub events. SDD-versant, with first-class support for testability,
observability, role-based documentation, security, accessibility, and
compliance.

The skill was designed and skeleton-drafted in chat sessions across two
days (~12 rounds of design discussion, then drafting). It is **not
production-ready** — it's a coherent skeleton with most reference docs
real, vocabulary registries complete, and Python helpers as working
stubs. The next phase is filling implementation gaps and testing
against a real repo.

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
│   ├── playbooks/                    # 10 playbook files + _dispatch.md
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

## Gaps to close (priority order)

### Tier 1 — would break on first real use

1. **Verify `checkpoint.py`'s public API matches what other helpers
   call.** Other helpers call `reconcile_with_checkpoint(intent,
   context)`. The earlier-session draft of checkpoint.py uses a
   `Session` dataclass; the actual entry point signature wasn't
   re-verified. Read `scripts/helpers/reconcile/checkpoint.py` end-to-end
   first.

2. **Wire up provider actions.** `apply.py` writes sidecars but doesn't
   call the provider (no label apply, no comment post, no reviewer
   assignment). Create `helpers/provider_actions.py` that wraps `gh api`
   for: `labels_apply_diff`, `comment_update_or_post`,
   `assign_reviewers`, `request_changes`, `dismiss_review`,
   `set_draft`. Hook these into the checkpoint after sidecar writes.

3. **Fix `transport/normalize.py:_h_push`.** Real GitHub push payloads
   don't have a top-level `files` field. The helper `_files_from_push`
   correctly aggregates from `commits[].added/modified/removed`, but
   `_h_push` should call it and put the result on the payload, not
   look for `payload.get("files")`. Same for PR — files come from a
   separate API call, not the webhook payload. Fix the contract:
   either fetch in normalize, or have playbooks fetch when needed.

4. **Trim `_dispatch.md` to match reality, OR stub the missing
   playbooks.** The dispatch table currently references playbooks that
   don't exist: `pull_request.ready_for_review.md`,
   `pull_request.closed.md`, `pull_request.merged.md`,
   `review.submitted.md`, `labels_changed.md`,
   `config_changed.md`, `profiles_changed.md`,
   `push.protected_branch.md`. Pick one approach and apply.

5. **Implement the remaining ~20 gates in `lifecycle.py`.**
   Currently only `spec_drafted`, `min_approvals_met`,
   `no_unresolved_review_threads`, `tests_pass`, `no_open_blockers`.
   The schema and playbooks reference about 25. Walk
   `references/config-schema.yml` `lifecycle.gates` section and
   implement each.

### Tier 2 — would surface during normal use

6. **Complete `cascade.find_dependents`.** Currently handles spec →
   impl_plan, open PRs, related ADRs, audience docs. Missing: spec →
   test_plan, obs_plan, threat_model. Look at the cascade rules in
   schema and audit coverage.

7. **Audience-doc templates.** Only `audience-operator.md` exists. Add:
   developer, sre, support, product, end_user, security, legal,
   architect. Use `audience-operator.md` as the pattern.

8. **Bootstrap-installed files that aren't templated.** Bootstrap
   references: `.workflow/.gitignore`, `.workflow/README.md`, the
   GitHub Actions workflow yml. Either generate inline (current
   approach, fine but fragile) or add to `references/templates/`.

9. **Skill-side tests in `tests/`.** Unit tests for helpers, especially
   classify.py, lifecycle.py composition, role_resolver.py
   resolution. Integration tests using fixtures of normalized events.
   Aim for coverage of the reconcile loop happy path first.

10. **Examples in `references/examples/`.** Sample bootstrap
    walkthrough output, sample event-to-playbook trace, sample reconcile
    pass. Useful for users debugging and for new contributors.

### Tier 3 — polish and follow-ups

11. **`pyproject.toml`.** The github_actions workflow does
    `pip install workflow-advisor`; no package metadata exists yet.

12. **Resolve doc references.** `references/cascade.md`,
    `references/reconfigure.md`, `references/metrics.md` are linked
    from SKILL.md but content lives elsewhere (mostly in
    `playbooks/operational.md`). Fix the links or split the file.

13. **CLI import naming.** `cli.py` does
    `from .helpers.reconcile import checkpoint as reconcile` then calls
    `reconcile.reconcile_with_checkpoint(...)`. Reads badly. Prefer
    `from .helpers.reconcile.checkpoint import reconcile_with_checkpoint`.

14. **LLM model string.** `llm.py` hardcodes
    `claude-sonnet-4-20250514`. Move to config.

15. **Polling-mode missed-event recovery.** `transport/poll.py` uses
    `_now_iso()` as the cursor on success but pulls `since=cursor`
    from the prior pass — a 60-second overlap is mentioned in the
    transport docs but not implemented. Add the overlap window.

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
