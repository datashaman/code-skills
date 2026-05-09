# Example: Reconcile Pass

Dry-run a provider payload:

```bash
workflow-advisor reconcile \
  --dry-run \
  --event-name pull_request \
  --event-payload .github/events/pr_opened.json
```

Typical dry-run output:

```text
Proposed changes
- sidecars to write: 1
- lifecycle updates: 1
- provider actions queued: 2
```

Apply mode writes only `.workflow/` state during the checkpointed reconcile
commit:

```bash
workflow-advisor reconcile \
  --event-name pull_request \
  --event-payload .github/events/pr_opened.json
```

Expected state changes:

```text
.workflow/artifacts/specs/<id>.yml
.workflow/lifecycle/active/pr-<number>.yml
.workflow/metrics/events.jsonl
.workflow/provider-actions/pending.jsonl
.workflow/state/processed_events.yml
```

Re-running the same event delivery id should produce:

```json
{"event": "reconcile.noop", "reason": "already_processed"}
```

This idempotency check prevents duplicate comments, repeated label mutations,
and duplicate decision-log entries for the same provider delivery.
