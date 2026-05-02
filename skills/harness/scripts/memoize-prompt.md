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

---

You are doing the weekly memory hygiene pass against a snapshot of my Claude
Code memory. The repo you are running in is a sanitised mirror of `~/.claude/`
(see README.md). Memory lives in `memory/`, indexed by `memory/MEMORY.md`.

## Your task

1. **Run the deterministic pass.** If `scripts/memoize.sh` exists in the
   snapshot, run it with `--target=memory`. Otherwise, replicate its checks
   in-process: index sync (every `memory/*.md` listed in `MEMORY.md`, every
   entry points at a real file), frontmatter hygiene (every memory has
   `name`, `description`, `type`), stale citations (path-shaped tokens that
   resolve nowhere), possible duplicates (same `type`, lexically similar
   name/description).

2. **Read every memory.** For each file under `memory/`, read it and form a
   one-line gist. Group by `type`.

3. **Look for the things the script can't catch:**
   - **Conceptual duplicates** that don't share vocabulary — two `feedback`
     memories saying the same thing in different words.
   - **Outdated facts** — `project` memories citing deadlines, milestones,
     stakeholders that have moved on. Check the snapshot's `CLAUDE.md` and
     other context for currency.
   - **Conflicting guidance** — two memories that pull in opposite directions.
   - **Index drift** — entries in `MEMORY.md` whose one-line hook no longer
     reflects the file's body.

4. **Write the report** to `audits/memory/YYYY-MM-DD.md`. Structure:

   ```markdown
   # Memory consolidation — {{date}}

   ## TL;DR
   3-5 bullets — the highest-leverage merges, deletes, or rewrites.

   ## Deterministic findings
   Output of memoize.sh (or the equivalent in-process pass). Verbatim.

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
- Conservative on stale citations and outdated facts. False positives cost
  more than misses; the user reads every line of this report.
- Prefer specific over comprehensive. 3 merges I'll do > 30 I won't.
- If nothing material changed since last week, write a short report saying
  so. Don't pad.
- Concise output — the user reads in feedforward / sensors / GC vocabulary.

Report length target: 400-1000 words.
