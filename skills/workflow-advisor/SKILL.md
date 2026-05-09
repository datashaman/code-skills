---
name: workflow-advisor
description: Interview a team about their development process, generate a configuration that captures it, and act as an ongoing advisor that responds to GitHub events (pushes, pull requests, issues, comments) to enforce, suggest, and adapt workflow over time. Versant in spec-driven development, with first-class support for testability, observability, role-based documentation, security, accessibility, and compliance methodologies. Use this skill when the user wants to set up team process automation, adopt SDD or related methodologies, configure GitHub workflow files from team interview, design event-driven CI/CD that adapts to project-specific roles and artifacts, or measure the effect of process changes on cycle time. Triggers on phrases like "set up team process", "workflow advisor", "configure SDD", "process automation", "team workflow", "GitHub workflow generation from interview", "spec-driven development setup", or any request to bootstrap a process for a repo from team interview.
---

# Workflow Advisor

A skill that interviews a team about how they work, captures the process in
a versioned configuration, and then acts as an ongoing advisor — reading
GitHub events, evaluating gates, proposing label changes, and surfacing
process metrics so the team can see what's working.

This skill is large because the surface area is real. The body of this
SKILL.md is a router; the actual work is delegated to reference files,
playbooks, and helper scripts.

## Operating model

The skill runs in two execution contexts that share state through a hidden,
committed `.workflow/` folder in the user's repo:

- **Reactive (CI):** GitHub Actions runs the skill on event triggers. The
  workflow file is generated during bootstrap. Non-interactive; runs to
  completion or fails. Auth via `GITHUB_TOKEN`.
- **Interactive (local):** Developer invokes the skill from Claude (chat
  or terminal). Conversational; supports interview, dry-running, debugging.

Both contexts use the same `workflow-advisor` CLI entry point. Both pass
through the same reconcile loop. Git is the synchronization mechanism
between them; `.workflow/` is the source of truth.

### The reconcile loop

The core engine. Every write — whether triggered by an event, a slash
command, a manual reconcile, or a folder edit — passes through:

1. **Observe.** Scan repo + provider, build observed state.
2. **Classify.** Categorize observed changes (editorial / substantive / structural).
3. **Apply.** Write sidecar updates idempotently.
4. **Cascade.** Propagate effects per cascade rules, with in-flight protection.
5. **Log.** Append decision entries.

Idempotent by construction: re-running on unchanged state is a no-op. Each
reconcile pass that writes produces at most one git commit, scoped to
`.workflow/` only. Commits are reversible via `git revert`.

See [`references/reconcile.md`](references/reconcile.md) for the full loop
semantics.

## When this skill triggers

Use the skill when:

- The user is in a project folder and asks about team process, code review,
  CI/CD, branching, releases, issue triage, PR automation, SDD adoption, or
  similar.
- A `.workflow/` folder needs creating or updating.
- An event payload (from CI or webhook) is being passed to the skill.
- The user wants to measure process impact, generate reports, or simulate
  config changes.
- The user mentions setting up workflows that respond to GitHub events.

Do **not** use this skill for:

- Generic CI/CD config writing without team-process context (use a simpler
  CI generator).
- Single-repo one-off automation unrelated to lifecycle / spec / process.
- Anything outside GitHub for v1 (other providers are abstracted in the
  design but not implemented).

## How to use

### Step 1: Detect repo state

On first turn:

1. Read [`references/bootstrap.md`](references/bootstrap.md) — the full
   bootstrap walkthrough.
2. Check for `.workflow/config.yml` in the working directory.
   - **Absent → bootstrap mode.** Read the bootstrap reference, run the
     progressive interview, propose the multi-stage bootstrap.
   - **Present → ongoing mode.** Load config; identify intent (advise,
     respond-to-event, generate, update-config, report); proceed.

### Step 2: Identify intent

Common intents:

| User says... | Intent | Next step |
|---|---|---|
| "set up", "bootstrap" | bootstrap | `references/bootstrap.md` |
| "show status of PR N" | status | `references/playbooks/status.md` |
| event payload provided | reactive | `references/playbooks/{event-name}.md` |
| "I changed the config" | reconfigure | `references/reconfigure.md` |
| "generate a report" | metrics | `references/metrics.md` |
| "simulate this event" | simulate | `references/playbooks/simulate.md` |
| "what would happen if..." | dry-run | `references/playbooks/simulate.md` |
| "amend spec X" | artifact change | `references/playbooks/spec_change.md` |
| `/{command}` posted | slash command | `references/vocabulary/commands.md` |

### Step 3: Run the relevant playbook

Playbooks are in `references/playbooks/`. Each is named after the event or
intent it handles. Playbooks reference the vocabulary (events, actions,
commands, labels, roles) and dispatch through the reconcile loop.

Never inline playbook logic in this SKILL.md. Routing to the right
playbook keeps the body tight and the playbooks reusable across both
execution contexts.

### Step 4: Propose, confirm, apply

Trust model for writes:

| What | Authorization |
|---|---|
| Read repo, provider, folder | Free. |
| Write `.workflow/` (idempotent state) | Free in CI; checkpointed git commit. |
| Write `.workflow/` (semantic changes — config, taxonomy, profiles) | Confirm in interactive; CI applies if event-driven. |
| Write provider config files (`.github/`, etc.) | Suggest; apply on confirmation. |
| Call provider APIs (labels, comments, assigns) | Suggest in interactive; apply directly in CI within `permissions:` scope. |
| Branch protection changes | Always require explicit confirmation. |

Diffs go through `comment.update_or_post` (idempotent) for in-PR proposals;
through inline chat for local interactive use. `pending.yml` holds
proposals between conversation turns so the user can refer back ("apply
the second one").

## Profiles

Methodology dimensions, each contributing artifacts, gates, labels, roles,
slash commands, and lifecycle stages. Read the profile file before relying
on its semantics.

| Profile | When to use | Reference |
|---|---|---|
| spec-driven | Almost always for SDD-versant teams | `references/profiles/spec-driven.md` |
| testability | Teams that gate on test plan + evidence | `references/profiles/testability.md` |
| observability | Teams that gate on instrumentation + post-release validation | `references/profiles/observability.md` |
| documentation | Teams that produce role-specific docs (operator, support, end_user, etc.) | `references/profiles/documentation.md` |
| security | Auth, payments, regulated, security-sensitive | `references/profiles/security.md` |
| accessibility | User-facing UI changes | `references/profiles/accessibility.md` |
| compliance | Regulated environments (SOC2, HIPAA, GDPR, PCI) | `references/profiles/compliance.md` |

Profile composition rules and interactions:
[`references/profiles/composition.md`](references/profiles/composition.md).

## Vocabulary

The skill's API contract. Always reference these by name; never hand-roll
their logic in playbooks.

- [`references/vocabulary/events.md`](references/vocabulary/events.md) — 50 abstract events with GitHub mappings
- [`references/vocabulary/actions.md`](references/vocabulary/actions.md) — ~75 actions playbooks dispatch
- [`references/vocabulary/commands.md`](references/vocabulary/commands.md) — ~25 slash commands with auth rules
- [`references/vocabulary/labels.md`](references/vocabulary/labels.md) — full label taxonomy with mutual-exclusion groups
- [`references/vocabulary/roles.md`](references/vocabulary/roles.md) — delivery and audience roles with resolution rules

## Helpers (Python)

Deterministic work — diffing, hashing, templating, reconciliation,
lifecycle composition, role resolution. The skill calls these for
mechanical operations; LLM judgment is reserved for classification of
ambiguous changes, comment drafting, and gate evaluation of subjective
criteria.

Layout in `scripts/helpers/`:

- `config_io.py` — load/save/validate config against schema
- `detect.py` — repo inference (provider, language, CI, branch model, contributors)
- `template.py` — render templates from `templates/`
- `diff.py` — unified diffs for proposals
- `reconcile/` — observe, classify, apply, cascade, log, checkpoint
- `lifecycle.py` — stage composition, gate evaluation
- `role_resolver.py` — role → concrete members
- `labels.py` — taxonomy sync, mutual-exclusion enforcement
- `artifact_store.py` — read/write artifact sidecars, front-matter sync
- `lifecycle_store.py` — read/write lifecycle sidecars, archive on close
- `transport/normalize.py` — provider event → abstract event translation
- `metrics/` — report computation, redaction, before/after comparison
- `migrations/` — schema migrations between versions

The CLI entry point is `scripts/cli.py`, exposing `workflow-advisor`
with subcommands matching the intents above.

## What this skill does NOT do

- It does not enforce branch protection without explicit confirmation
  (one-way door).
- It does not commit to user code files (`src/`, etc.); only to `.workflow/`
  and proposed `.github/` files.
- It does not store secrets; configs reference secrets by name.
- It does not run automation outside the configured transport (no
  background daemons, no implicit webhook receivers).
- It does not measure outcome metrics like "did this feature reduce
  defects" — only process metrics. Reports are clear about this scope.

## Failure handling

When reconcile crashes mid-pass:

1. The git checkpoint is the safety net. If `reconcile.apply` died before
   `git_commit`, no folder writes are persistent (atomic by checkpoint
   semantics). Re-running picks up cleanly.
2. If a provider API call partially succeeded (e.g., 3 of 5 labels applied
   before a rate limit), the next reconcile pass is idempotent and finishes
   the rest. `labels.apply` checks before writing.
3. If the failure is a hard provider outage, `metrics.emit_event` records
   it, and `schedule.daily` will retry. The skill never silently skips.

When the user manually edits the folder:

- Treat manual edits as authoritative on the next reconcile.
- Re-evaluate downstream gates; cascade if classification triggers.
- Log the manual edit with a clear "human override" decision entry.

When provider state and folder state disagree:

- Provider is the source of truth for *operational* state (current PR
  labels, current assignees).
- Folder is the source of truth for *team-decided* state (process
  definition, artifact lifecycle, gate policies).
- Reconcile is the negotiation: folder declares intent, provider state is
  observed, the diff is reconciled per the cascade rules.

## Interview semantics

The interview is **progressive** — demand-driven from a question bank
indexed by config key. The skill only asks what it needs to complete the
current intent. First-time bootstrap might ask 6 questions; later, when
the user adds a profile, only the new profile's questions are asked.

Inference precedes asking:
- Two independent signals agree → infer silently, note in summary.
- One signal → infer and confirm in one prompt.
- No signals → ask.

The question bank lives in
[`references/interview.md`](references/interview.md), keyed by config
field. Each entry: question text, options, inference hints, required-for
contexts.

## When in doubt

- Read the relevant reference rather than guessing.
- Stay inside the vocabulary; if a playbook needs a new action, add it to
  `references/vocabulary/actions.md` first.
- Prefer suggest-then-apply over silent automation.
- Preserve in-flight work over silent reverts.
- Log the decision; the user (and future you) will thank you.
