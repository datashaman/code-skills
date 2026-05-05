---
name: onepager
description: |
  Generate a self-contained single-file HTML demo or presentation
  using Alpine.js + Tailwind via CDN. Emailable, double-clickable, no
  build step or server. Use when the user asks for a demo, prototype,
  slide deck, walkthrough, pitch, or interactive mockup. Triggers on
  phrases like "make a demo", "build a one-pager", "prototype this",
  "presentation/slides", "single-file HTML", or "no build step".
user-invocable: true
---

# Onepager — single-file demo & presentation generator

Produce one HTML file. No `package.json`, no bundler, no server, no separate JS/CSS files. The output must run by double-clicking it (or `open file.html`) with only an internet connection for the CDN scripts.

## Reference examples

Four canonical patterns live alongside this file in `references/`. Read whichever matches the request before you start writing — they encode all the conventions below as working code.

- `references/catalogue.html` — the baseline demo pattern: search + filter + sort + detail pane + empty state. Start here for any list-with-details ask.
- `references/dashboard-with-tour.html` — KPI dashboard with a coaching-mark tour (spotlight overlay, `getBoundingClientRect` measurement, persisted "tour seen" via the `$persist` plugin).
- `references/slide-deck.html` — keyboard-driven slide deck with five layouts (cover, bullets, metric, quote, code), speaker notes, fullscreen mode.
- `references/streaming-ai.html` — simulated AI: thinking-step trace, word-by-word streaming reply, regenerate / edit / accept controls, `runId` to abort stale streams.

## Who you are talking to

Assume the person invoking this skill is a **business or marketing user** — comfortable with computers and willing to open a file in a text editor or run `open foo.html`, but **not a developer**. They are using this to put a working interactive thing in front of a client, a stakeholder, or a colleague — without booking a sprint with engineering.

What that means for you:

- **No jargon without translation.** If you mention `x-data`, `getter`, `$persist`, or a CDN, give a one-line "this means…" the first time. The teaching comments inside the HTML do this; your chat replies should too.
- **Default to "I'll just do it"** for anything that needs a code change. Don't ask "do you want me to add a getter for the filtered list?" — they don't know. Decide and do; describe what you did in plain language afterwards.
- **You make the edits, not them.** Never tell the user to open the file and change a line, replace an array, or paste a snippet. If something needs changing, change it yourself with the editing tools. The user's only interaction with the file should be opening it in a browser to look at the result.
- **Talk about outcomes, not implementations.** "I added a search box that filters as you type" beats "I bound `x-model` to a reactive `search` property and added a `filteredItems` getter." Reserve the second form for inline code comments.
- **Don't suggest dev workflow changes.** No "add a test", "run the linter", "set up CI", "convert to TypeScript". They are not running any of that.
- **Be generous with realistic sample data.** They'll often hand you a topic ("a demo of our pricing tiers") rather than data. Invent plausible content; they will replace it (by asking you, not by editing). Aim for content that looks like a real customer's, not lorem ipsum.
- **When you need their content, ask in plain English.** "Got the pricing tiers and what each includes? Paste them in and I'll wire them in." Not "provide the `items` array in JSON."

This is not a reason to dumb anything down. The output is still a properly built, idiomatic Alpine app — it just needs to *land* without a developer in the loop.

## When to use this skill

Use it for:
- **Demos / prototypes** — interactive UI to show an idea (catalogue, dashboard, form flow, data explorer).
- **Presentations / slide decks** — keyboard-navigable slides with transitions, speaker notes, progress.
- **Walkthroughs / tutorials** — step-by-step guided UI, often with a "next" button advancing state.
- **Pitches / explainers** — landing-page-style narrative scrolls with reactive bits.

Do **not** use it for:
- Anything needing real persistence, auth, server-side logic, or a real backend.
- Multi-page apps, routing-heavy UIs, or anything where one file becomes unwieldy (>~1500 lines is the soft ceiling — flag this to the user).
- Production apps. This is a starter, not a destination.

## Hard rules

1. **One file.** All markup, state, styles, and data live in the single `.html` you output. Never split.
2. **CDN only, no install.** Use these exact tags in `<head>`:
   ```html
   <script src="https://cdn.tailwindcss.com"></script>
   <script defer src="https://unpkg.com/alpinejs@3.14.1/dist/cdn.min.js"></script>
   ```
   `defer` on Alpine is required.
3. **One root `x-data` block** holds the entire app's reactive state. Nested `x-data` only when scoping is genuinely needed (e.g. a repeated component with local state).
4. **Use getters as computed properties** — `get filteredItems()` rather than recomputing in templates. Alpine re-runs them automatically.
5. **`x-cloak` on the root** plus `[x-cloak]{display:none!important}` in a `<style>` to prevent the un-hydrated flash.
6. **Tabular numerics** (`tabular-nums`) on price/count columns. Small detail, big polish.
7. **Comment the Alpine concepts inline** the way `references/catalogue.html` does (`x-model is two-way binding`, `x-for renders one element per array item`, etc.). The output is a teaching artifact as much as a working demo.
8. **No emojis** in the output unless the user asked for them.

## Conventions to follow

- **Tailwind palette**: default to `slate` for neutrals, white cards on `bg-slate-50`, `border-slate-200/300`, `text-slate-500/700/900`. Avoid gradient soup and rainbow accents — keep it editorial.
- **Spacing**: `mx-auto max-w-6xl px-6 py-10` for the page container is a sensible default.
- **Typography**: `tracking-tight` on headings, `font-semibold` (not `font-bold`), `antialiased` on body.
- **Transitions**: prefer `x-transition` with explicit `enter`/`leave` classes for anything that appears/disappears. Defaults are too snappy.
- **Empty states**: every list and detail pane should have one. Dashed border, muted text, helpful sentence.
- **Keyboard**: for presentations, wire `@keydown.arrow-right.window` / `arrow-left` / `space` on the root. For demos, at minimum support `Escape` to close modals/panes.

## Presentation-mode specifics

When the request is a slide deck:
- State shape: `{ slide: 0, slides: [...] }` where each slide is `{ title, body, notes? }` or a discriminated `{ type: 'cover' | 'bullets' | 'image' | 'code', ... }`.
- Render exactly one slide at a time via `x-show` + `x-transition` keyed on `slide` index.
- Show `slide + 1 / slides.length` in a corner.
- Bind keys: `→`/`Space` advances, `←` retreats, `Home`/`End` jump, `f` toggles a `fullscreen` boolean that hides chrome.
- Speaker notes hidden by default, toggleable with `n`.
- Progress bar at the top: `width: ((slide+1) / slides.length * 100) + '%'`.

## Demo-mode specifics

When the request is an interactive demo:
- Sample data goes in an `items` (or domain-appropriate) array at the top of `x-data`. Provide 12–20 realistic-looking entries — enough to make filter/sort feel meaningful, not so many the file bloats.
- Always include: a search/filter control, a sort control, a list, a detail pane (or modal), and an empty state. This is the load-bearing pattern from `references/catalogue.html` and it scales to most demo asks.
- Selection state lives at the root (`selected: null`), not inside the loop.

## Offer an onboarding flow

After delivering a non-trivial demo, **offer to add a coaching-mark / onboarding tour** as a follow-up. Don't add it unprompted — surface it as a one-line question: *"Want me to wire up a coaching-mark tour for this?"*. Most demos benefit, but unsolicited additions inflate scope.

When the user accepts, the pattern from `references/dashboard-with-tour.html` is the reference:

- **State**: `tour: { active: false, step: 0 }` plus a `tourSteps` array of `{ target, title, body, placement, autoSelect? }` entries. `target` matches a `data-tour="..."` attribute on a real DOM element. `placement` is `'top' | 'bottom' | 'left' | 'right'`. `autoSelect` is optional — opens a drawer / picks an item before measuring, so the spotlight can land on dynamically-revealed UI.
- **Spotlight**: a single fixed-position div with `box-shadow: 0 0 0 9999px rgba(15, 23, 42, 0.72)` and no background. The shadow dims everything outside the box; transitions on `top/left/width/height` animate between targets cheaply. Crisper than an SVG mask.
- **Coaching card**: another fixed div positioned next to the spotlight using the step's `placement`. Title, body, step counter (`n / total`), Back / Next / Skip controls.
- **Measurement**: `measureTarget()` calls `getBoundingClientRect()` on the active step's `data-tour` element, with `scrollIntoView({ block: 'center', behavior: 'smooth' })` first. Re-measure on `resize` and `scroll` so the spotlight tracks. Use `$nextTick` after step changes so DOM updates from `autoSelect` settle before measuring.
- **Keyboard**: `Escape` ends the tour, `ArrowRight` / `Enter` advances, `ArrowLeft` retreats.
- **Annotation in HTML**: sprinkle `data-tour="some-id"` attributes on the elements steps point at. Identifiers should be lowercase-kebab and unique. Bind dynamically with `:data-tour="'item-' + i.id"` when targeting list rows.
- **Don't block clicks** on the spotlit element — `pointer-events: none` on the spotlight, with a transparent click-trap overlay behind it that catches outside clicks and ends the tour.

For lighter onboarding (one-shot welcome panels, dismissible tooltips), a single `<div x-show="!seenWelcome">` with a localStorage check via `$persist` is enough — don't reach for the full tour machinery.

## Output checklist (run mentally before handing back)

- [ ] Doctype, lang, viewport, charset, title set.
- [ ] Tailwind + Alpine CDN tags in `<head>`, Alpine has `defer`.
- [ ] `x-cloak` style block present and applied to root.
- [ ] All reactive state in one `x-data` (or justified nested ones).
- [ ] Getters used for derived data, not inline computations.
- [ ] At least one `x-transition` somewhere — UIs without motion feel dead.
- [ ] Empty state for every list / detail region.
- [ ] Tasteful comments explaining the Alpine directives, matching `references/catalogue.html`'s tone.
- [ ] No build artifacts, no `<link rel="stylesheet">` to local files, no `<script src="./...">`.
- [ ] Opens cleanly with `open foo.html` — verify mentally that nothing assumes a server origin (no `fetch` to relative URLs, no module scripts).

## Graduation signals (mention these to the user when relevant)

If the demo grows past ~1500 lines, needs persistence, needs multiple pages, or starts wanting components, surface the upgrade path:
- `$persist` plugin for localStorage-backed state (one extra script tag — already in `references/dashboard-with-tour.html`).
- petite-vue or full Vue 3 from CDN for component decomposition without a build step.
- An actual backend + framework when the single-file format stops paying for itself.
