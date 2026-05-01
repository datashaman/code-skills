# audit-ai-strategy

Audit a codebase's **AI playbook** through John Cutler's four-bucket lens: where AI is amplifying bad patterns, where it is supercharging good ones, where it unlocks workflows that have no pre-AI analogue, and whether the codebase makes context-reading easy enough for any of it to land.

## Source

This skill is built around the framing in:

**John Cutler**, *TBM 420: The AI Playbook Puzzle* — [https://cutlefish.substack.com/p/tbm-420-the-ai-playbook-puzzle](https://cutlefish.substack.com/p/tbm-420-the-ai-playbook-puzzle)

## The four buckets (60-second primer)

1. **Bad ideas amplified** — pre-AI patterns AI is now making faster/cheaper without anyone questioning whether the pattern was good. *Move: kill or rethink.*
2. **Good ideas supercharged** — already-healthy practices that compound when AI joins the loop. *Move: sharpen and invest.*
3. **Genuinely new possibilities** — workflows with no pre-AI analogue; only viable because AI is participating. *Move: invent the smallest reversible experiment.*
4. **The meta-skill (context-reading)** — whether the codebase, docs, and process make it easy to understand *why* a practice works here, not just *what*. Determines whether 1–3 land at all. *Move: document or restructure.*

The audit also sanity-checks against Cutler's three traps: **Amplify Bad**, **Identity Threat**, and **Avoiding It**.

## When to use

Good prompts: *audit AI strategy*, *evaluate our AI playbook*, *find AI opportunities*, *where can we think outside the box with AI*.

## Arguments


| Argument | Default        | Purpose                                                       |
| -------- | -------------- | ------------------------------------------------------------- |
| `path`   | whole repo     | Limit the audit to a subdirectory or subsystem                |
| `focus`  | general scan   | Specific concern — e.g. `executors`, `approval flow`, `docs`  |


## Files in this folder


| File        | Role                                                                                |
| ----------- | ----------------------------------------------------------------------------------- |
| `SKILL.md`  | Full agent instructions: surface map, four-bucket sort, traps, and report template  |
| `README.md` | This overview                                                                       |
| `reports/`  | Written audit reports (per project / date)                                          |


## Report output

Audits are written as:

`reports/<project-name>/YYYY-MM-DD-ai-strategy.md`

`<project-name>` should come from the audited repo's directory basename (or git remote when that's clearer). Do not place reports next to `SKILL.md`.

The report opens with the article link and a one-line primer per bucket so a reader who never opens the article still understands the framing.

## Requirements

- A repository to audit (the skill adapts gracefully if there is no AI surface yet — the audit becomes "where could AI participate")
- Bash + `grep` / `find` for surface mapping (see `SKILL.md`)

For the full step-by-step workflow, open **`SKILL.md`**.
