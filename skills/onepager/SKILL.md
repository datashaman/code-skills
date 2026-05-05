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

Four canonical patterns live alongside this file in `references/`. Read whichever matches the request before you start writing. Use them for interaction structure and Alpine patterns, not as mandatory visual themes.

- `references/catalogue.html` — the baseline demo pattern: search + filter + sort + detail pane + empty state. Start here for any list-with-details ask.
- `references/dashboard-with-tour.html` — KPI dashboard with a coaching-mark tour (spotlight overlay, `getBoundingClientRect` measurement, persisted "tour seen" via the `$persist` plugin).
- `references/slide-deck.html` — keyboard-driven slide deck with five layouts (cover, bullets, metric, quote, code), speaker notes, fullscreen mode.
- `references/streaming-ai.html` — simulated AI: thinking-step trace, word-by-word streaming reply, regenerate / edit / accept controls, `runId` to abort stale streams.

## Who you are talking to

Assume the person invoking this skill is a **non-developer stakeholder** — comfortable with computers and willing to open a file in a text editor or run `open foo.html`, but not interested in framework internals. They are using this to put a working interactive thing in front of a client, a stakeholder, a team, or an audience without booking a sprint with engineering.

What that means for you:

- **No jargon without translation.** If you mention `x-data`, `getter`, `$persist`, or a CDN, give a one-line "this means…" the first time. The teaching comments inside the HTML do this; your chat replies should too.
- **Default to "I'll just do it"** for technical implementation details. Do not ask whether to add getters, state fields, or event handlers. Do ask for creative direction when the user's request does not specify the desired style, tone, audience, or theme.
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
9. **No scattered assets.** Images, icons, textures, fonts, and data must either be embedded in the HTML (`data:` URLs, inline SVG, inline CSS, or inline arrays) or loaded from stable remote URLs/CDNs. Do not leave sibling `.png`, `.jpg`, `.svg`, `.json`, `.js`, `.css`, or screenshot files next to the onepager.
10. **Clean up after yourself.** If you generate images, screenshots, extracted data, browser snapshots, or temporary files while building or verifying the onepager, delete those temporary artifacts before delivery unless the user explicitly asked to keep them.

## Style and theme discovery

Before creating a onepager, identify whether the user has already specified the visual direction. Treat phrases like "investor memo", "retro arcade", "luxury retail", "internal dashboard", "zine", "playful", "minimal", "cyberpunk", "for kids", "for executives", or a linked/reference design as style direction.

If style direction is missing or too vague, interview the user briefly before writing the HTML. Ask one concise question with 3-5 concrete style options plus an invitation to name their own. Keep the options tailored to the topic rather than generic. For example:

> What style should this onepager use: analyst briefing, collector magazine, playful trading-card binder, auction-house premium, or something else?

When the user provides a style, honor it through layout, typography scale, color, imagery, density, copy tone, and interaction details. Do not impose a business/editorial theme unless the user chose it or the topic clearly calls for it.

If the user explicitly asks you to proceed without asking questions, choose a style that fits the audience and topic, then state the assumption in one sentence before building.

## Interaction and implementation conventions

- **Theme follows the interview.** Pick color, spacing, and typography from the user's chosen style. There is no universal palette or business default.
- **Fallback style only when needed.** If the user gives no style direction and cannot be reached, use a clear, readable neutral treatment with restrained colors and enough contrast. Keep it visually appropriate to the topic, not automatically corporate.
- **Spacing**: use a responsive page container appropriate to the chosen style. Dense dashboards, magazine explainers, pitch pages, and playful demos should not all share the same spacing system.
- **Typography**: make headings, labels, and body copy match the theme and audience. Preserve readability; do not use tiny text, negative tracking, or viewport-scaled font sizes.
- **Transitions**: prefer `x-transition` with explicit `enter`/`leave` classes for anything that appears/disappears. Motion should fit the style; keep it subtle for serious contexts and more expressive for playful ones.
- **Empty states**: every list and detail pane should have one. Write the empty-state copy in the selected tone.
- **Keyboard**: for presentations, wire `@keydown.arrow-right.window` / `arrow-left` / `space` on the root. For demos, at minimum support `Escape` to close modals/panes.

## Images and visual assets

Prefer CSS, inline SVG, or remote image URLs for decorative visuals. If an image must travel with the onepager, embed it as a `data:` URL inside the HTML so the delivered artifact remains one file.

When using generated bitmap images, either embed the final chosen image in the HTML or use a stable hosted URL if the environment provides one. Remove any intermediate image files, screenshots, masks, or rejected variants. The final working directory should contain the onepager HTML only, plus any unrelated files that existed before the task.

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
- [ ] No build artifacts, no sibling assets, no screenshot files, no browser snapshot folders, no `<link rel="stylesheet">` to local files, no `<script src="./...">`, and no local `<img src="./...">`.
- [ ] Opens cleanly with `open foo.html` — verify mentally that nothing assumes a server origin (no `fetch` to relative URLs, no module scripts).

## Graduation signals (mention these to the user when relevant)

If the demo grows past ~1500 lines, needs persistence, needs multiple pages, or starts wanting components, surface the upgrade path:
- `$persist` plugin for localStorage-backed state (one extra script tag — already in `references/dashboard-with-tour.html`).
- petite-vue or full Vue 3 from CDN for component decomposition without a build step.
- An actual backend + framework when the single-file format stops paying for itself.
