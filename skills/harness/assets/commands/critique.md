---
description: Critique the most recent change before continuing — diff re-read + advisor() pass
---

A deliberate critique pass *between* steps, without waiting for Stop. Use mid-flow when an interpretation is about to harden into a chain of edits, or before declaring a milestone done.

Procedure:

1. **Re-read the change.** Run `git diff HEAD` (catches both staged and unstaged). If the working tree is clean (already committed, or no change yet), summarise the last few `Edit`/`Write` calls from the tool transcript instead.
2. **Critique it yourself first.** One paragraph: what does this change actually do, what could be wrong, what assumption is it leaning on?
3. **Call `advisor()`.** The advisor sees the full transcript — frame the question concretely. Examples: "Is the off-by-one in `foo()` actually a bug or am I misreading the loop?", "Does this migration handle the concurrent-write case I claimed it did?", "I rewrote X to use Y — is the boundary correct, or did I leak Y's concerns into a caller?"
4. **Report a punch list.** Under 200 words. What stands, what's shaky, what's the next concrete check.

If `$ARGUMENTS` is provided, treat it as a scope hint — `/critique migration safety`, `/critique the test I just wrote` — and focus the diff re-read and the advisor question on that.

Do not start new implementation work in this turn. The output of `/critique` is *findings*, not edits — the user (or the next turn) decides what to do about them.
