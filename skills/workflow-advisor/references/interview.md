# Interview Question Bank

The interview is **progressive** — demand-driven from this question bank.
The skill only asks what it needs to complete the current intent. First-time
bootstrap might ask 6 questions; later, when the user adds a profile, only
the new profile's questions are asked.

Questions are indexed by config key. Each entry has:
- **Key** — the config field this answers
- **Question** — the prompt
- **Options** — choices, where applicable
- **Inference hints** — how to guess from repo signals
- **Required for** — intents that need this answer

Inference behavior:
- Two independent signals → infer silently, note in summary.
- One signal → infer and confirm in the question.
- No signals → ask without a default.

---

## Bootstrap minimum questions (in order)

These run during stage 1 of bootstrap, in this order.

### `profiles.{name}.enabled`

> Which profiles do you want active?
>
> - [x] spec-driven (recommended)
> - [x] testability (recommended)
> - [x] observability (recommended)
> - [ ] documentation (heavier — adds audience-doc gates)
> - [ ] security (heavier — adds threat model gates for auth/payments)
> - [ ] accessibility (UI work only)
> - [ ] compliance (regulated environments — flips multiple defaults)

Inference hints:
- Heavy CI presence → user likely cares about observability.
- Existing `docs/runbook*` → strong signal for observability and documentation.
- Existing `SECURITY.md` → security profile candidate.
- Existing UI files → accessibility profile candidate.

Required for: bootstrap, profile addition.

---

### `repo.branch_model`

> Branch model — I detected {detected}. Confirm?
>
> - trunk-based (single main, short-lived feature branches)
> - github-flow
> - gitflow (with develop/release branches)
> - release-branches

Inference hints:
- `git log --all --format='%D'` shows long-lived `develop` → gitflow.
- Only `main` and short feature branches → trunk-based.
- Long-lived `release-*` branches → release-branches.

Required for: bootstrap, push playbook setup.

---

### `review_policy`

> How many reviewers are required to merge a PR?
>
> - 1
> - 2
> - 3+
>
> CODEOWNERS detected — should affected areas require codeowner approval?
> - [x] yes
> - [ ] no

Inference hints:
- Existing branch protection rules in provider → strongest signal for both.
- CODEOWNERS file present → bias toward yes on codeowner requirement.

Required for: bootstrap, gate setup.

---

### `roles.{role}.members`

> Roles — who plays each role?
>
> Based on git history:
> | Role | Default | Notes |
> |---|---|---|
> | architect | {top_committer} | most-active contributor |
> | tech_lead | {top_committer} | reviews most PRs |
> | reviewer | {active_reviewers} | active in reviews |
> | maintainer | {merge_actors} | merged to main |
>
> Edit any of these, or accept the defaults?
>
> Roles I have no signal for ({list}): can you assign someone, or skip
> for now?

Inference hints:
- `architect` / `tech_lead`: top contributor by merge count.
- `reviewer`: contributors with high `reviews/commits` ratio.
- `maintainer`: actors who merged PRs to default branch.
- `test_lead`, `sre`, `security`, `accessibility_lead`: no git signal;
  always ask.
- Audience roles: never inferred from git; always ask.

Required for: bootstrap, profile activation that introduces new roles.

---

### `artifacts.spec.lives_in` (and analogous)

> Where do specs live?
>
> I detected {n} files in `docs/` that look spec-like:
> {list}
>
> - [ ] keep in `docs/` (existing structure)
> - [x] move to `docs/specs/` (recommended for clarity once ADRs, runbooks, etc. join)
> - [ ] custom location

Inference hints:
- Files with numbered prefixes in a `docs/` directory → likely specs.
- ADR-formatted files (filename pattern, structured content) → existing ADRs.

Required for: bootstrap if existing artifacts detected.

---

### `linkage.spec`

> How should PRs reference their spec?
>
> - [x] PR body line: `Spec: docs/specs/0042-foo.md` (recommended, easy
>   to enforce)
> - [ ] commit trailer: `Spec-Id: 0042`
> - [ ] PR label

Inference hints:
- Existing PRs that mention specs by path → body line convention candidate.
- Existing `Issue:` or similar commit trailers → trailer convention candidate.

Required for: bootstrap, spec-driven profile setup.

---

### `transport.mode`

> How should the skill receive events from GitHub?
>
> - [a] GitHub Actions *(recommended for most teams)* — runs in your
>   repo's Actions on relevant events. Zero infrastructure. Pays Actions
>   minutes per event.
> - [b] `gh webhook forward` — events forward to a local machine running
>   the skill. Useful for local development. Requires keeping the session
>   running.
> - [c] Self-hosted webhook — you run a small server. Fastest, full
>   control, real infra cost.
> - [d] Polling — skill polls GitHub on a schedule. Works behind firewalls.
>   Higher latency.
> - [e] On-demand only — no reactive automation; skill runs only when
>   developers invoke it.

Inference hints:
- Repo behind firewall (no public hostname for webhook) → polling preferred.
- Solo / hobby contributor count → on_demand_only or polling.
- Active team with merge frequency → github_actions.

Required for: bootstrap (always asked).

---

## Profile-specific questions

These run when a profile is enabled, either at bootstrap or later.

### testability

`testability.thresholds.coverage.lines` and `.branches`:
> Coverage thresholds — what minimum line and branch coverage should
> trigger a warning or block?

`testability.thresholds.coverage.enforcement`:
> Coverage enforcement — should missing coverage warn (comment only)
> or block (cannot merge)?

`testability.levels.{level}.required_for`:
> Required test levels per change type — defaults are reasonable;
> change anything?

### observability

`observability.post_release.validation_window_days`:
> Post-release validation window — how many days should a release stay
> in `stage:released` before auto-advancing to `stage:validated`? (default 7)

`observability.signals.{signal}`:
> Required signals — defaults: logs and metrics always required, traces
> for performance-sensitive features, alerts for features and breaking
> changes. Customize?

### documentation

`documentation.audiences.{audience}.required_for`:
> Audience documentation — for each audience role, what change types
> require their doc?

`documentation.generation.release_notes.mode`:
> Release notes — should I draft them automatically (with product
> approval), require human authoring, or both options available?

### security

`security.classification_triggers`:
> Security-sensitive paths — defaults cover auth, payments, crypto,
> secrets. Add more?

`security.evidence`:
> Required security evidence — SAST, dependency audit, secret scan,
> pen test findings. Configure per change type?

### accessibility

`accessibility.standards.target`:
> Accessibility standard target — WCAG 2.2 AA (recommended), 2.1 AA,
> 2.2 AAA, or Section 508?

`accessibility.standards.enforcement`:
> Enforcement — warn (comment only) or block (cannot merge)?

### compliance

`compliance.frameworks`:
> Which compliance frameworks apply? (SOC2, HIPAA, GDPR, PCI DSS, custom)

`compliance.retention.audit_artifacts`:
> Audit retention — how long? (default 7 years for SOC2/PCI; varies)

> **Acknowledgement required:** enabling compliance will commit the
> decisions log and metrics events to the repo (required for audit).
> Historic process discussion will be in git history. Acknowledge to
> proceed.

---

## Operational questions

These don't run at bootstrap; they run on specific intents.

### `observability_reports.actor_attribution`

> When generating reports, how should actor attribution be rendered?
>
> - roles ("architect approved spec-0042") — safe for sharing externally
> - names ("bob approved spec-0042") — useful internally
> - hybrid ("architect (bob) approved spec-0042")

Required for: first report generation.

### `archive.on_threshold`

> Archive folder is approaching the migration threshold ({size}).
> What would you like to do?
>
> - [a] migrate `lifecycle/archive/` to a permanent docs location now
> - [b] increase the threshold and continue
> - [c] enable auto-prune (compliance teams: not recommended)

Required for: when archive crosses configured threshold.

### Existing-label triage

> You have {n} existing labels. None match my taxonomy. What should I do?
>
> - [a] Keep them all (canonical labels co-exist with existing — possible duplication)
> - [b] Alias the obvious ones (`bug` → `type:bugfix`, etc.) and keep the rest
> - [c] Show me the list and I'll decide per-label

Required for: bootstrap stage 4.

---

## When to ask

A question is asked when:
- The corresponding config field is needed for the current intent, AND
- The field is not already in `config.yml`, AND
- The field cannot be inferred from repo signals with confidence.

Otherwise:
- Inferred silently (and noted in any summary the skill produces).
- Filled from existing config (no question needed).
- Skipped if the intent doesn't need it.

The skill does not proactively walk the entire question bank. The
interview is reactive to what's needed.

## Resume across sessions

If a user abandons mid-interview, partial answers are saved to
`.workflow/.interview_in_progress.yml` rather than being written to
`config.yml`. On next invocation:

> I see we started a setup interview but didn't finish. Resume where we
> left off, or start over?

If the user restarts, the in-progress file is deleted and questions
re-asked. If they resume, the skill picks up from the next unanswered
question.
