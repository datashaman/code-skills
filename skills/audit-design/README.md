# audit-design

**Design + WCAG accessibility audit** for web UIs. Built for
developers who can't eyeball visual or accessibility problems
(colorblindness, limited design experience, or just not designers).
Every accessibility finding is mapped to the relevant WCAG 2.1
success criterion.

For URLs, uses a live browser to render the page first — SPAs and
dynamically-injected content are handled correctly.

## When to use

Good prompts: *audit the design*, *WCAG audit*, *accessibility check*,
*design audit*, *check if this is shippable*.

Run it on:

- A **URL** you've deployed — rendered in a live browser, so SPAs
  and client-rendered apps work correctly.
- A **local directory** of HTML / CSS / JSX / TSX / Vue / Svelte
  source — static scan, no browser needed.
- **Both**, for the plan-vs-implementation case — mockup source +
  live deploy. The report surfaces divergences (e.g. contrast failures
  that crept in during implementation, Tailwind clusters that never
  got extracted, microstandards stripped in the build).

## What it checks

### WCAG 2.1 (mapped, pass/fail matrix)

| Criterion | Check |
|-----------|-------|
| 1.1.1 | `<img>` tags have `alt` |
| 1.2.2 | `<video>` has `<track>` captions |
| 1.3.1 / 2.4.6 | Heading hierarchy, no skipped levels |
| 1.3.5 | Form inputs declare `autocomplete` |
| 1.4.1 | State classes don't rely on color alone; no red+green-only pairs |
| 1.4.3 | Every `color` + `background` pair meets AA contrast (4.5:1 body, 3:1 large) |
| 1.4.4 | Viewport meta doesn't block zoom |
| 2.1.1 / 4.1.2 | No clickable `<div>` / `<div role="button">` without `<button>` |
| 2.4.1 | `<main>` landmark present |
| 2.4.2 | Non-empty `<title>` |
| 2.4.4 | No empty or generic ("click here") link text |
| 2.4.7 | `outline:none` paired with `:focus-visible` |
| 2.5.5 | Interactive target heights ≥ 44px |
| 3.1.1 | `<html lang>` set |
| 3.3.2 | Form inputs have `<label>` or `aria-label` |
| 4.1.1 | W3C HTML validator summary |

Criteria that need a live browser (1.4.10 Reflow, 1.4.12 Text
Spacing) are explicitly marked `not-checked` and flagged as requiring
a live-browser tool.

### Design hygiene (beyond WCAG)

- **Palette** — unique non-gray color count (flag > 12).
- **Typography** — font family count, blacklist (Papyrus, Comic
  Sans, Lobster, Impact), body font-size ≥ 16px, straight quotes in
  headings.
- **Spacing** — padding/margin values fit 4px or 8px scale,
  border-radius distribution (uniform bubbly vs. scale).
- **AI slop** — purple/violet/indigo gradients, 3-col feature
  grids, icons-in-colored-circles, centered-everything,
  colored-left-border cards, emoji in headings, generic hero copy
  ("Welcome to [X]", "Unlock the power of…").
- **Microstandards** — OpenGraph, Twitter Card, JSON-LD/schema.org,
  microdata, RDFa, canonical, theme-color. Suggests based on what
  the content looks like it represents.
- **Tailwind clusters** — flags elements with 12+ utility classes
  and suggests extraction into `@layer components` blocks via
  `@apply`.
- **Component health** — divitis (deep nested `<div>` chains,
  high div:semantic ratio), clickable `<div>`/`<span>`, inline
  `style=""` blobs, repeated DOM fingerprints that should be
  extracted into components, oversize JSX/TSX files (>300 lines),
  prop-heavy components (10+ props).
- **Hygiene** — `transition: all`, `<img>` missing dimensions,
  `@font-face` without `font-display: swap`.

### The W3C "shock" section

Final section of the report calls the W3C Nu HTML Checker and the
Jigsaw CSS validator and shows error counts + top repeating
messages. Most real sites carry 20–200 errors — useful wake-up
data. Disable with `--no-validate` offline.

## How it works

**URL mode:**
1. Navigate to the URL in a live browser (Chrome), take a screenshot.
2. Extract rendered HTML (`document.documentElement.outerHTML`) and all
   CSS rules (`document.styleSheets`) via JavaScript — CORS-blocked
   sheets are skipped.
3. Save to a temp directory and run the scanner against it.
4. Check browser console for JS errors.

**Path mode:**
1. Walk the directory for HTML/CSS/JSX/TSX/Vue/Svelte files.
2. Run the scanner directly against local files.

**Both modes then:**
1. **Parse CSS rules** with a lightweight brace tracker — handles
   nested `@media`, returns `(selector, body)` pairs for every rule.
2. **Per-check functions** inspect CSS + HTML and emit finding dicts.
3. **WCAG coverage** cross-references findings into the success-
   criteria matrix.
4. **Score** (0–100) with weighted deductions; colorblind-critical
   criteria (contrast, color signaling) carry the heaviest weight.

## Arguments

```
python3 scripts/scan_design.py --url   https://example.com
python3 scripts/scan_design.py --path  ./src
python3 scripts/scan_design.py --path  ./src --no-validate
```

## Limits

Be honest with the user about these — the skill says them in its
report too:

- Regex-based CSS parsing misses: runtime CSS variable resolution,
  inheritance chains, computed dark-mode colors, pre-compiled
  preprocessor output.
- CSS extraction via `document.styleSheets` skips cross-origin sheets
  blocked by CORS.
- W3C validators are strict — not every error is a real bug, but
  patterns repeating 5+ times usually are. Skipped in URL mode
  (`--no-validate`).
- Tailwind detection is heuristic (>40% shaped tokens); Bootstrap
  5 utilities can false-positive.

## Files in this folder

| File | Role |
|------|------|
| `SKILL.md` | Agent instructions: input scoping, per-section interpretation, scoring bands, plan-vs-impl mode |
| `scripts/scan_design.py` | The scanner — loads source, runs every check, emits one JSON object |

## Not in scope

- Design-system generation
- Mockup / variant generation
- Plan-mode critique of a plan-doc
- Functional QA (flows, regressions)
- Performance benchmarking (LCP, CLS, bundle size)
