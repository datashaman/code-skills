# Monthly Claude Code setup audit — agent prompt

Use this prompt as the `events[].data.message.content` when creating a remote routine
that audits a snapshot repo against the latest Anthropic releases and Claude Code
community best practice. The routine should clone the snapshot repo (e.g. `<you>/claude-setup`)
and have access to Bash, Read, Write, Edit, Glob, Grep, WebFetch, WebSearch, Agent.

---

You are auditing my Claude Code setup against the latest Anthropic releases and Claude Code community best practice. The repo you are running in is a sanitized mirror of `~/.claude/` — see README.md for the layout.

## Your task

1. **Inventory the current setup.** Read CLAUDE.md, settings.json, hooks/*.sh, commands/*.md, agents/*.md (if any), memory/MEMORY.md and the linked memory files, plugins/installed_plugins.json, and skills-installed.txt.

2. **Research what shipped in the last ~30 days.** Use WebFetch + WebSearch on:
   - https://platform.claude.com/docs/en/release-notes/overview
   - https://code.claude.com/docs/en/changelog
   - https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md
   - https://www.anthropic.com/news
   - https://www.anthropic.com/engineering

3. **Read the canonical Claude Code voices for new posts.** WebFetch each:
   - https://howborisusesclaudecode.com/
   - https://simonwillison.net/tags/claude-code/
   - https://blog.fsck.com/
   - https://ghuntley.com/
   - https://hamel.dev/blog/
   - https://steve-yegge.medium.com/

4. **Compare and propose deltas.** For each finding, decide: does this suggest a change to CLAUDE.md / settings.json / hooks / commands / agents / memory / plugins?

5. **Write the report** to `audits/YYYY-MM-DD-setup-audit.md`. Structure:

   ```markdown
   # Setup audit — {{date}}

   ## TL;DR
   3-5 bullets of the highest-leverage changes.

   ## What shipped (last ~30 days)
   ### Anthropic
   - Dated bullets, source-linked.
   ### Community
   - Dated bullets, source-linked.

   ## Gaps in current setup
   Per surface: what's missing or stale, with the specific change.

   ## Proposed deltas (ordered by leverage)
   - **What:** one-line summary
   - **Where:** exact file path
   - **Diff:** old → new
   - **Why:** which release/post motivates this, with link

   ## Skip-list
   Things that looked relevant but aren't worth doing.

   ## Sources
   ```

6. **Open a PR.** Branch `audit/YYYY-MM-DD`, commit `audit: monthly setup audit YYYY-MM-DD`, PR title `Setup audit — {{date}}`, PR body = TL;DR. Use `gh pr create`.

## Constraints

- DO NOT modify any tracked file outside `audits/`.
- If a recommendation involves a model migration (deprecation), call it URGENT in TL;DR.
- Prefer specific over comprehensive. 5 items I'll act on > 50 I won't.
- If nothing material shipped, write a short report saying so. Don't pad.
- Concise output — frame in feedforward / sensors / GC vocabulary if I use it.

Report length target: 800-1500 words.
