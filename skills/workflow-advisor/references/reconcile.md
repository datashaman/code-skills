# Reconcile Loop

The core engine. Every state-changing operation in the skill passes
through reconcile. Idempotent by construction: re-running on unchanged
state is a no-op. Each pass that writes produces at most one git commit
scoped to `.workflow/`, making changes reversible via `git revert`.

## Operations

The loop has five operations, executed in order:

1. **observe** — Scan repo + provider, build observed state.
2. **classify** — Categorize observed changes.
3. **apply** — Write sidecar updates idempotently.
4. **cascade** — Propagate effects per cascade rules with in-flight protection.
5. **log** — Append decision entries.

Each operation is implemented as a helper in `scripts/helpers/reconcile/`:
`observe.py`, `classify.py`, `apply.py`, `cascade.py`, `log.py`. Plus
`checkpoint.py` for the git-checkpoint wrapper.

## Entry points

The reconcile loop is invoked from:

- **CLI:** `workflow-advisor reconcile --event-name X --event-payload Y`
- **Slash commands:** `comment.respond_to_command` action ultimately calls reconcile.
- **Manual local invocation:** `/workflow-reconcile` slash, or chat ask.
- **Schedule events:** daily/weekly cron triggers reconcile.

All entry points pass through the same loop. They differ only in what
event context is provided.

## Observe

Build observed state for the relevant scope:

- For an event-driven invocation: only the items the event touches (one
  PR, one issue, one artifact). Bounded scope is what makes reconcile
  fast in CI.
- For a `schedule.daily` invocation: a broader scan — stale specs,
  drift detection, archive threshold checks.
- For a manual `workflow-advisor reconcile` with no event: full reconcile
  of all active lifecycle items. Most expensive; usually only run
  manually or after a bootstrap.

For each in-scope artifact:
- Compute current content hash.
- Read sidecar (if exists).
- Read provider state (current labels, current PR/issue state).
- Record the observation in memory; no writes yet.

## Classify

For each observation where state differs from sidecar:

1. **Mechanical signals first.** Run `scripts/helpers/classify.py` with
   diff size, sections changed, file paths. Produces a tentative
   classification (editorial / substantive / structural).
2. **LLM judgment if ambiguous.** When mechanical signals are split or
   close to a threshold, escalate to LLM judgment with the diff and
   classification rules. Subject to `config.ai_usage` policy.
3. **Human override.** If a `/reclassify` command was previously issued
   for this change, honor it.

The result is a classification with rationale, used by the next two
operations.

## Apply

Idempotent writes to `.workflow/` based on observations and
classifications.

For each artifact with a state change:
- Write/update sidecar with new hash, revision, last_observed timestamp.
- Sync front-matter if `front_matter_sync: true`.
- Update `last_change_classification` field.

For each lifecycle item (PR/issue) with a state-affecting observation:
- Update `lifecycle/active/{item}.yml` with current stage, gate
  evaluations, assigned reviewers.
- Compute target labels from current state (which `stage:*`, which
  `needs:*`, which `review:*`).
- Diff target labels vs observed labels.

No provider writes yet; just the folder.

## Cascade

For each artifact change classified as substantive or structural:

1. Look up the cascade rule for the change type from
   `config.cascade.{change_type}`.
2. For each affected dependent (impl_plan, open PRs, related ADRs):
   - Compute the desired action (revert state, archive, flag).
   - Check **in-flight protection**: if the dependent is mid-stage
     (e.g., PR has approvals already, review threads in progress) AND
     `cascade.preserve_in_flight: true` (default), prefer label-and-notify
     over revert.
3. Build a cascade plan as a list of actions to apply.
4. For each action in the plan:
   - Folder updates: append to apply queue.
   - Provider updates (label changes, comments): append to provider queue.

Then apply the cascade:
- Folder queue → write atomically with `apply` semantics.
- Provider queue → execute idempotently; failures retry on next reconcile.

## Log

Append entries to `.workflow/decisions/{YYYY-MM-DD}.md` for any
non-trivial decision:

- Classifications (especially LLM-judged or overridden).
- Cascade applications.
- In-flight conflicts and how they were resolved.
- Manual edits detected and integrated.
- Empty-role fallbacks invoked.
- Gate overrides.

Also emit structured events to `.workflow/metrics/events.jsonl`:

```jsonl
{"ts":"2026-05-09T10:23:00Z","event":"reconcile.cascade","trigger":"spec_amendment","spec_id":"0042","classification":"substantive","cascaded_to":["impl-plan/0042","pr/127"],"duration_ms":340}
```

The decisions log is for humans; the events stream is for metrics
computation.

## Checkpoint

The whole loop is wrapped in `scripts/helpers/reconcile/checkpoint.py`:

```python
def reconcile_with_checkpoint(intent, context):
    if working_tree_dirty(".workflow/"):
        bail("workflow folder has uncommitted changes; resolve first")
    
    observation = observe(context)
    classifications = classify(observation)
    apply_plan = compute_apply(observation, classifications)
    cascade_plan = compute_cascade(observation, classifications)
    
    if intent == "dry_run":
        return { "apply": apply_plan, "cascade": cascade_plan }
    
    if requires_user_confirmation(apply_plan, cascade_plan):
        present_diff_and_wait()
    
    apply(apply_plan)
    cascade_apply(cascade_plan)
    log(observation, classifications, apply_plan, cascade_plan)
    
    commit_message = build_commit_message(intent, context, apply_plan, cascade_plan)
    git_commit(".workflow/", commit_message)
```

Key properties:
- **Atomic per pass.** All folder writes for one reconcile land together
  or not at all. If checkpoint fails (rare; disk full, etc.), the apply
  is rolled back via `git checkout .workflow/`.
- **Dirty-tree bail.** If the user has uncommitted folder changes,
  reconcile stops rather than committing on top. Respects in-progress
  human edits.
- **Skill-only commits.** The commit only touches `.workflow/`. Never
  mixed with code changes.

## Concurrent edits

Two reconcile passes touching the same items are serialized by the
transport's concurrency control:

- **GitHub Actions:** `concurrency` group serializes per repo.
- **Local interactive:** the dirty-tree bail stops the second invocation
  if the first hasn't committed yet.

When two PRs both modify the same spec (concurrent feature branches):
- Each branch runs reconcile independently in its own context.
- On merge, git merges the sidecars; conflicts surface as standard merge
  conflicts.
- The merge conflict resolution is itself an event (the merge commit's
  `push` event); reconcile re-evaluates against the merged state.

## Drift detection

`schedule.daily` runs a drift detection pass:

- For each artifact: compare current hash to sidecar hash. If they
  differ but no change event was processed for it, treat as a manual
  edit and run classification.
- For each PR: compare current labels to sidecar's `target_labels`. If
  they differ, treat as a manual label change and re-evaluate gates.
- For each provider config (`.github/workflows/`): compare to what
  bootstrap would generate now. If drift, surface a "config drift
  detected" notice but do not auto-overwrite.

Drift is normal and often intentional. The skill notices and surfaces;
it does not silently revert.

## Failure modes

| Failure | Behavior |
|---|---|
| `observe` fails (provider API down) | Bail; emit metric; retry on next event. |
| `classify` fails on ambiguous diff | Default to substantive (safer error); log decision. |
| `apply` fails mid-write | Atomicity not guaranteed without rollback; checkpoint detects pending-change-without-commit and resets. |
| `cascade` fails on a single dependent | Continue with the rest; record the failed dependent for retry. |
| `log` fails | Continue silently; metrics stream is best-effort. |
| `git_commit` fails | Folder writes already happened; next reconcile sees them in working tree, bails on dirty tree, asks user to resolve. |

## Cost discipline

Reconcile is meant to run frequently (every event). Cost discipline
matters:

- **Bounded scope.** Event-driven reconciles only touch items the event
  references. Avoid full scans except on schedule.
- **Mechanical first.** `config.ai_usage.classification:
  mechanical_first_then_llm` means most reconciles never call the LLM.
- **Cache provider responses.** Within a single reconcile pass, provider
  state is fetched once and reused.
- **Idempotency check before write.** Every action checks "is this
  already true?" before invoking the API.

A typical PR event triggers a reconcile that finishes in a few seconds
with one or two GitHub API calls and zero LLM calls. Substantive spec
amendments are the expensive case (LLM classification + cascade), and
those are infrequent.
