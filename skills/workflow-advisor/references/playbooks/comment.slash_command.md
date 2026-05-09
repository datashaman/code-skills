# Playbook: comment.slash_command

Dispatches slash commands posted as comments. This playbook is invoked
when the transport normalization layer detects a `/command` pattern in
a `comment.created` body and emits a `comment.slash_command` event.

## Inputs

- `event_payload` — `{ parent_type, parent_number, command, args, author, comment_id }`
- `config` — loaded `.workflow/config.yml`
- `lifecycle_sidecar` — for the parent PR or issue

## Steps

### 1. Validate command exists

Look up the command in `references/vocabulary/commands.md`. If it doesn't
exist:
- React with 👀 then 👎 on the comment (via provider API).
- Post a reply: "I don't recognize `/{command}`. Available commands:
  run `/workflow-help` to see the list filtered by your authority."
- Stop. No reconcile commit.

### 2. Authorize the actor

Call `role.check_authority(actor, command)`:
1. Resolve the command's required roles from `config.slash_commands.{command}`.
2. Resolve each required role's members.
3. Check if `actor` is in any required role's members.
4. Special cases:
   - `any` → always authorized.
   - `per_gate_override_policy` → look up the specific gate's override
     policy and re-check authority for that.
5. If the command is `read_only`-tagged and the actor's role is also
   `read_only` (e.g., auditor), allow.

If unauthorized:
- React 👀 then 👎.
- Post a reply quoting the configured authority list: "This command
  requires {role}. You can request someone with that role to run it,
  or use `/workflow-help` to see what you can run."
- Log to decision log: "unauthorized command attempt: {actor} tried
  {command}".
- Stop.

### 3. Validate command arguments

Each command in the vocabulary declares its expected args. Parse and
validate:
- Required args missing → reply with usage hint, stop.
- Unknown flags → reply with usage hint, stop.
- Args reference nonexistent items (e.g., `/supersede #99` where #99
  doesn't exist) → reply with the reason, stop.

### 4. Acknowledge the command

React 👀 on the comment to signal "received". This is fast (one API call)
and gives the user immediate feedback even if dispatch is slow.

### 5. Dispatch to the command's actions

Each command in the vocabulary maps to one or more actions. Look up the
mapping and call them in order.

Examples:

| Command | Actions dispatched |
|---|---|
| `/approve-spec [id?]` | `artifact.update_state(spec, approved)` → `cascade.compute` if cascade rules apply |
| `/sign-off` | `gate.evaluate(pr)` → `stage.set(merge-ready)` if pass else `comment.post` with reasons |
| `/reclassify [class]` | `artifact.classify_change(override=class)` → `cascade.compute` |
| `/supersede #N` | `artifact.supersede(old=#N, new=current)` |
| `/override-gate [name]` | `gate.override(name, reason)` |
| `/skip-stage [stage]` | `stage.skip(stage, reason)` + loud `decision.append` |
| `/post-release-validated` | `release.validated` event → `stage.set(validated)` |
| `/rollback-release [tag]` | `release.rolled_back` event → cascade |
| `/workflow-status` | `gate.evaluate` → `comment.post` |
| `/workflow-reconcile` | `reconcile.apply` scoped to current item |
| `/workflow-help` | `role.check_authority(actor, *all_commands)` → `comment.post` |
| `/workflow-explain [decision-id]` | `decision.lookup` → `comment.post` |
| `/assign-role [role] [@user]` | write to config → `repo.config_changed` event |

The dispatch is wrapped in the standard reconcile checkpoint. All
folder writes from the command land in one git commit.

### 6. Respond with structured output

Use `comment.respond_to_command(event, result)` to post a reply that:
- Confirms what was done (or that nothing changed if idempotent).
- Lists any side effects (labels added/removed, stage moved, cascade
  triggered).
- Links to the decision log entry for traceability.
- Reacts 👍 on the original comment (replacing 👀).

Example response for `/approve-spec`:

```
Spec `0042-user-auth` marked approved.

✓ State: in-review → approved
✓ Linked impl-plan `0042` advanced to in-review
✓ PR #127 advanced from stage:spec to stage:impl-plan

Decision: .workflow/decisions/2026-05-09.md#decision-12
```

If the command failed (e.g., gate evaluation didn't pass for `/sign-off`):

```
Cannot sign off — these gates are still failing:

- ✗ tests_pass — last CI run failed (link)
- ✗ no_unresolved_review_threads — 2 threads open (#thread-1, #thread-2)

Resolve these and run `/sign-off` again.
```

React 👎 on the original comment to signal "ack but not applied".

### 7. Emit metrics and log

`metrics.emit_event` records the command, actor, authorization result,
dispatch outcome, duration. This feeds metrics on slash-command usage
and friction (rejected commands, unauthorized attempts).

`decision.append` for any non-trivial command (anything that overrode a
gate, skipped a stage, or had cross-cutting cascade).

## Idempotency

Commands are idempotent where the underlying actions are. Calling
`/approve-spec` twice on an already-approved spec:
- Second call detects no state change.
- Reacts 👍 with reply "Already approved (no change)".
- No reconcile commit.

Commands that aren't naturally idempotent (e.g., `/skip-stage` posted
twice with different reasons) treat the second as superseding:
- Decision log records both with a "supersedes" link.
- Net effect is the second's reason taking precedence.

## Authorization edge cases

### Empty role authorizing
`/approve-spec` requires `architect`. The architect role has no members.
The fallback rule: `tech_lead` can approve when `architect` is empty,
and the response notes:

```
Spec approved (architect role empty — tech_lead authorization used per
fallback rule). Assign someone to architect to lock this down.
```

### External-member commands
Commands cannot be dispatched by external members (no GitHub identity).
A maintainer can record an external approval via `/attest` (compliance
profile) which writes a recorded attestation but does not dispatch the
underlying action.

### Override loops
`/override-gate` or `/skip-stage` override the safety net the skill
provides. They're allowed but heavily logged:
- Decision entry includes the actor, reason, and what would have blocked.
- `metrics.emit_event` flags as `override_used: true`.
- `/workflow-status` surfaces recent overrides on the PR.

A team that uses overrides constantly is signaling that their gates are
miscalibrated. Reports surface the override rate per gate so the team
can adjust config.

## Failure modes

| Failure | Behavior |
|---|---|
| Command parser fails (malformed args) | Reply with usage hint, no commit. |
| Authorization API call fails | React 👎, reply "couldn't verify authority — try again", no commit. Retry on next reconcile. |
| Action helper crashes | Checkpoint rolls back; reply "command failed; nothing applied — see logs". |
| Reply post fails | Action did succeed but reply didn't; next reconcile detects the gap and posts the missing reply. |

## See also

- `references/vocabulary/commands.md` — full command list with auth and
  dispatches.
- `references/vocabulary/actions.md` — what each action does.
- `references/playbooks/comments.md` — for non-command comments.
