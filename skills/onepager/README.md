# onepager

**Single-file Alpine.js + Tailwind demos and presentations** — emailable, double-clickable, no build step. The skill writes one HTML file you can open straight in a browser.

Aimed at business and marketing users who need to put an interactive thing in front of a client, stakeholder, or colleague without booking engineering. The agent makes all edits; the user only opens the file in a browser to see the result.

## When to use

Good prompts: *make a demo*, *build a one-pager*, *prototype this*, *slide deck*, *interactive mockup*, *walkthrough*, *pitch*. Drop a topic ("a demo of our pricing tiers", "a Q1 review deck", "show what our agent does") and the skill produces the file.

Don't use for production apps, multi-page sites, or anything that needs a real backend, auth, or persistence beyond `localStorage`.

## Arguments

None. The skill takes a freeform topic in natural language.

**Usage:**
```
/onepager a demo of our pricing tiers
/onepager Q1 business review slide deck
/onepager a walkthrough of our onboarding flow with coaching marks
```

## What you get

One HTML file with:

- **Alpine.js 3** for reactivity (`x-data`, `x-model`, `x-for`, `x-show`, `x-transition`)
- **Tailwind Play CDN** for styling — no PostCSS pipeline
- **One root `x-data` block** holding all state, with getters as computed properties
- **Inline teaching comments** explaining each Alpine directive (the file is also a teaching artifact)
- An empty state for every list and detail pane, soft transitions on appear/disappear, and tabular numerics on number columns

## Files in this folder

| File          | Role                                                                                |
| ------------- | ----------------------------------------------------------------------------------- |
| `SKILL.md`    | Full agent instructions: hard rules, conventions, mode-specific patterns, checklist |
| `README.md`   | This overview                                                                       |
| `references/` | Four canonical patterns the skill references                                        |

## Reference patterns

| File                                  | Pattern                                                                                                |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `references/catalogue.html`           | Baseline list-with-details: search + filter + sort + detail pane + empty state                         |
| `references/dashboard-with-tour.html` | KPI dashboard with coaching-mark tour (spotlight overlay, `getBoundingClientRect`, `$persist` plugin)  |
| `references/slide-deck.html`          | Keyboard-driven slide deck — five layouts (cover, bullets, metric, quote, code), notes, fullscreen     |
| `references/streaming-ai.html`        | Simulated AI: thinking-step trace, word-by-word streaming reply, regenerate / edit / accept            |

## Graduation signals

The skill flags these to the user when the demo starts wanting them:

- `@alpinejs/persist` plugin for `localStorage`-backed state (one extra script tag).
- petite-vue or full Vue 3 from CDN for component decomposition without a build step.
- A real backend + framework once the single-file format stops paying for itself (~1500 line soft ceiling).
