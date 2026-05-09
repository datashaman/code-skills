# Bootstrap

Bootstrap is what happens the first time the skill runs in a repo that
has no `.workflow/` folder. It produces the initial config, sidecars for
existing artifacts, provider config files, and label taxonomy. Bootstrap
is **multi-stage with explicit checkpoints** — the user confirms each
transition.

## When to use this reference

- A user invokes the skill in a repo with no `.workflow/` folder.
- A `repo.initialized` event fires.
- The user explicitly says "set up", "bootstrap", "configure for this repo".

## Pre-requirements

Before stage 3 (`.github/` config writing), the repo needs:
- `ANTHROPIC_API_KEY` as a repository secret (for Actions to call the API
  in reactive mode).
- Maintainer-level access to install Actions workflows.

The skill checks for and surfaces missing pre-requirements rather than
failing silently.

## The stages

Bootstrap has four stages. Each is a checkpoint the user confirms before
proceeding. Each produces one or more git commits, scoped per stage so
revert is clean.

### Stage 0: Detect and report

Run `scripts/helpers/detect.py` to gather:
- Provider (from `.git/config` remote)
- Language profile (file extensions, manifests)
- Existing CI (`.github/workflows/`)
- Branch model (analyze `git log --all --format='%D'`, branch names)
- Existing docs (scan `docs/`, look for spec-like or ADR-like patterns)
- Existing labels (provider API)
- CODEOWNERS
- Recent contributors (`git shortlog -sn --since=6.months`)

Build an inference report. Show it to the user. Offer:
- Proceed with inference-first interview (default)
- Skip inferences and ask everything explicitly

Do not write anything yet.

### Stage 1: Interview and `.workflow/` skeleton

Run the progressive interview (see `interview.md`). Aim for ~6 questions.

Interview questions in order:

1. **Profiles to enable.** Default-on: spec-driven, testability,
   observability. Default-off (prompted with framing): documentation,
   security, accessibility. Always-off-default: compliance.
2. **Branch model.** Confirm or correct inference.
3. **Approvals.** Min approvals + CODEOWNERS requirement.
4. **Roles.** Show inferred mappings; user accepts/edits/skips per role.
   Empty roles get `needs:role-assignment:{role}` and continue.
5. **Spec location.** Where do specs live? Confirm or move target.
6. **Spec linkage convention.** PR body line, commit trailer, or label.
7. **Transport.** How should events reach the skill? See
   `references/transports/` for full options. Default recommendation:
   `github_actions`. (Skip this question if the user already opted into
   on_demand_only.)

After interview:
- Write `.workflow/config.yml`.
- Write `.workflow/schema_version` (current schema integer).
- Write `.workflow/.gitignore` (decisions/, metrics/events.jsonl, state/).
- Create `.workflow/templates/` from skill defaults (one per artifact
  type per enabled profile).
- For each existing spec-like file detected: hash, write
  `.workflow/artifacts/specs/{id}.yml` sidecar with state inferred from
  front-matter or defaulted to `approved` (since they're already merged).
- Write `.workflow/README.md` explaining the folder.
- Run starter process tests for enabled profiles into `.workflow/tests/`.

Commit message: `workflow: bootstrap stage 1 — initialize .workflow/ folder`.

After commit, surface what's done and what's next. Pause for user to
review.

### Stage 2: Existing artifact moves and front-matter

If the user opted to move existing specs to a new location (e.g.,
`docs/specs/`), do this now. Two commits:

1. `git mv` operations only — preserves history under `git log --follow`.
   Commit: `workflow: bootstrap stage 2a — move specs to docs/specs/`.
2. Add front-matter to each moved file, syncing with sidecars. Commit:
   `workflow: bootstrap stage 2b — add front-matter to existing specs`.

Why two commits: `git blame` stays clean. The first commit shows only
moves; the second shows only the front-matter additions.

If no moves are needed, skip stage 2.

After commits, surface what's done and what's next.

### Stage 3: Provider config files

This is where the skill writes to `.github/`. Generate based on transport
choice:

- **github_actions:** Write `.github/workflows/workflow-advisor.yml`.
  Triggers and permissions per the foundations (read repo, write
  PRs/issues, contents). Includes `concurrency: cancel-in-progress: false`.
- **polling:** Write `.github/workflows/workflow-advisor-poll.yml` with
  cron trigger only.
- **gh_forward, self_hosted_webhook, github_app, on_demand_only:** No
  `.github/workflows/` file. Instead, write
  `.workflow/transport/{mode}.md` with setup instructions.

Always (regardless of transport):
- `.github/PULL_REQUEST_TEMPLATE.md` with `Spec:`, `Test plan:`,
  `Observability plan:` lines (for enabled profiles) and a lifecycle
  checklist.
- `.github/ISSUE_TEMPLATE/feature.yml` — structured form with
  audience-impact section.
- `.github/ISSUE_TEMPLATE/bug.yml`.

Show all proposed files as diffs before applying. Apply on confirmation.

Commit: `workflow: bootstrap stage 3 — provider config files`.

If the user has uncommitted changes in `.github/`, ask before merging
into them.

### Stage 4: GitHub API actions

Things that change the remote, not local git. Less reversible than commits.

1. **Snapshot existing labels** to `.workflow/state/label_snapshot.yml`.
   Keep this for rollback if anything fails midway.
2. **Existing label triage.** Show the user existing labels with three
   options:
   - Keep all (canonical labels co-exist with existing).
   - Alias the obvious ones (skill suggests; user confirms).
   - Per-label review.
3. **Create canonical labels.** Idempotently — skip any that already
   exist with matching colors/descriptions.
4. **Branch protection.** **Default: skip and recommend manual.**
   The skill suggests rules to add but does NOT push them. Tell the user:
   "Add this once you've validated the skill on a few real PRs; here's
   what to add." Branch protection is a one-way door; the skill should
   not be in the position of reverting it.

Commit (only if aliases were chosen): `workflow: bootstrap stage 4 —
label aliases`. Label creation itself is a remote operation; the
"commit" is purely the alias config addition.

### Bootstrap complete

Summarize what's done. Write a `bootstrap_followup.md` to `.workflow/`
listing:

- Roles still unassigned (with the gates they affect)
- Branch protection deferred
- Existing artifacts that don't have linked test plans / obs plans /
  audience docs (backfilling is optional)
- Whether `ANTHROPIC_API_KEY` was confirmed as a repo secret

The next time the skill runs, it reads `bootstrap_followup.md` and
surfaces unresolved items at the start of the interaction.

## Inference behavior

Two independent signals → infer silently, note in summary.
One signal → infer and confirm in the question.
No signals → ask without a default.

Examples:
- Branch model trunk-based: branches all merge to `main`, only short-lived
  feature branches in `git log` → confirm in summary, no question asked.
- Architect role: one contributor authored 80% of merges to main → "I'd
  guess marlin is the architect — confirm or change?"
- SRE role: no signal in git history (git can't tell who runs production)
  → ask without a default.

When uncertain, prefer asking. The interview is optimized for "ask less
than feels comfortable" but not less than safe.

## Profile activation defaults

Not every team should bootstrap with all seven profiles. The defaults are
calibrated for typical SDD-versant teams:

| Profile | Default | Why |
|---|---|---|
| spec-driven | on | The methodology this skill is built around |
| testability | on | Most teams want test plan as artifact and coverage gates |
| observability | on | Modern services treat this as table stakes |
| documentation | off (prompted) | Heavy — adds many roles and gates; prompt with value framing |
| security | off (prompted) | Heavy — adds gates that block on threat models |
| accessibility | off (prompted) | Only valuable for UI work |
| compliance | off (always opt-in) | Most teams don't need it; flips multiple defaults |

The interview shows all seven and recommends; user picks. Do not silently
default to "all on" or "minimum only."

## Empty-role behavior

Profiles activate even if their required roles are empty. The skill does
not block bootstrap on missing role assignments. Instead:

- Add `needs:role-assignment:{role}` to the global label set.
- When a gate would route to that role, fall back to `tech_lead`.
- Surface in `bootstrap_followup.md` and in `/workflow-status`.

This keeps momentum without losing visibility on the gap.

## Existing-label triage

Almost every real repo has pre-existing labels. The skill handles three
modes:

1. **Keep all.** No aliasing. Provider gets 47 new labels alongside the
   existing 12. Some duplication; team accepts.
2. **Alias the obvious ones.** Skill suggests:
   - `bug` → `type:bugfix`
   - `enhancement` → `type:feature`
   - `documentation` → `type:docs`
   - and any other clear matches based on label name patterns.
   User confirms or edits.
3. **Per-label review.** Walk the list one at a time. For low-volume,
   careful teams.

Aliases write to `config.labels.aliases`. Reading is bidirectional —
the skill treats `bug` as `type:bugfix` for gates; on writing, the skill
always uses the canonical name. Existing-aliased labels are not removed.

## What can go wrong

- **User abandons mid-interview.** Save partial config to
  `.workflow/.interview_in_progress.yml`; resume on next invocation.
  Don't pollute `config.yml` with half-answered fields.
- **Detect step misidentifies branch model.** Confirm in summary always;
  user can correct.
- **Existing specs have non-standard structure.** Sidecars get inferred
  state of `unknown`; skill prompts the user to confirm state per spec.
- **Provider API rate limits during stage 4.** Snapshot first; idempotent
  retries on next run pick up where left off.
- **`ANTHROPIC_API_KEY` not set.** Stage 3 still writes the workflow
  file; on first Actions run it'll fail with a clear message. Bootstrap
  warns at stage 3 if the secret isn't detected (via the GitHub API check
  for repo secrets).

## Idempotency

Re-running bootstrap on a repo that already has `.workflow/` is **not**
the same as bootstrap. It's the ongoing-mode reconcile path. The
detection step recognizes `.workflow/config.yml` and routes accordingly.

If a user truly wants to re-bootstrap (e.g., after a major reorganization
or migration), they can delete `.workflow/` and re-invoke. The skill
notices and treats it as a fresh bootstrap, but warns:
"You have existing `.workflow/` history in git. Are you sure you want to
re-bootstrap? Existing artifacts will be re-imported. The decision log
and metrics will be reset."
