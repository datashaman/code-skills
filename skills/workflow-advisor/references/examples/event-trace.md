# Example: Event-to-Playbook Trace

Input provider event:

```text
GitHub pull_request opened
```

Normalized event:

```json
{
  "name": "pull_request.opened",
  "subject": {
    "type": "pr",
    "id": 42
  }
}
```

Dispatch route:

```text
references/playbooks/_dispatch.md
└── pull_request.opened -> references/playbooks/pull_request.opened.md
```

Reconcile phases:

```text
observe   -> read config, sidecars, current artifact state
classify  -> derive type/area/stage labels and artifact linkage
apply     -> write .workflow sidecars and queue provider actions
cascade   -> find dependent artifacts and preserve in-flight work
log       -> append decision log, metrics event, processed event id
```

Provider actions are explicit records under `.workflow/provider-actions/`.
With the default `provider_actions.mode: queue`, the skill never mutates
GitHub during reconcile; users can inspect and flush the queue separately.
