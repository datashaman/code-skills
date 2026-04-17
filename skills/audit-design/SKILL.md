---
name: audit-design
description: >
  Design and WCAG accessibility audit for web UIs. Accepts a URL or
  local directory. Uses a live browser for URLs — handles SPAs and
  dynamically-rendered content. Scores contrast, colour signalling,
  alt text, semantic structure, keyboard access, and other WCAG
  criteria, plus design hygiene (fonts, spacing, AI-slop patterns,
  component health). Returns a 0–100 score with actionable findings.
  Use when the user says "audit the design", "WCAG audit",
  "accessibility check", or "design review".
user-invocable: true
---

# Design Audit

Design and WCAG accessibility audit for web UIs. Every accessibility
finding is mapped to the relevant WCAG 2.1 success criterion. For
URLs, a live browser renders the page first — SPAs and
dynamically-injected content are handled correctly. Does not fix code
or generate mockups.

## Step 1: Scope the input

Ask the user for one of:

- **URL** — a deployed site you can reach over HTTPS
- **path** — a local directory of HTML/CSS/JSX/TSX/Vue/Svelte source
- **both** — the "plan vs implementation" case; audit the source
  directory AND the live deploy, then surface the divergences

## Step 2: Run the audit

### URL mode — browser-first

Use the chrome browser tools to render the page fully before scanning.

1. Create a new tab and navigate to the URL:

```
tabs_create_mcp → navigate(url=<url>)
```

2. Take a screenshot and show it to the user:

```
mcp__claude-in-chrome__computer { action: "screenshot" }
```
Then Read the screenshot file so it appears in the conversation.

3. Extract the rendered HTML and all CSS into a temp directory:

```javascript
// Get fully-rendered HTML (post JS execution)
document.documentElement.outerHTML

// Get all CSS rules from every loaded stylesheet
Array.from(document.styleSheets).map(sheet => {
  try { return Array.from(sheet.cssRules).map(r => r.cssText).join('\n') }
  catch(e) { return '' }
}).join('\n\n')
```

Save the HTML as `/tmp/audit_design/index.html` and the CSS as
`/tmp/audit_design/styles.css` (use a timestamp suffix if needed to
avoid collisions).

4. Check for JS errors on the page:

```
read_console_messages(onlyErrors=true)
```

Report any errors as additional findings at the end of the audit.

5. Run the scanner against the temp directory:

```bash
python3 "$SKILL_DIR/scripts/scan_design.py" --path /tmp/audit_design --no-validate
```

### Path mode — static scan

```bash
python3 "$SKILL_DIR/scripts/scan_design.py" --path <dir>
# add --no-validate to skip W3C calls (offline, or the API is flaky)
```

No browser needed for local files.

## Step 3: Read the report, section by section

### Contrast — the colorblind-critical one

`contrast[]` lists every rule where `color` + `background[-color]` in
the same block fails WCAG AA (4.5:1 body, 3:1 large/bold ≥18.66px).
These are the hardest to catch by eye and the ones that actually lock
users out. Report them verbatim with the ratio: `"body (#aaa on #fff)
= 2.32, needs 4.5"`.

Static parsing has a ceiling: it won't catch contrast pairs that
depend on inheritance, CSS variables that resolve at runtime, dark
mode, or dynamically-injected styles. Say so if the count looks
suspiciously low.

### Color signaling — AI's favorite accessibility bug

`color_signaling.findings[]` flags `.success` / `.error` / `.warning`
classes whose differentiation is color-only (no border, no
pseudo-element, no font-weight, no icon slot). **High severity** —
fix these even if contrast passes, because colorblind users and
grayscale-printed screenshots still need the info.

`color_signaling.red_green_pairs` is the count of `.success`/`.error`
rules using green and red respectively with no other cue. Red-green
deficiency affects ~8% of men. Recommend adding an icon, a prefix
label ("✓ Saved" / "⚠ Error"), or a distinct shape.

### Palette

`palette.unique_non_gray` counts distinct non-gray colors. Flag if
>12 — the palette has drifted. List the top 15 in `palette.sample`
so the user can see how wide it is.

### Typography

- `typography.blacklist_hits[]` — Papyrus/Comic Sans/Lobster/Impact
  hit. Call it out plainly.
- `typography.generic_hits[]` — Inter/Roboto/Open Sans/Poppins. Not
  broken, but a "chose the default" signal. Mention as polish only.
- `typography.unique_primary_families` — >3 means too many fonts.
- `typography.body_size_below_16px` — accessibility regression on
  mobile. iOS zooms forms when inputs are under 16px.
- `typography.straight_quote_headings` — count of headings using
  `"` / `'` instead of `"` `"` / `'` `'`. Polish only.

### Spacing

- `spacing.scale_coherence_pct` — % of padding/margin values that fit
  a 4px or 8px scale. <75% = ad-hoc spacing. Recommend codifying a
  scale in CSS variables or Tailwind theme.
- `spacing.radius_distinct_values` — if 1-2, the "uniform bubbly
  radius" tell (every element uses the same large radius). If >6,
  the radius is drifting — no hierarchy.

### AI slop — the "would a real designer ship this?" test

`ai_slop[]` returns pattern hits, each with severity. Relay them
verbatim — the patterns are the explanation. Common combos:

- Purple/violet/indigo gradient + 3-col grid + icons-in-circles +
  centered-everything = the SaaS starter template look. Call this
  out as one gestalt, not four separate bugs.
- Colored left-border cards + uniform bubbly radius = "AI UI kit"
  aesthetic.
- Placeholder copy matches ("Welcome to [X]", "Unlock the
  power of…") — rewrite with concrete, specific copy.

### Semantic HTML and microstandards

`semantics.findings[]` — heading hierarchy, landmarks, form labels,
alt text, lang. Treat high-severity items as bugs (screen reader
blockers), medium as polish.

`semantics.microstandards` — map of which standards the page
declares. Cross-reference with `semantics.suggestions[]` for
recommendations based on what the HTML *looks like* it represents:

- OpenGraph — always a win; controls social link previews.
- JSON-LD (schema.org) — only suggest when the content type fits
  (Article, Product, Event, Recipe, Breadcrumb). Don't push it on
  landing pages with no structured content.
- Microdata / RDFa — alternatives to JSON-LD. Don't recommend
  adding these if JSON-LD is already present.
- Canonical, theme-color, viewport — small but worth flagging if
  missing.

### Tailwind clusters → @apply extraction

`tailwind.detected` is a heuristic (>40% Tailwind-shaped tokens + 20+
total tokens). When it's true:

- `clusters_over_12` — elements with 12+ utility classes. These are
  extraction candidates.
- `worst_offenders[]` — lists the actual classes. Show 2-3 to the
  user so they can see what's happening.
- `apply_used` / `component_layer_used` — whether the CSS already
  has `@apply` or an `@layer components` block.

Recommend:

```css
@layer components {
  .card-feature {
    @apply bg-purple-500 text-white p-4 m-2 rounded-lg shadow-md
           flex items-center justify-between
           hover:bg-purple-600 transition duration-200
           border-2 border-purple-300;
  }
}
```

…and then HTML becomes `<div class="card-feature">`. The design
intent is in one place, instead of smeared across every occurrence.

Only suggest this if `clusters_over_12 >= 3` — two clusters aren't
worth the abstraction.

### Component health

`components.findings[]` — divitis, clickable divs, oversize JSX/TSX,
repeated DOM structures. Each carries severity + a fix note.

- `deepest_div_chain` ≥ 5 — the markup is doing layout with nested
  wrappers instead of CSS. Suggest flattening with grid/flex.
- `clickable_non_button` ≥ 1 — accessibility bug. `<button
  type="button">` is free and keyboard-accessible by default.
- `inline_style_blobs` ≥ 5 — inline styles bypass the design system;
  any design change must hunt each one. Move to classes.
- `extraction_candidates[]` — same tag+class signature repeated 4+
  times. **This is the "would benefit from a component" signal.**
  Cite the exact fingerprint and occurrence count when
  recommending extraction.
- `oversize_components[]` / `heavy_prop_components[]` — only
  populated in `--path` mode. >300 lines or 10+ props is a split
  signal.

### WCAG extras

`wcag_extras[]` carries the accessibility findings not captured by the
semantics / contrast / hygiene blocks. Each entry has a `wcag` tag:

- **2.4.2** missing or empty `<title>` — screen readers announce it
  first.
- **2.4.4** empty `<a>` or generic link text ("click here", "read
  more"). Screen reader users skim links in isolation.
- **1.2.2** `<video>` without `<track>` captions.
- **2.5.5** interactive elements with explicit `height` < 44px. Static
  parsing is best-effort (can't catch computed values) — flag the
  specific selectors so the user can verify.
- **1.3.5** form inputs missing `autocomplete`.

### WCAG coverage summary

`wcag_coverage` is a roll-up of every WCAG criterion the audit can
check, with status `pass` / `fail` / `not-checked`. Present it as a
compact matrix near the top of the report — users who asked for a
"WCAG audit" want to see the criteria list:

```
WCAG 2.1 COVERAGE (AA scope, plus 2.5.5 AAA)
  PASS  1.2.2  Captions
  PASS  1.3.5  Identify Input Purpose
  FAIL  1.1.1  Non-text Content (images have alt)          — 1 finding
  FAIL  1.3.1  Info and Relationships                       — 2 findings
  FAIL  1.4.1  Use of Color                                 — 3 findings
  FAIL  1.4.3  Contrast (Minimum) AA                        — 1 finding
  ...
  SKIP  1.4.10 Reflow                                       — requires live browser
  SKIP  1.4.12 Text Spacing                                 — requires live browser
```

Clearly mark the skipped criteria with a note that they need a live
browser to check. Don't imply the audit is complete WCAG AA
certification — it's a large static subset, not the full standard.

### Technical hygiene

`hygiene[]` — outline:none without `:focus-visible`, `transition:
all`, `user-scalable=no`, `<img>` missing dimensions (CLS cause),
`@font-face` without `font-display: swap` (FOIT). All simple, each
is a one-line fix. Report them with severity.

### W3C validation — the shock section

`validation.html` and `validation.css` are the W3C Nu Html Checker
and Jigsaw CSS validator summaries. Present this section at the END
of the report, separated clearly:

```
===============  W3C VALIDATION  ===============
HTML: 47 errors, 12 warnings (validator.nu)
  top recurring:
    - Element "div" not allowed as child of element "p"  (× 9)
    - Attribute "onclick" is not serializable as XML 1.0 (× 6)
    ...
CSS:  23 errors, 8 warnings (jigsaw.w3.org)
  top recurring:
    - Property "text-wrap" doesn't exist in CSS level 2.1 (× 4)
    ...
```

Most real-world sites have 20-200 validator errors. The user's
reaction ("how is that even possible?") is the point. Frame it
honestly: validator strictness is higher than browsers enforce, not
every error is a bug, but patterns that repeat 5+ times are usually
real.

If `validation.*.error` is present (network failure, timeout), say
so and move on — don't block the report on the validator.

## Step 4: Score and top fixes

`score` is a 0–100 integer. Report the band and the top 3
highest-severity fixes:

| Score   | Band         |
|---------|--------------|
| 90–100  | Clean        |
| 75–89   | Needs polish |
| 50–74   | Needs work   |
| 0–49    | Rough        |

Top 3 = the three highest-severity findings across all categories,
de-duplicated by rough theme. Each fix: what + where + how, one
sentence each. Don't list all findings — the user has the JSON if
they want depth.

## Plan vs implementation mode

If the user provides both a URL (implementation) and a path (plan /
source / mockup), run the scanner twice with the same
`--no-validate` setting, then present a **divergence summary**
before the per-category details:

1. Score delta (plan vs impl)
2. Findings that appear in **one but not the other** — grouped by
   category. Usually the interesting ones are:
   - impl has contrast failures the plan didn't (colors drifted
     during translation)
   - impl has more Tailwind clusters than the plan (no extraction
     happened)
   - plan has microstandards the impl stripped (JSON-LD, OG)
   - impl has AI-slop patterns the plan didn't
3. Common findings (both sides have them) — fix once, both sides
   benefit.

Keep the divergence summary tight: 5-10 lines. If you find nothing
meaningful, say so — "impl matches plan within audit tolerance."

## Not in scope

These need a live browser or a different kind of tool, and this skill
does not try to do them:

- Live visual rendering, screenshots, before/after diffs
- Design-system generation (palette, typography, DESIGN.md)
- Mockup / variant generation
- Plan-mode critique of a plan-doc
- Functional QA (user-flow bugs, regression testing)
- Performance benchmarking (LCP, CLS, bundle size)

If the user asks for any of these, tell them plainly that this skill
doesn't do it — don't invent workarounds.

## Known limits

Say these up front if asked how confident the audit is:

- **Regex-based CSS parsing** misses: CSS variables resolved at
  runtime, inherited contrast pairs, computed dark-mode colors,
  media-query nesting effects.
- **CSS extraction via `document.styleSheets`** may miss cross-origin
  stylesheets blocked by CORS. If `cssRules` throws, that stylesheet
  is skipped silently.
- **W3C validators** flag things browsers don't enforce. Treat
  repeated patterns as real, one-off errors as noise. Skipped in URL
  mode (we use `--no-validate` to avoid double-fetching).
- Tailwind detection is a heuristic (>40% shaped tokens). False
  positives on Bootstrap 5 or other utility frameworks are possible.

When a category would be unreliable, say so in the report rather
than emitting a falsely-confident number.
