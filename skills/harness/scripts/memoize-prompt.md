# Weekly memory consolidation — agent prompt

Use this prompt as the `events[].data.message.content` when creating a remote
routine that consolidates `~/.claude/projects/<slug>/memory/`. The routine
clones the snapshot repo (e.g. `<you>/claude-setup`) and needs Bash, Read,
Write, Edit, Glob, Grep, Agent.

Suggested config:
- cron: `0 6 * * 0` (Sunday 06:00 UTC)
- model: `claude-opus-4-7`
- tools: Bash, Read, Write, Edit, Glob, Grep, Agent
- sources: the user's snapshot repo (must exist — run `harness snapshot` first)

## Scope note

The local `memoize.sh` script does four checks: index sync, frontmatter
hygiene, stale citations, and lexical duplicates. Of these, **stale
citations cannot run remotely** — the search roots (`~/.claude/projects`,
`~/Projects`) are local-machine state that the snapshot repo does not
mirror. The remote routine focuses on the **conceptual** drift the local
script can't see (semantic duplicates, outdated facts, conflicts), and
re-runs the cheap structural checks (index, frontmatter) directly against
the snapshot.

---

You are doing the weekly memory hygiene pass against a snapshot of my Claude
Code memory. The repo you are running in is a sanitised mirror of `~/.claude/`
(see README.md). Memory lives in `memory/`, indexed by `memory/MEMORY.md`.
The snapshot does **not** contain harness scripts or local search roots.

## Your task

1. **Structural checks (in-process).** For files under `memory/`, applying
   `memory/MEMORY.md` as the index:
   - **Index sync** — every `memory/*.md` whose filename does NOT start with
     `_` and is NOT `MEMORY.md` itself must appear as an entry in
     `MEMORY.md`. Every `MEMORY.md` entry must point at a real file.
   - **Frontmatter hygiene** — every memory file must start with a `---`
     YAML frontmatter block containing non-empty `name`, `description`,
     and `type` fields.

2. **Read every memory.** For each `memory/*.md` file (skipping `MEMORY.md`
   and any `_*.md` such as the consolidation report itself), read it and
   form a one-line gist. Group by `type`.

3. **Conceptual checks the structural pass can't catch:**
   - **Conceptual duplicates** that don't share vocabulary — two `feedback`
     memories saying the same thing in different words.
   - **Outdated facts** — `project` memories citing deadlines, milestones,
     stakeholders that have moved on. Cross-check against the snapshot's
     `CLAUDE.md` and other context for currency.
   - **Conflicting guidance** — two memories that pull in opposite
     directions.
   - **Index drift** — entries in `MEMORY.md` whose one-line hook no
     longer reflects the file's body.

4. **Write the report** to `audits/memory/YYYY-MM-DD.md`. Structure:

   ```markdown
   # Memory consolidation — {{date}}

   ## TL;DR
   3-5 bullets — the highest-leverage merges, deletes, or rewrites.

   ## Structural findings
   Index sync + frontmatter hygiene issues. Per-file bullets.

   ## Conceptual duplicates
   Pairs of memories that say the same thing differently. Propose a merge
   target and the surviving content.

   ## Outdated facts
   Memories whose body cites stale state. Quote the line, suggest the edit.

   ## Conflicts
   Memories pulling in opposite directions. Surface the contradiction; do
   not resolve it unilaterally.

   ## Proposed edits (ordered by leverage)
   - **What:** one-line summary
   - **Where:** `memory/<file>.md`
   - **Diff:** old → new (or "merge X into Y, delete X")
   - **Why:** the signal in the body that motivates this

   ## Skip-list
   Things that looked relevant but aren't worth doing this week.
   ```

5. **Open a PR.** Branch `memoize/YYYY-MM-DD`, commit
   `memoize: weekly memory consolidation YYYY-MM-DD`, PR title
   `Memory consolidation — {{date}}`, PR body = TL;DR. Use `gh pr create`.

## Constraints

- DO NOT modify any tracked file outside `audits/memory/`. The user reviews
  proposed edits and applies them locally — the routine never edits memory.
- Skip files whose names start with `_` (e.g. `_memoize-report.md` if it
  ever lands in the snapshot) and `MEMORY.md` when iterating "every memory".
- Stale-citation analysis is local-only; do not attempt a snapshot
  equivalent — false positives drown the signal.
- Conservative on outdated facts. False positives cost more than misses;
  the user reads every line of this report.
- Prefer specific over comprehensive. 3 merges I'll do > 30 I won't.
- If nothing material changed since last week, write a short report saying
  so. Don't pad.
- Concise output — the user reads in feedforward / sensors / GC vocabulary.

Report length target: 400-1000 words.
