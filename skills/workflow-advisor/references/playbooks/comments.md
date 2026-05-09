# Playbook: comments

Handles `comment.created` and `comment.edited` events for comments that
are NOT slash commands. (Slash commands have their own playbook,
`comment.slash_command.md`.)

Most non-command comments are no-op for the skill — humans talking to
each other, not to the skill. The skill stays out of the way.

## When the skill responds

The skill processes a non-command comment when:

- The comment **mentions the skill bot** by handle (e.g., `@workflow-advisor`)
  — treat as a question; respond if it can.
- The comment **edits a slash command** that was previously dispatched
  — re-evaluate; if the edited command differs from the original, dispatch
  again with a "command edited" note.
- The comment **resolves a review thread** mechanically — checked via
  GraphQL polling; updates `review_threads_unresolved` count for gates.

For typical conversation comments, the skill does nothing.

## Steps

### 1. Filter

If the comment is from the skill bot itself: ignore (self-loop guard).

If the comment is a slash command: route to `comment.slash_command`
playbook (this should already be done in the transport normalization
layer, but defensive check).

### 2. Mention detection

If the comment body contains `@workflow-advisor` (or whatever the bot's
configured handle is), treat as a question. Response patterns:

| Mention | Response |
|---|---|
| `@workflow-advisor status` | Equivalent to `/workflow-status`; dispatch and reply. |
| `@workflow-advisor what's blocking?` | Dispatch `gate.evaluate`; reply with failing gates. |
| `@workflow-advisor explain decision-15` | Dispatch `decision.lookup` for decision-15; reply with content. |
| `@workflow-advisor help` | Equivalent to `/workflow-help`. |
| Other questions | Best-effort: parse intent; if it maps to a known action, run it; otherwise reply "I'm not sure what you mean — try `/workflow-help`." |

### 3. Comment-edit handling

If `comment.edited` and the original comment was a slash command:
- Parse the new body.
- If new body is also a slash command:
  - If same command, same args: no-op.
  - If different: dispatch as new command, with reply "command was
    edited — re-running with new args".
- If new body is no longer a slash command: post a brief note: "the
  previously-dispatched command is unaffected by this edit."

### 4. Thread resolution detection

This actually happens via GraphQL polling, not via comment events.
Listed here for completeness:

- `schedule.daily` and on-demand `gate.evaluate` poll review threads
  via GraphQL.
- Update sidecar's `review_threads_unresolved` count.
- Re-evaluate `no_unresolved_review_threads` gate.

## Idempotency

Strongly idempotent. Mention-driven actions check current state before
acting.

## Failure modes

| Failure | Behavior |
|---|---|
| Mention parsing fails | Reply "I'm not sure what you mean"; no commit. |
| Best-effort intent fails | Reply with link to `/workflow-help`. |
| Self-mention loop (bot mentions itself) | Filter at step 1. |
