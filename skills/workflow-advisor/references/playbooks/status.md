# Playbook: status

A read-only playbook that renders the current workflow state for a PR,
issue, spec, or the repo as a whole. Invoked by:

- `/workflow-status` slash command on a PR or issue.
- `workflow-advisor status [target]` CLI command (interactive use).
- The dashboard view in process reports.

This playbook **never writes**. It does not pass through reconcile's
apply/cascade/log phases — only observe.

## Inputs

- Target — `pr-N`, `issue-N`, `spec-NNNN`, or absent (repo-wide).
- `config` — loaded from `.workflow/config.yml`.
- Sidecars in `.workflow/`.
- Provider state for the target (current labels, reviews, etc.) — fetched
  fresh, not cached.

## Steps

### 1. Resolve target

Parse the target argument:
- `pr-127` → `lifecycle/active/pr-127.yml`
- `issue-89` → `lifecycle/active/issue-89.yml`
- `spec-0042` → `artifacts/specs/0042-{slug}.yml`
- (none) → repo-wide summary

If the target is referenced from a slash command on a PR, the PR is
implicit; no parse needed.

If the target doesn't exist:
- For PR/issue: fall back to fetching from provider; if provider also
  shows nothing, respond with "no such PR/issue".
- For spec: fuzzy match by ID prefix and title keywords; suggest the
  closest match.

### 2. Observe target state

Read fresh:
- Sidecar from `.workflow/`.
- Provider state (labels, reviews, status checks, comments containing
  prior workflow-advisor status comments).
- For a PR: linked artifacts (specs, plans, docs) and their states.
- For a spec: linked PRs and impl-plans.

If sidecar and provider disagree, flag the discrepancy (don't silently
trust either) and surface in the rendered output.

### 3. Compose the status report

Per target type, the report has different sections.

#### PR status

```markdown
## Workflow status — PR #127

**Title:** Add user authentication flow
**Author:** @marlin
**Type:** type:feature
**Areas:** area:auth, area:pii
**Stage:** stage:review
**Linked spec:** [docs/specs/0042-user-auth.md](...) — state: approved

### Gates
| Gate | State | Notes |
|---|---|---|
| spec_linked | ✓ | linked to spec-0042 |
| spec_approved | ✓ | approved by @marlin (architect) on 2026-05-04 |
| impl_plan_approved | ✓ | approved on 2026-05-07 |
| test_plan_approved | ✓ | approved by @alice (test_lead) on 2026-05-07 |
| obs_plan_approved | ✓ | approved on 2026-05-07 |
| tests_pass | ✓ | last run 2026-05-09 |
| coverage_threshold | ⚠ | 78% lines (target 80%) — warn-only |
| min_approvals | ✗ | 1 of 1 received from codeowner; need 1 from architect |
| codeowners_approved | ✓ | @alice approved |
| no_unresolved_threads | ✓ | 0 open threads |
| security_review | ⚠ | no security role assigned (routed to tech_lead) |

### Required artifacts
| Artifact | Audience | State |
|---|---|---|
| spec | architect | ✓ approved |
| impl-plan | tech_lead | ✓ approved |
| test-plan | test_lead | ✓ approved |
| obs-plan | sre | ✓ approved |
| developer integration guide | developer | ✓ drafted, awaiting review |
| operator deployment guide | operator | needs:doc:operator |
| support troubleshooting | support | doc:support:skipped (reason: internal-only feature) |

### Reviewers assigned
- @marlin (architect) — pending
- @alice (codeowner: src/auth/) — ✓ approved
- @bob (codeowner: src/users/) — pending

### Next step
Awaiting architect approval (@marlin). Operator doc is needed before
merge.

### Recent decisions
- 2026-05-09T10:23 — substantive amendment to spec-0042; in-flight protection applied
- 2026-05-08T14:12 — test plan approved
- 2026-05-07T09:33 — impl plan approved
- See `.workflow/decisions/` for full history.
```

#### Issue status

Lighter; issues don't have all the gates PRs do.

```markdown
## Workflow status — Issue #89

**Title:** Users report slow login on mobile
**Type:** type:bugfix
**Areas:** area:auth, area:performance
**Stage:** stage:implementation (issue is being addressed in PR #127)
**Linked PR:** [#127](...)
**Reporter:** @customer-x
**Triaged:** @marlin (2026-05-01)

### Status
PR #127 is implementing this; see PR for current state.
```

#### Spec status

```markdown
## Workflow status — spec-0042

**Title:** User auth flow
**Path:** docs/specs/0042-user-auth.md
**State:** approved
**Author:** @marlin
**Architect approval:** @marlin on 2026-05-04
**Revision:** 8 (last change: substantive on 2026-05-09)

### Linked artifacts
- impl-plan: [docs/impl-plans/0042-user-auth.md](...) — state: in-review
- test-plan: [docs/test-plans/0042-user-auth.md](...) — state: approved
- obs-plan: [docs/observability/0042-user-auth.md](...) — state: approved
- threat-model: [docs/security/threat-models/0042-user-auth.md](...) — state: approved

### Linked PRs
- [#127](...) — stage:review (in-flight protection applied 2026-05-09)
- [#119](...) — closed (precursor)

### History
- 2026-05-09 — substantive amendment by @marlin (revision 7 → 8)
- 2026-05-04 — approved by @marlin (architect)
- 2026-05-02 — drafted by @marlin
```

#### Repo-wide status

```markdown
## Workflow status — marlin/yuvee-backend

### Active items
- 7 open PRs (4 in stage:review, 2 in stage:implementation, 1 in stage:spec)
- 12 open issues (5 triaged, 7 awaiting triage)
- 4 specs (3 approved, 1 in-review)
- 2 ADRs (both approved)

### Bottlenecks
- 3 PRs blocked > 5d:
  - #104: needs:spec-reapproval since 2026-05-02
  - #118: stage:arch-review awaiting @marlin since 2026-05-03
  - #122: stage:review awaiting @alice since 2026-05-03

### Stale specs
- spec-0038: in-review for 14d (last activity 2026-04-25)
- spec-0040: draft for 21d (last activity 2026-04-18)

### Role load (last 7 days)
- @marlin (architect, tech_lead, maintainer, sre, test_lead): 23 reviews
- @alice (reviewer): 9 reviews
- @bob (reviewer): 4 reviews

### Recent overrides
- 1 reclassification (spec-0038 substantive → editorial by @marlin, 2026-05-06)
- 1 gate override (min_approvals on PR #119 by @marlin, reason: hotfix, 2026-05-04)

### Health summary
3 PRs are bottlenecked. @marlin's review queue is full. Consider
delegating some architect responsibilities to @alice or recruiting
additional architects.
```

### 4. Privacy and attribution

If `observability_reports.reports.actor_attribution` is `roles`,
replace handles with role names in the rendered output:

> "Awaiting architect approval (architect)"

If `hybrid`:

> "Awaiting architect approval (architect: @marlin)"

If `names` (default):

> "Awaiting architect approval (@marlin)"

A `--render-as` flag overrides per-invocation (useful for sharing
externally even if config is `names` internally).

### 5. Output

For slash commands on PRs/issues:
- Post via `comment.update_or_post` with marker `<!-- workflow-advisor:status -->`
  so subsequent updates edit the existing comment.

For CLI invocations:
- Print to stdout in the requested `--format` (text, markdown, json).

### 6. No reconcile commit

This playbook does not write to `.workflow/`. The status comment posted
to the provider is the only side effect, and even that is idempotent
(update-or-post means re-running produces no change if the rendered
content is identical).

## Idempotency

Trivially idempotent — read-only. Re-running produces the same output
as long as observed state hasn't changed.

## Performance considerations

For repo-wide status, the playbook can be expensive on large repos
(many PRs, many sidecars). Two mitigations:

- The metrics rolling reports cache aggregations; status reuses them.
- For very large repos, status defaults to summarizing (top 5
  bottlenecks, top 5 stale items) with a note about how to drill in.

## See also

- `references/playbooks/pull_request.opened.md` — generates the initial
  status comment when a PR is opened.
- `references/vocabulary/actions.md` — `comment.update_or_post`,
  `gate.evaluate`, `role.resolve`.
- `references/metrics/` — report rendering shares output formatters
  with this playbook.
