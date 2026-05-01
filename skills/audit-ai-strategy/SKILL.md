---
name: audit-ai-strategy
description: |
  Audit a codebase's AI strategy through John Cutler's four-bucket lens: bad ideas
  amplified, good ideas supercharged, genuinely new possibilities, and the meta-skill
  of reading context. Identifies where AI is bolted onto broken patterns, where it
  amplifies what already works, and where the codebase could embrace workflows that
  only exist because AI is in the loop.
  Use when asked to "audit AI strategy", "evaluate our AI playbook", "find AI
  opportunities", or "where can we think outside the box with AI".
---

# AI Strategy Audit

Source: John Cutler, *TBM 420: The AI Playbook Puzzle* — [https://cutlefish.substack.com/p/tbm-420-the-ai-playbook-puzzle](https://cutlefish.substack.com/p/tbm-420-the-ai-playbook-puzzle)

The goal is not to grade AI usage. It is to surface the *playbook* the codebase is enacting — explicit or implicit — and judge whether each piece falls into one of Cutler's four buckets:

1. **Bad ideas amplified** — pre-AI patterns that AI is now accelerating without anyone questioning whether the pattern itself was good.
2. **Good ideas supercharged** — practices that were already healthy and become disproportionately stronger with AI in the loop.
3. **Genuinely new possibilities** — workflows with no historical precedent that *only* work because AI is participating.
4. **The meta-skill** — context-reading. Whether the codebase, docs, and process help an AI (and a human) understand *why* a practice works here, not just *what* the practice is.

The deliverable is an audit report that names each finding, tags it with the bucket it belongs to, and proposes a move — usually one of: kill, sharpen, invent, or document.

## Arguments

- `path` (optional): Subdirectory or subsystem to scope the audit to (default: entire repo).
- `focus` (optional): A specific concern — e.g. "executors", "approval flow", "PR review", "docs". Default: whole-codebase scan.

## Steps

### 1. Read the room before forming opinions

Before forming any judgement, gather context. Run these in parallel where possible.

- Read `README.md`, `CLAUDE.md`/`AGENTS.md`, `CONTRIBUTING.md`, and any top-level `CONTEXT.md`.
- List `docs/adr/` (or equivalent) and skim titles — ADRs encode the load-bearing decisions and reveal what the team has explicitly *chosen*, which is the strongest signal of intentional vs accidental playbook.
- Identify AI surface area:
  - LLM SDK imports (`anthropic`, `openai`, `@ai-sdk/*`, `Laravel\Ai\*`, `langchain`, etc.) — `grep -r` for SDK package names.
  - MCP servers, tools, agents, skills directories.
  - Prompt files, system prompts, agent definitions.
  - Executor / runner / orchestrator code.
  - Approval, gating, review, and human-in-the-loop surfaces.
  - Evals, traces, observability for AI calls.
- Identify the *humans-in-the-loop*: where does a person approve, review, edit, or reject AI output? Where do they not, and should they?
- Identify the *machines-in-the-loop*: where does AI feed AI? Are there feedback loops, or is each call a one-shot?

Write down the AI surface map before going further. If the codebase has *no* AI surface, the audit becomes "where could AI participate" rather than "is AI being used well" — adapt accordingly.

### 2. Sort findings into the four buckets

For each notable practice, ask the four diagnostic questions in order. The order matters — the first one is the trap most teams fall into.

#### Bucket 1 — Bad ideas amplified

Look for pre-AI patterns that AI is now making *worse* by making them faster or cheaper:

- **Static artefacts that should be living.** Long PRDs, frozen specs, or design docs that get generated up-front and then ignored. AI makes generating them trivial, which makes the rot invisible.
- **Gate-heavy workflows.** Multiple sequential approval steps, each with its own AI assist, where the *number* of gates is the actual bottleneck — not the work at each gate.
- **Siloed handoffs.** AI summaries between teams that obscure rather than reveal — "the model said X" replacing "I read it and here's what matters".
- **Mock-driven confidence.** AI-generated tests that pass against AI-generated mocks, providing no signal about real behaviour.
- **Volume as proxy for value.** Lots of AI-generated tickets, comments, or code review nits — measuring output instead of outcome.
- **Process LARP.** Ceremonies that exist because they used to exist, now sped up with AI, but no longer doing the work they were originally invented for.

Tag each finding `[BUCKET 1 — kill or rethink]`.

#### Bucket 2 — Good ideas supercharged

Look for healthy practices where AI compounds the value:

- **Living documents.** Docs, ADRs, or context files that are continuously refreshed and that the team actually reads. AI makes maintenance cheap enough to keep them honest.
- **Continuous co-design.** Humans and AI iterating on the same artefact, where each pass adds signal.
- **Prototyping as shared understanding.** Throwaway working code as a communication medium, not a deliverable.
- **Outcome-centric loops.** AI used to shorten the distance between "we hypothesised" and "we observed".
- **Small, reversible steps.** A codebase that supports many cheap experiments — AI thrives here, brittle codebases don't.
- **Strong feedback at the boundary.** Tests, types, lints, and runtime checks that catch AI mistakes the same way they catch human mistakes.

Tag each finding `[BUCKET 2 — sharpen and invest]`.

#### Bucket 3 — Genuinely new possibilities

This is the "outside the box" bucket — the article's central provocation. Look for workflows that have *no pre-AI analogue* and would be absurd to attempt without an AI in the loop. For each AI surface in the codebase, ask:

- **What if the AI never stopped working?** Background agents that triage issues, prune dead flags, refresh docs against code drift, propose ADR updates when code contradicts them.
- **What if context were continuously regenerated?** A `CONTEXT.md` or knowledge graph rebuilt from the actual code on every commit, not maintained by hand.
- **What if every artefact had a reverse?** AI that converts code → spec → tests → docs → code, used to detect drift between layers.
- **What if review were a conversation, not a gate?** PRs where the AI argues with itself from multiple personas (security, perf, simplicity) before a human ever looks.
- **What if onboarding were per-task, not per-person?** A new contributor (human or agent) gets a tailored brief generated from the exact files they're about to touch.
- **What if rejection were data?** Every rejected AI output captured as a training signal for the *prompts and tools*, not the model.
- **What if "the spec" were a running test suite plus a running prose explanation, kept in sync by an agent?**
- **What if domain language were enforced?** An agent that reads PRs and flags terminology drift against a glossary.
- **What if the executor were pluggable enough that competing models race the same task and a human picks the winner?**

Be deliberately weird here. The point is to provoke, not to ship. Tag each `[BUCKET 3 — invent]` and mark the level of speculation: *plausible / stretch / weird*.

#### Bucket 4 — The meta-skill

Judge whether the codebase makes context-reading easy or hard. This is the bucket that determines whether buckets 1–3 will land at all.

- **Why is captured, not just what.** ADRs, comments-where-non-obvious, commit messages that explain motivation.
- **Terminology is enforced.** Domain words mean one thing. The same concept does not appear under three names.
- **Entry points are signposted.** A new agent (or engineer) can answer "where do I start for X?" in under a minute.
- **Decisions are reversible-by-default.** When an approach gets rethought, the old reasoning is still findable, not silently overwritten.
- **The codebase teaches itself.** Reading the code in dependency order produces understanding, not confusion.

Tag each finding `[BUCKET 4 — document or restructure]`.

### 3. Watch for the three traps

Before writing the report, sanity-check the findings against Cutler's three traps. Each trap is a *failure mode of the audit itself*:

- **Amplify Bad** — Did you recommend adding AI to a process without questioning whether the process should exist? If yes, recategorise as Bucket 1.
- **Identity Threat** — Are you praising the team's existing practices to avoid suggesting reinvention? If your Bucket 3 list is empty or timid, you have probably flinched.
- **Avoiding It** — Are you giving generic AI advice ("add evals", "use a vector DB") without grounding it in *this* codebase's actual surface area? If yes, go back to step 1.

### 4. Write the report

Write to `{skill-base-dir}/reports/{project-name}/YYYY-MM-DD-ai-strategy.md`. Create directories if missing. Treat `reports/` as local output, not skill source.

Use this structure:

```markdown
# AI Strategy Audit

**Date**: [date] | **Scope**: [path or "whole repo"] | **Focus**: [focus or "general"]

**Framework**: John Cutler, *TBM 420: The AI Playbook Puzzle* — <https://cutlefish.substack.com/p/tbm-420-the-ai-playbook-puzzle>

### The four buckets (60-second primer)

1. **Bad ideas amplified** — pre-AI patterns AI is now making faster/cheaper without anyone asking if the pattern was good. *Move: kill or rethink.*
2. **Good ideas supercharged** — already-healthy practices that compound when AI joins the loop. *Move: sharpen and invest.*
3. **Genuinely new possibilities** — workflows with no pre-AI analogue; only viable because AI is participating. *Move: invent (smallest reversible experiment).*
4. **The meta-skill (context-reading)** — whether the codebase, docs, and process make it easy to understand *why* a practice works here, not just *what*. Determines whether 1–3 land at all. *Move: document or restructure.*

The three traps to avoid: **Amplify Bad** (adding AI to a broken process), **Identity Threat** (praising existing practice to dodge reinvention), **Avoiding It** (generic advice not grounded in this codebase).

## Executive Summary

[3–5 bullets. Lead with the most expensive bad-idea-amplified finding and the most exciting genuinely-new possibility. Resist the urge to lead with the safe Bucket 2 wins.]

## AI Surface Map

[Brief inventory: where AI lives in this codebase today. SDKs, agents, MCP tools, prompts, executors, approval surfaces. One line each.]

## Findings by Bucket

### Bucket 1 — Bad ideas amplified

| # | Finding | Evidence (file / pattern) | Move |
|---|---------|---------------------------|------|
| 1 | [name] | [path:line or pattern] | kill / rethink / replace with X |

### Bucket 2 — Good ideas supercharged

| # | Finding | Evidence | Move |
|---|---------|----------|------|
| 1 | [name] | [path / pattern] | sharpen / invest / extend to Y |

### Bucket 3 — Genuinely new possibilities

| # | Idea | Why it's only possible with AI | Speculation level | First experiment |
|---|------|-------------------------------|-------------------|-----------------|
| 1 | [name] | [reasoning] | plausible / stretch / weird | [smallest reversible step] |

### Bucket 4 — Meta-skill (context-readability)

| # | Finding | Evidence | Move |
|---|---------|----------|------|
| 1 | [name] | [path / gap] | document / restructure / enforce |

## Cross-cuts

### Danger zone — bad ideas that are about to be amplified
[Bucket 1 items where someone has *proposed* adding AI but hasn't yet. Cheapest wins.]

### Compounding bets
[Bucket 2 + Bucket 4 items that reinforce each other — sharpening one makes the other cheaper.]

### Outside-the-box shortlist
[Pick 2–3 Bucket 3 items the team could pilot in under a sprint. Name the smallest reversible experiment for each.]

## Identity check

[Cutler's "stay in motion while everything shifts" — name 1–2 places where the codebase or team appears to be performing AI adoption while internally resisting reinvention. Be specific, not preachy.]

## Recommendations

1. [Single highest-leverage move]
2. [Second]
3. [Third]
```

### 5. Present findings

- Tell the user where the report was saved.
- Open with a one-line link to the source article and a single sentence per bucket so a reader who never opens the article still understands the framing:
  > Framing: John Cutler's *TBM 420: The AI Playbook Puzzle* (<https://cutlefish.substack.com/p/tbm-420-the-ai-playbook-puzzle>) — (1) bad ideas amplified, (2) good ideas supercharged, (3) genuinely new possibilities, (4) the meta-skill of context-reading.
- Then lead with the executive summary and the **outside-the-box shortlist** — that is the part of the audit that earns its keep.
- Do not over-index on Bucket 2. It is the comfortable bucket and the least useful one to dwell on.
- Offer to deepen any single Bucket 3 idea into a concrete plan or to convert Bucket 1 findings into a kill-list PR.
