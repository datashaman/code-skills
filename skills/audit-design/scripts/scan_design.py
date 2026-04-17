#!/usr/bin/env python3
"""
Static design audit scanner. Accepts a local path (HTML/CSS/JSX) or a
URL, extracts inline + linked CSS, and emits a single JSON object with
findings across eight categories:

  contrast        — WCAG ratio pairs pulled from same-rule color+background
  color_signaling — semantic state classes (success/error/warning) that
                    rely on color alone, or on red+green pairings
  palette         — unique non-gray color count + list
  typography      — font families, blacklist hits, body size checks,
                    straight quotes in content
  spacing         — padding/margin scale coherence, border-radius spread
  ai_slop         — the blacklisted patterns a colorblind developer can't
                    eyeball: purple/violet gradients, 3-col feature grids,
                    icons in colored circles, centered everything,
                    colored left-border cards, emoji in headings,
                    placeholder copy
  semantics       — heading hierarchy, landmark regions, form labels,
                    relevant microstandards (OpenGraph, JSON-LD,
                    microdata, RDFa, ARIA) detected or missing
  tailwind        — elements with large utility-class clusters that
                    are extraction candidates for @apply-based
                    component classes
  components      — unhealthy component usage: divitis / deep nesting,
                    <div role="button"> anti-patterns, inline style
                    blobs, repeated DOM structures that should be
                    extracted into components, and oversize JSX/TSX
                    component files
  hygiene         — outline:none, transition:all, user-scalable=no,
                    <img> missing dimensions, missing font-display:swap
  validation      — W3C HTML + CSS validator summary (online call,
                    skipped if --no-validate)

Usage:
  scan_design.py --path <dir> [--no-validate]
  scan_design.py --url <url>  [--no-validate]

Exactly one of --path or --url is required.
"""

import argparse
from collections import Counter, defaultdict
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

# ---------------------------------------------------------------------------
# Color utilities (WCAG 2.1 contrast)
# ---------------------------------------------------------------------------

HEX_RE = re.compile(r"#([0-9a-fA-F]{3,8})\b")
RGB_RE = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*[\d.]+\s*)?\)")
HSL_RE = re.compile(r"hsla?\(\s*(\d+)\s*,\s*(\d+)%\s*,\s*(\d+)%\s*(?:,\s*[\d.]+\s*)?\)")

NAMED_COLORS = {
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    "red": (255, 0, 0),
    "green": (0, 128, 0),
    "lime": (0, 255, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "cyan": (0, 255, 255),
    "magenta": (255, 0, 255),
    "silver": (192, 192, 192),
    "gray": (128, 128, 128),
    "grey": (128, 128, 128),
    "maroon": (128, 0, 0),
    "olive": (128, 128, 0),
    "purple": (128, 0, 128),
    "teal": (0, 128, 128),
    "navy": (0, 0, 128),
    "orange": (255, 165, 0),
    "pink": (255, 192, 203),
    "rebeccapurple": (102, 51, 153),
    "indigo": (75, 0, 130),
    "violet": (238, 130, 238),
    "transparent": None,
}


def parse_hex(h):
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    elif len(h) == 4:
        h = "".join(c * 2 for c in h[:3])
    elif len(h) == 8:
        h = h[:6]
    elif len(h) != 6:
        return None
    try:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except ValueError:
        return None


def hsl_to_rgb(h, s, lightness):
    s, lightness = s / 100.0, lightness / 100.0
    c = (1 - abs(2 * lightness - 1)) * s
    x = c * (1 - abs((h / 60.0) % 2 - 1))
    m = lightness - c / 2
    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    return (
        max(0, min(255, int((r + m) * 255))),
        max(0, min(255, int((g + m) * 255))),
        max(0, min(255, int((b + m) * 255))),
    )


def find_color(token):
    """Return RGB tuple or None for a single color token."""
    token = token.strip().lower()
    if token in NAMED_COLORS:
        return NAMED_COLORS[token]
    m = HEX_RE.fullmatch(token)
    if m:
        return parse_hex(m.group(1))
    m = RGB_RE.fullmatch(token)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = HSL_RE.fullmatch(token)
    if m:
        return hsl_to_rgb(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def extract_all_colors(text):
    colors = []
    for m in HEX_RE.finditer(text):
        rgb = parse_hex(m.group(1))
        if rgb:
            colors.append(rgb)
    for m in RGB_RE.finditer(text):
        colors.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    for m in HSL_RE.finditer(text):
        colors.append(hsl_to_rgb(int(m.group(1)), int(m.group(2)), int(m.group(3))))
    return colors


def relative_luminance(rgb):
    def ch(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast_ratio(rgb1, rgb2):
    l1, l2 = relative_luminance(rgb1), relative_luminance(rgb2)
    if l1 < l2:
        l1, l2 = l2, l1
    return (l1 + 0.05) / (l2 + 0.05)


def is_gray(rgb):
    r, g, b = rgb
    return max(r, g, b) - min(r, g, b) <= 8


def hue(rgb):
    r, g, b = [c / 255.0 for c in rgb]
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    if d == 0:
        return None
    if mx == r:
        h = ((g - b) / d) % 6
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    return h * 60


def hue_family(h):
    if h is None:
        return "gray"
    if h < 15 or h >= 345:
        return "red"
    if h < 45:
        return "orange"
    if h < 70:
        return "yellow"
    if h < 160:
        return "green"
    if h < 200:
        return "cyan"
    if h < 250:
        return "blue"
    if h < 290:
        return "purple"
    return "pink"


# ---------------------------------------------------------------------------
# Source loading
# ---------------------------------------------------------------------------

UA = "Mozilla/5.0 (audit-design scanner)"


def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
        enc = r.headers.get_content_charset() or "utf-8"
        return data.decode(enc, errors="replace")


def load_from_url(url):
    """Fetch HTML + linked stylesheets. Detect SPAs (near-empty body)."""
    html = fetch(url)
    spa_warning = False
    body_match = re.search(r"<body[^>]*>(.*?)</body>", html, re.DOTALL | re.IGNORECASE)
    if body_match:
        body_text = re.sub(
            r"<script.*?</script>", "", body_match.group(1), flags=re.DOTALL | re.IGNORECASE
        )
        body_text = re.sub(r"<[^>]+>", "", body_text).strip()
        if len(body_text) < 200:
            spa_warning = True

    css_chunks = []
    for m in re.finditer(r"<style[^>]*>(.*?)</style>", html, re.DOTALL | re.IGNORECASE):
        css_chunks.append(m.group(1))
    for m in re.finditer(r'<link[^>]+rel=["\']?stylesheet["\']?[^>]*>', html, re.IGNORECASE):
        href_m = re.search(r'href=["\']([^"\']+)["\']', m.group(0))
        if not href_m:
            continue
        href = urllib.parse.urljoin(url, href_m.group(1))
        try:
            css_chunks.append(fetch(href))
        except Exception as e:
            css_chunks.append(f"/* failed to fetch {href}: {e} */")
    return {
        "html": html,
        "css": "\n\n".join(css_chunks),
        "source_type": "url",
        "source": url,
        "spa_warning": spa_warning,
    }


def load_from_path(path):
    """Walk a directory for HTML/CSS/JSX/TSX/Vue/Svelte files."""
    html_parts, css_parts = [], []
    exts_html = {".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte"}
    exts_css = {".css", ".scss", ".sass", ".less"}
    n_files = 0
    for root, _, files in os.walk(path):
        if any(
            skip in root for skip in ("/node_modules/", "/.git/", "/dist/", "/build/", "/.next/")
        ):
            continue
        for f in files:
            fp = os.path.join(root, f)
            ext = os.path.splitext(f)[1].lower()
            if ext in exts_html or ext in exts_css:
                try:
                    with open(fp, encoding="utf-8", errors="replace") as fh:
                        content = fh.read()
                except OSError:
                    continue
                n_files += 1
                if ext in exts_html:
                    html_parts.append(content)
                    for m in re.finditer(
                        r"<style[^>]*>(.*?)</style>", content, re.DOTALL | re.IGNORECASE
                    ):
                        css_parts.append(m.group(1))
                else:
                    css_parts.append(content)
    return {
        "html": "\n\n".join(html_parts),
        "css": "\n\n".join(css_parts),
        "source_type": "path",
        "source": path,
        "files_scanned": n_files,
        "spa_warning": False,
    }


# ---------------------------------------------------------------------------
# CSS rule parser (lightweight)
# ---------------------------------------------------------------------------


def iter_rules(css):
    """Yield (selector, body) for each CSS rule. Ignores @media nesting
    structure but still sees the inner rules."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    depth = 0
    buf = []
    selector = []
    for ch in css:
        if ch == "{":
            if depth == 0:
                sel = "".join(selector).strip()
                selector = []
                depth = 1
                buf = []
                continue
            depth += 1
            buf.append(ch)
        elif ch == "}":
            depth -= 1
            if depth == 0:
                yield sel, "".join(buf)
                buf = []
            else:
                buf.append(ch)
        else:
            if depth == 0:
                selector.append(ch)
            else:
                buf.append(ch)


def get_decl(body, prop):
    """Return the last declaration value for `prop` in a rule body."""
    pattern = re.compile(rf"(?:^|;)\s*{re.escape(prop)}\s*:\s*([^;}}]+)", re.IGNORECASE)
    vals = pattern.findall(body)
    return vals[-1].strip() if vals else None


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

BLACKLIST_FONTS = {
    "papyrus",
    "comic sans",
    "comic sans ms",
    "lobster",
    "impact",
    "jokerman",
    "curlz mt",
}
GENERIC_FONTS = {"inter", "roboto", "open sans", "poppins"}

SLOP_PLACEHOLDER_COPY = [
    r"lorem\s+ipsum",
    r"welcome\s+to\s+\[",
    r"unlock\s+the\s+power\s+of",
    r"your\s+all-in-one\s+solution",
    r"revolutioniz(?:e|ing)\s+the\s+way",
    r"take\s+your\s+\w+\s+to\s+the\s+next\s+level",
]

EMOJI_RE = re.compile(
    "[" + "\U0001f300-\U0001f5ff"  # symbols & pictographs
    "\U0001f600-\U0001f64f"  # emoticons
    "\U0001f680-\U0001f6ff"  # transport
    "\U0001f700-\U0001f77f"
    "\U0001f900-\U0001f9ff"
    "\U0001fa00-\U0001fa6f"
    "\U0001fa70-\U0001faff"
    "\U00002700-\U000027bf"  # dingbats
    "\U0001f1e0-\U0001f1ff"  # flags
    "]+"
)


def check_contrast(css):
    findings = []
    for sel, body in iter_rules(css):
        fg = get_decl(body, "color")
        bg = get_decl(body, "background-color") or get_decl(body, "background")
        if not fg or not bg:
            continue
        fg_rgb = find_color(fg.split()[0])
        bg_colors = extract_all_colors(bg)
        bg_rgb = bg_colors[0] if bg_colors else find_color(bg.split()[0])
        if not fg_rgb or not bg_rgb:
            continue
        ratio = contrast_ratio(fg_rgb, bg_rgb)
        font_size = get_decl(body, "font-size") or ""
        font_weight = get_decl(body, "font-weight") or ""
        size_px = None
        m = re.match(r"([\d.]+)px", font_size.strip())
        if m:
            size_px = float(m.group(1))
        is_large = (size_px and size_px >= 24) or (
            size_px and size_px >= 18.66 and font_weight.strip() in ("bold", "700", "800", "900")
        )
        required = 3.0 if is_large else 4.5
        if ratio < required:
            findings.append(
                {
                    "selector": sel[:120],
                    "fg": fg.strip()[:40],
                    "bg": bg.strip()[:40],
                    "ratio": round(ratio, 2),
                    "required": required,
                    "severity": "high" if ratio < 3.0 else "medium",
                }
            )
    return findings


STATE_CLASSES = re.compile(
    r"\.(success|error|warning|danger|info|alert|notice|valid|invalid)"
    r"(?:[-_][\w-]+)?\b",
    re.IGNORECASE,
)


def check_color_signaling(css, html):
    """Flag state classes whose differentiation is color-only. Proxy: if
    the rule sets color/background but no pseudo-element (::before),
    no border, no icon-related property — it's at risk."""
    findings = []
    red_green_pairs = 0
    for sel, body in iter_rules(css):
        if not STATE_CLASSES.search(sel):
            continue
        has_color = bool(
            get_decl(body, "color")
            or get_decl(body, "background-color")
            or get_decl(body, "background")
        )
        if not has_color:
            continue
        non_color_cues = bool(
            re.search(r"::(before|after)", sel)
            or get_decl(body, "border")
            or get_decl(body, "border-left")
            or get_decl(body, "border-color")
            or get_decl(body, "text-decoration")
            or get_decl(body, "font-weight")
        )
        if not non_color_cues:
            findings.append(
                {
                    "selector": sel[:120],
                    "note": "state class differentiated by color only — add icon, label, or border",
                    "severity": "high",
                }
            )
    # Red+green only combinations: look for sibling success/error pairs
    # using red and green hues without other cues.
    success_colors, error_colors = [], []
    for sel, body in iter_rules(css):
        sl = sel.lower()
        fg = get_decl(body, "color")
        if not fg:
            continue
        rgb = find_color(fg.split()[0])
        if not rgb:
            continue
        if "success" in sl or "valid" in sl:
            success_colors.append(rgb)
        elif "error" in sl or "danger" in sl or "invalid" in sl:
            error_colors.append(rgb)
    for s in success_colors:
        for e in error_colors:
            if hue_family(hue(s)) == "green" and hue_family(hue(e)) == "red":
                red_green_pairs += 1
    return findings, red_green_pairs


def check_palette(css):
    raw = extract_all_colors(css)
    non_gray = [c for c in raw if not is_gray(c)]
    uniq = list({c for c in non_gray})
    return {
        "unique_non_gray": len(uniq),
        "flagged": len(uniq) > 12,
        "sample": [f"rgb{c}" for c in uniq[:15]],
    }


def check_typography(css, html):
    families = []
    for m in re.finditer(r"font-family\s*:\s*([^;}\n]+)", css, re.IGNORECASE):
        families.append(m.group(1).strip())
    # First listed family in each stack
    primaries = Counter()
    blacklist_hits = []
    generic_hits = []
    for stack in families:
        first = stack.split(",")[0].strip().strip("'\"").lower()
        if not first:
            continue
        primaries[first] += 1
        if first in BLACKLIST_FONTS or any(b in first for b in BLACKLIST_FONTS):
            blacklist_hits.append(first)
        if first in GENERIC_FONTS:
            generic_hits.append(first)

    # body font-size check
    body_size_issue = None
    for sel, body in iter_rules(css):
        if re.match(r"^\s*(html|body)\b", sel.strip(), re.IGNORECASE):
            fs = get_decl(body, "font-size")
            if fs:
                m = re.match(r"([\d.]+)px", fs.strip())
                if m and float(m.group(1)) < 16:
                    body_size_issue = f"{sel.strip()}: {fs.strip()}"
                    break

    # Straight quotes in heading text
    straight_quote_hits = 0
    for m in re.finditer(r"<h[1-6][^>]*>(.*?)</h[1-6]>", html, re.DOTALL | re.IGNORECASE):
        text = re.sub(r"<[^>]+>", "", m.group(1))
        if '"' in text or "'" in text:
            straight_quote_hits += 1

    return {
        "unique_primary_families": len(primaries),
        "primary_families": list(primaries.keys())[:10],
        "flagged_count": len(primaries) > 3,
        "blacklist_hits": sorted(set(blacklist_hits)),
        "generic_hits": sorted(set(generic_hits)),
        "body_size_below_16px": body_size_issue,
        "straight_quote_headings": straight_quote_hits,
    }


def check_spacing(css):
    # Collect all padding/margin pixel values, see if they fit 4 or 8 base
    vals = []
    for prop in ("padding", "margin", "gap"):
        for m in re.finditer(
            rf"\b{prop}(?:-(?:top|right|bottom|left|block|inline)[-\w]*)?\s*:\s*([^;}}]+)",
            css,
            re.IGNORECASE,
        ):
            for tok in m.group(1).split():
                pm = re.match(r"([\d.]+)px", tok)
                if pm:
                    v = float(pm.group(1))
                    if 0 < v <= 128:
                        vals.append(v)
    fit_4 = sum(1 for v in vals if v % 4 == 0)
    fit_8 = sum(1 for v in vals if v % 8 == 0)
    total = len(vals) or 1
    best = max(fit_4, fit_8)
    coherence = best / total

    radii = []
    for m in re.finditer(r"border-radius\s*:\s*([^;}\n]+)", css, re.IGNORECASE):
        for tok in m.group(1).split():
            pm = re.match(r"([\d.]+)(px|rem|em)", tok)
            if pm:
                radii.append(tok.strip())
    radii_counter = Counter(radii)

    return {
        "spacing_samples": len(vals),
        "scale_coherence_pct": round(coherence * 100, 1),
        "scale_ok": coherence >= 0.75,
        "radius_distinct_values": len(set(radii)),
        "radius_top": radii_counter.most_common(5),
    }


PURPLE_GRADIENT_RE = re.compile(
    r"(?:linear|radial)-gradient\([^)]*"
    r"(?:purple|violet|indigo|rebeccapurple|#[6-9a-f][0-9a-f]{5})",
    re.IGNORECASE,
)


def check_ai_slop(css, html):
    findings = []

    # purple/violet gradients
    if PURPLE_GRADIENT_RE.search(css):
        findings.append(
            {
                "pattern": "purple/violet/indigo gradient",
                "severity": "polish",
                "note": "AI-slop tell; swap for a specific brand color",
            }
        )

    # 3-column symmetric grid (soft signal)
    if re.search(r"grid-template-columns\s*:\s*repeat\(\s*3\s*,\s*1fr\)", css):
        findings.append(
            {
                "pattern": "repeat(3, 1fr) grid",
                "severity": "polish",
                "note": "Could be the SaaS-starter feature grid. Check content, not layout.",
            }
        )

    # text-align: center frequency
    center_count = len(re.findall(r"text-align\s*:\s*center", css, re.IGNORECASE))
    align_total = len(re.findall(r"text-align\s*:", css, re.IGNORECASE))
    center_ratio = center_count / align_total if align_total else 0
    if align_total >= 5 and center_ratio > 0.5:
        findings.append(
            {
                "pattern": f"text-align: center used in {center_count}/{align_total} rules",
                "severity": "medium",
                "note": "Centering everything is a common AI-slop tell; use sparingly for hierarchy.",
            }
        )

    # colored left-border cards
    left_border = len(
        re.findall(
            r"border-left\s*:\s*\d+(?:px|rem)?\s+solid\s+(?!transparent|currentcolor)",
            css,
            re.IGNORECASE,
        )
    )
    if left_border >= 2:
        findings.append(
            {
                "pattern": f"colored border-left on {left_border} rules",
                "severity": "polish",
                "note": "The 'accent stripe card' is an AI-slop signature.",
            }
        )

    # icons in colored circles
    circle_icon = len(
        re.findall(
            r"border-radius\s*:\s*50%[^}]*background(?:-color)?\s*:",
            css,
            re.IGNORECASE | re.DOTALL,
        )
    )
    if circle_icon >= 3:
        findings.append(
            {
                "pattern": f"{circle_icon} rules with border-radius:50% + background color (icon-in-circle)",
                "severity": "polish",
                "note": "Symptom of the 3-col feature grid aesthetic.",
            }
        )

    # uniform bubbly radius
    radius_values = []
    for m in re.finditer(r"border-radius\s*:\s*([^;}\n]+)", css, re.IGNORECASE):
        radius_values.append(m.group(1).strip())
    if radius_values:
        common, count = Counter(radius_values).most_common(1)[0]
        if count >= 5 and count / len(radius_values) > 0.6:
            findings.append(
                {
                    "pattern": f"border-radius '{common}' used in {count}/{len(radius_values)} rules",
                    "severity": "polish",
                    "note": "Uniform radius across element types = bubbly AI look. Use a radius scale.",
                }
            )

    # emoji in headings
    emoji_in_headings = 0
    for m in re.finditer(r"<h[1-6][^>]*>(.*?)</h[1-6]>", html, re.DOTALL | re.IGNORECASE):
        text = re.sub(r"<[^>]+>", "", m.group(1))
        if EMOJI_RE.search(text):
            emoji_in_headings += 1
    if emoji_in_headings:
        findings.append(
            {
                "pattern": f"emoji in {emoji_in_headings} headings",
                "severity": "polish",
                "note": "Emoji as design decoration reads as lazy/AI-generated.",
            }
        )

    # placeholder copy
    copy_hits = []
    text_only = re.sub(r"<script.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text_only = re.sub(r"<style.*?</style>", "", text_only, flags=re.DOTALL | re.IGNORECASE)
    text_only = re.sub(r"<[^>]+>", " ", text_only)
    for pattern in SLOP_PLACEHOLDER_COPY:
        if re.search(pattern, text_only, re.IGNORECASE):
            copy_hits.append(pattern)
    if copy_hits:
        findings.append(
            {
                "pattern": "placeholder/generic hero copy",
                "severity": "high",
                "note": f"Matched: {', '.join(copy_hits)}. Rewrite with concrete, specific copy.",
            }
        )

    return findings


def check_hygiene(css, html):
    issues = []

    # outline: none without focus-visible present anywhere
    outline_none = len(re.findall(r"outline\s*:\s*(?:none|0)", css, re.IGNORECASE))
    focus_visible = len(re.findall(r":focus-visible", css))
    if outline_none and focus_visible == 0:
        issues.append(
            {
                "issue": f"outline:none used {outline_none}x but no :focus-visible styles found",
                "severity": "high",
                "note": "Keyboard users lose focus indicator. Pair every outline:none with a :focus-visible replacement.",
            }
        )

    if re.search(r"transition\s*:\s*all\b", css, re.IGNORECASE):
        issues.append(
            {
                "issue": "transition: all",
                "severity": "medium",
                "note": "Animates layout properties too; causes jank. List specific properties.",
            }
        )

    if re.search(r'user-scalable\s*=\s*["\']?no', html, re.IGNORECASE) or re.search(
        r'maximum-scale\s*=\s*["\']?1', html, re.IGNORECASE
    ):
        issues.append(
            {
                "issue": "viewport blocks user zoom",
                "severity": "high",
                "note": "Accessibility regression — remove user-scalable=no / maximum-scale=1.",
            }
        )

    # <img> missing dimensions
    img_tags = re.findall(r"<img\b[^>]*>", html, re.IGNORECASE)
    missing = [
        t for t in img_tags if not (re.search(r"\bwidth\s*=", t) and re.search(r"\bheight\s*=", t))
    ]
    if img_tags:
        issues.append(
            {
                "issue": f"{len(missing)}/{len(img_tags)} <img> tags missing width+height",
                "severity": "medium" if missing else "info",
                "note": "Set explicit dimensions to prevent CLS.",
            }
        )

    # @font-face without font-display: swap
    font_face_blocks = re.findall(r"@font-face\s*\{[^}]*\}", css, re.IGNORECASE | re.DOTALL)
    missing_swap = [
        b for b in font_face_blocks if not re.search(r"font-display\s*:\s*swap", b, re.IGNORECASE)
    ]
    if font_face_blocks:
        issues.append(
            {
                "issue": f"{len(missing_swap)}/{len(font_face_blocks)} @font-face blocks missing font-display: swap",
                "severity": "medium" if missing_swap else "info",
                "note": "Without swap, users see FOIT (invisible text) until the font loads.",
            }
        )

    return issues


# ---------------------------------------------------------------------------
# Semantic HTML + microstandards
# ---------------------------------------------------------------------------

LANDMARKS = ["header", "nav", "main", "aside", "footer"]
SECTIONING = ["article", "section", "figure", "figcaption", "details", "summary"]


def check_semantics(html):
    findings = []
    heading_tags = re.findall(r"<(h[1-6])\b", html, re.IGNORECASE)
    heading_levels = [int(t[1]) for t in heading_tags]

    h1_count = heading_levels.count(1)
    if h1_count == 0 and heading_levels:
        findings.append(
            {
                "issue": "no <h1>",
                "severity": "high",
                "note": "Every page needs exactly one h1 stating its purpose.",
            }
        )
    elif h1_count > 1:
        findings.append(
            {
                "issue": f"{h1_count} <h1> tags",
                "severity": "medium",
                "note": "Use one h1 per page; demote the rest to h2.",
            }
        )

    skipped = []
    last = 0
    for lv in heading_levels:
        if last and lv > last + 1:
            skipped.append(f"h{last}→h{lv}")
        last = lv
    if skipped:
        findings.append(
            {
                "issue": f"heading levels skipped: {', '.join(skipped[:5])}",
                "severity": "medium",
                "note": "Screen readers announce hierarchy; don't jump levels.",
            }
        )

    present_landmarks = [t for t in LANDMARKS if re.search(rf"<{t}\b", html, re.IGNORECASE)]
    missing_landmarks = [t for t in LANDMARKS if t not in present_landmarks]
    if "main" in missing_landmarks and html.strip():
        findings.append(
            {
                "issue": "no <main> landmark",
                "severity": "high",
                "note": "Screen readers use <main> as a 'skip to content' target.",
            }
        )

    present_sectioning = [t for t in SECTIONING if re.search(rf"<{t}\b", html, re.IGNORECASE)]

    # Form inputs without labels or aria-label
    unlabeled_inputs = 0
    for m in re.finditer(r"<(input|textarea|select)\b([^>]*)>", html, re.IGNORECASE):
        attrs = m.group(2)
        # Skip non-form inputs
        itype = re.search(r'type\s*=\s*["\']?(\w+)', attrs)
        if itype and itype.group(1).lower() in {"hidden", "submit", "button", "reset", "image"}:
            continue
        has_id = re.search(r'\bid\s*=\s*["\']([^"\']+)', attrs)
        has_aria = re.search(r"aria-label(?:ledby)?\s*=", attrs)
        labeled = False
        if has_aria:
            labeled = True
        elif has_id:
            if re.search(
                rf'<label\b[^>]*for\s*=\s*["\']{re.escape(has_id.group(1))}["\']',
                html,
                re.IGNORECASE,
            ):
                labeled = True
        if not labeled:
            unlabeled_inputs += 1
    if unlabeled_inputs:
        findings.append(
            {
                "issue": f"{unlabeled_inputs} form inputs without <label> or aria-label",
                "severity": "high",
                "note": "Unlabeled inputs fail screen readers and Safari autofill heuristics.",
            }
        )

    # <img> missing alt
    img_no_alt = 0
    for m in re.finditer(r"<img\b([^>]*)>", html, re.IGNORECASE):
        if not re.search(r"\balt\s*=", m.group(1)):
            img_no_alt += 1
    if img_no_alt:
        findings.append(
            {
                "issue": f"{img_no_alt} <img> tags missing alt",
                "severity": "high",
                "note": "Use alt='' for decorative images, alt='description' otherwise.",
            }
        )

    # Lang attribute
    if html.strip() and not re.search(r"<html\b[^>]*\blang\s*=", html, re.IGNORECASE):
        findings.append(
            {
                "issue": "no lang attribute on <html>",
                "severity": "medium",
                "note": "Screen readers + translation tools need it; add <html lang='en'>.",
            }
        )

    # Microstandards detection
    standards = {
        "opengraph": bool(re.search(r'<meta[^>]+property=["\']og:', html, re.IGNORECASE)),
        "twitter_card": bool(re.search(r'<meta[^>]+name=["\']twitter:', html, re.IGNORECASE)),
        "json_ld": bool(
            re.search(r'<script[^>]+type=["\']application/ld\+json', html, re.IGNORECASE)
        ),
        "microdata": bool(re.search(r"\bitemscope\b", html, re.IGNORECASE)),
        "rdfa": bool(re.search(r"\b(?:vocab|typeof|property)\s*=", html)),
        "schema_org": bool(re.search(r"schema\.org", html, re.IGNORECASE)),
        "canonical": bool(re.search(r'<link[^>]+rel=["\']canonical', html, re.IGNORECASE)),
        "favicon": bool(
            re.search(r'<link[^>]+rel=["\'](?:icon|shortcut icon)', html, re.IGNORECASE)
        ),
        "theme_color": bool(re.search(r'<meta[^>]+name=["\']theme-color', html, re.IGNORECASE)),
        "viewport": bool(re.search(r'<meta[^>]+name=["\']viewport', html, re.IGNORECASE)),
    }

    # Detect page type from content to suggest relevant standards
    suggestions = []
    lower = html.lower()
    if not standards["opengraph"]:
        suggestions.append(
            "OpenGraph meta tags (og:title, og:description, og:image) — controls link previews on social + chat apps."
        )
    if not standards["json_ld"] and any(
        k in lower
        for k in ("article", "product", "price", "recipe", "event", "<time", "author", "breadcrumb")
    ):
        suggestions.append(
            "JSON-LD with schema.org — content looks like it has a real type (Article, Product, Event, Recipe). Structured data drives rich-result eligibility."
        )
    if not standards["canonical"]:
        suggestions.append("<link rel='canonical'> — prevents duplicate-content SEO hits.")
    if not standards["theme_color"]:
        suggestions.append("<meta name='theme-color'> — colors the mobile browser chrome.")

    return {
        "findings": findings,
        "heading_levels": heading_levels[:40],
        "landmarks_present": present_landmarks,
        "landmarks_missing": missing_landmarks,
        "sectioning_present": present_sectioning,
        "microstandards": standards,
        "suggestions": suggestions,
    }


# ---------------------------------------------------------------------------
# Tailwind utility-class cluster detection
# ---------------------------------------------------------------------------

TW_PREFIXES = (
    "bg",
    "text",
    "border",
    "rounded",
    "shadow",
    "ring",
    "outline",
    "p",
    "px",
    "py",
    "pt",
    "pr",
    "pb",
    "pl",
    "ps",
    "pe",
    "m",
    "mx",
    "my",
    "mt",
    "mr",
    "mb",
    "ml",
    "ms",
    "me",
    "w",
    "h",
    "min-w",
    "min-h",
    "max-w",
    "max-h",
    "size",
    "gap",
    "space-x",
    "space-y",
    "divide-x",
    "divide-y",
    "flex",
    "grid",
    "items",
    "justify",
    "self",
    "place",
    "col",
    "row",
    "col-span",
    "row-span",
    "col-start",
    "col-end",
    "order",
    "content",
    "font",
    "tracking",
    "leading",
    "decoration",
    "underline",
    "whitespace",
    "break",
    "truncate",
    "line-clamp",
    "opacity",
    "z",
    "top",
    "right",
    "bottom",
    "left",
    "inset",
    "translate-x",
    "translate-y",
    "rotate",
    "scale",
    "skew",
    "origin",
    "transform",
    "transition",
    "duration",
    "ease",
    "animate",
    "delay",
    "cursor",
    "select",
    "pointer-events",
    "resize",
    "scroll",
    "list",
    "fill",
    "stroke",
    "placeholder",
    "accent",
    "caret",
    "backdrop",
    "filter",
    "blur",
    "brightness",
    "contrast",
    "block",
    "inline",
    "hidden",
    "static",
    "fixed",
    "absolute",
    "relative",
    "sticky",
    "overflow",
    "overflow-x",
    "overflow-y",
    "object",
    "aspect",
)

TW_PREFIX_RE = re.compile(
    r"^(?:(?:sm|md|lg|xl|2xl|hover|focus|active|disabled|group-hover|"
    r"dark|peer|first|last|odd|even|focus-visible|focus-within):)*"
    r"(?:-?)(?:" + "|".join(re.escape(p) for p in TW_PREFIXES) + r")"
    r"(?:-[-\w/.%]+)?$"
)


def looks_tailwind(cls):
    return bool(TW_PREFIX_RE.match(cls)) or cls in (
        "container",
        "prose",
        "sr-only",
        "not-sr-only",
        "antialiased",
        "subpixel-antialiased",
        "italic",
        "underline",
        "uppercase",
        "lowercase",
        "capitalize",
        "truncate",
    )


def check_tailwind(html, css):
    class_lists = re.findall(r'class(?:Name)?\s*=\s*["\']([^"\']+)["\']', html)
    if not class_lists:
        return {
            "detected": False,
            "note": "No class attributes found in HTML.",
        }
    total_tokens = 0
    tw_tokens = 0
    cluster_sizes = []
    worst = []
    for cl in class_lists:
        tokens = cl.split()
        if not tokens:
            continue
        tw_in = sum(1 for t in tokens if looks_tailwind(t))
        total_tokens += len(tokens)
        tw_tokens += tw_in
        if tw_in >= 3:
            cluster_sizes.append(tw_in)
        if tw_in >= 12:
            worst.append(
                {
                    "class_count": tw_in,
                    "tokens": " ".join(tokens[:20]) + ("…" if len(tokens) > 20 else ""),
                }
            )

    tw_ratio = tw_tokens / total_tokens if total_tokens else 0
    detected = tw_ratio > 0.4 and tw_tokens >= 20

    worst.sort(key=lambda x: -x["class_count"])

    apply_used = bool(re.search(r"@apply\s", css, re.IGNORECASE))
    component_layer = bool(re.search(r"@layer\s+components", css, re.IGNORECASE))

    suggestion = None
    if detected and worst:
        suggestion = (
            f"{len(worst)} element(s) have 12+ utility classes. Extract to "
            f"semantic classes in an @layer components block with @apply — "
            f"the markup becomes readable and the design intent is reusable."
        )
        if not component_layer:
            suggestion += " No @layer components block found; add one to your CSS entry file."

    return {
        "detected": detected,
        "tw_ratio": round(tw_ratio, 3),
        "tw_tokens": tw_tokens,
        "total_tokens": total_tokens,
        "clusters_over_12": len(worst),
        "clusters_over_8": sum(1 for n in cluster_sizes if n >= 8),
        "worst_offenders": worst[:5],
        "apply_used": apply_used,
        "component_layer_used": component_layer,
        "suggestion": suggestion,
    }


# ---------------------------------------------------------------------------
# WCAG additional checks (complements semantics + contrast + hygiene)
# ---------------------------------------------------------------------------

GENERIC_LINK_TEXT = {
    "click here",
    "here",
    "read more",
    "more",
    "learn more",
    "this",
    "this link",
    "link",
    "continue",
    "details",
    "go",
    "info",
}


def check_wcag_extras(html, css):
    """WCAG criteria not already covered by semantics/contrast/hygiene."""
    findings = []

    # 2.4.2 Page Titled
    title_m = re.search(r"<title\b[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
    if html.strip() and (not title_m or not title_m.group(1).strip()):
        findings.append(
            {
                "wcag": "2.4.2",
                "issue": "missing or empty <title>",
                "severity": "high",
                "note": "The <title> is the first thing screen readers announce and what shows in tabs/bookmarks.",
            }
        )

    # 2.4.4 Link Purpose — generic/empty anchor text
    generic_links = 0
    empty_links = 0
    for m in re.finditer(r"<a\b[^>]*>(.*?)</a>", html, re.DOTALL | re.IGNORECASE):
        tag_open = re.match(r"<a\b[^>]*>", m.group(0)).group(0)
        # has aria-label? then it's labeled — skip
        if re.search(r"aria-label\s*=", tag_open):
            continue
        inner = re.sub(r"<[^>]+>", " ", m.group(1)).strip().lower()
        if not inner:
            # Might contain an <img alt> — check
            img_alt = re.search(r'<img[^>]+alt\s*=\s*["\']([^"\']+)', m.group(1))
            if not img_alt or not img_alt.group(1).strip():
                empty_links += 1
        elif inner in GENERIC_LINK_TEXT:
            generic_links += 1
    if empty_links:
        findings.append(
            {
                "wcag": "2.4.4",
                "issue": f"{empty_links} <a> tags with no accessible text",
                "severity": "high",
                "note": "Empty links are invisible to screen readers. Add text content, aria-label, or alt on the inner image.",
            }
        )
    if generic_links >= 2:
        findings.append(
            {
                "wcag": "2.4.4",
                "issue": f'{generic_links} generic link texts ("click here", "read more", etc.)',
                "severity": "medium",
                "note": "Screen reader users often tab through links in isolation; generic text tells them nothing.",
            }
        )

    # 1.2.2 Captions — <video> without <track>
    videos = re.findall(r"<video\b(.*?)</video>", html, re.DOTALL | re.IGNORECASE)
    video_no_track = sum(1 for v in videos if "<track" not in v.lower())
    if video_no_track:
        findings.append(
            {
                "wcag": "1.2.2",
                "issue": f"{video_no_track} <video> without <track> (captions)",
                "severity": "high",
                "note": "Video needs captions for deaf/HoH users. Add <track kind='captions'> at minimum.",
            }
        )

    # 2.5.5 Target Size — explicit height < 44px on buttons/anchors
    small_targets = []
    for sel, body in iter_rules(css):
        if not re.search(
            r"(?:^|,|\s)(?:button|a|input\[type=[\"']?(?:button|submit|reset)[\"']?\]|\.btn|\.button)\b",
            sel,
            re.IGNORECASE,
        ):
            continue
        for prop in ("height", "min-height"):
            val = get_decl(body, prop)
            if not val:
                continue
            m = re.match(r"([\d.]+)px", val.strip())
            if m and float(m.group(1)) < 44:
                small_targets.append(
                    {
                        "selector": sel[:80],
                        "prop": prop,
                        "value": val.strip(),
                    }
                )
                break
    if small_targets:
        findings.append(
            {
                "wcag": "2.5.5",
                "issue": f"{len(small_targets)} interactive rule(s) with height < 44px",
                "severity": "medium",
                "note": "WCAG 2.5.5 (AAA) asks for 44×44px minimum; 2.5.8 (AA, WCAG 2.2) asks for 24×24px. Buttons smaller than 44px are hard to tap on mobile.",
                "examples": small_targets[:3],
            }
        )

    # 1.3.5 Identify Input Purpose — inputs missing autocomplete
    common_inputs = 0
    no_autocomplete = 0
    for m in re.finditer(r"<input\b([^>]*)>", html, re.IGNORECASE):
        attrs = m.group(1)
        itype = re.search(r'\btype\s*=\s*["\']?(\w+)', attrs)
        name = re.search(r'\bname\s*=\s*["\']?([^"\'>\s]+)', attrs)
        if not itype or not name:
            continue
        if itype.group(1).lower() not in {"text", "email", "tel", "password", "url"}:
            continue
        common_inputs += 1
        if not re.search(r"\bautocomplete\s*=", attrs):
            no_autocomplete += 1
    if common_inputs >= 3 and no_autocomplete / common_inputs >= 0.5:
        findings.append(
            {
                "wcag": "1.3.5",
                "issue": f"{no_autocomplete}/{common_inputs} form inputs missing autocomplete attribute",
                "severity": "medium",
                "note": "autocomplete='email' / 'given-name' / 'tel' etc. lets browsers + assistive tech fill the right info.",
            }
        )

    return findings


WCAG_CATALOG = {
    "1.1.1": "Non-text Content (images have alt)",
    "1.2.2": "Captions (Prerecorded)",
    "1.3.1": "Info and Relationships (semantic structure)",
    "1.3.5": "Identify Input Purpose (autocomplete)",
    "1.4.1": "Use of Color (not color alone)",
    "1.4.3": "Contrast (Minimum) AA",
    "1.4.4": "Resize Text (no user-scalable=no)",
    "1.4.10": "Reflow (not checked here)",
    "1.4.11": "Non-text Contrast (UI components ≥ 3:1)",
    "1.4.12": "Text Spacing (not checked here)",
    "2.1.1": "Keyboard (no <div onClick> as button)",
    "2.4.1": "Bypass Blocks (<main> landmark)",
    "2.4.2": "Page Titled",
    "2.4.4": "Link Purpose (In Context)",
    "2.4.6": "Headings and Labels",
    "2.4.7": "Focus Visible",
    "2.5.5": "Target Size (44×44px)",
    "3.1.1": "Language of Page (<html lang>)",
    "3.3.2": "Labels or Instructions (form labels)",
    "4.1.1": "Parsing (W3C HTML validator)",
    "4.1.2": "Name, Role, Value (ARIA / form labels)",
}


def wcag_coverage(results):
    """Map checked criteria to status: pass / fail / warn / not-checked."""
    # Map each criterion to the findings that hit it.
    fails_by_wcag = defaultdict(list)

    for f in results["contrast"]:
        fails_by_wcag["1.4.3"].append(f)
    for f in results["color_signaling"]["findings"]:
        fails_by_wcag["1.4.1"].append(f)
    if results["color_signaling"]["red_green_pairs"]:
        fails_by_wcag["1.4.1"].append({"issue": "red/green state pair"})
    for f in results["semantics"]["findings"]:
        issue = f.get("issue", "")
        if "heading" in issue or "h1" in issue:
            fails_by_wcag["1.3.1"].append(f)
            fails_by_wcag["2.4.6"].append(f)
        elif "main" in issue or "landmark" in issue:
            fails_by_wcag["2.4.1"].append(f)
        elif "label" in issue or "aria-label" in issue or "input" in issue:
            fails_by_wcag["3.3.2"].append(f)
            fails_by_wcag["4.1.2"].append(f)
        elif "alt" in issue:
            fails_by_wcag["1.1.1"].append(f)
        elif "lang" in issue:
            fails_by_wcag["3.1.1"].append(f)
    for f in results.get("components", {}).get("findings", []):
        issue = f.get("issue", "")
        if "clickable" in issue or 'role="button"' in issue or "onClick" in issue:
            fails_by_wcag["2.1.1"].append(f)
            fails_by_wcag["4.1.2"].append(f)
    for f in results["hygiene"]:
        issue = f.get("issue", "")
        if "outline" in issue:
            fails_by_wcag["2.4.7"].append(f)
        elif "user zoom" in issue:
            fails_by_wcag["1.4.4"].append(f)
    for f in results.get("wcag_extras", []):
        wc = f.get("wcag")
        if wc:
            fails_by_wcag[wc].append(f)

    # HTML validator counts for 4.1.1
    html_val = (
        results.get("validation", {}).get("html", {})
        if isinstance(results.get("validation"), dict)
        else {}
    )
    html_errs = html_val.get("errors", 0) if isinstance(html_val, dict) else 0
    if html_errs:
        fails_by_wcag["4.1.1"].append({"issue": f"{html_errs} W3C HTML errors"})

    coverage = {}
    for wc, desc in WCAG_CATALOG.items():
        fs = fails_by_wcag.get(wc, [])
        if wc in ("1.4.10", "1.4.12"):
            coverage[wc] = {
                "description": desc,
                "status": "not-checked",
                "reason": "requires a live browser",
            }
        elif fs:
            coverage[wc] = {"description": desc, "status": "fail", "fail_count": len(fs)}
        else:
            coverage[wc] = {"description": desc, "status": "pass"}
    return coverage


# ---------------------------------------------------------------------------
# Component health: divitis, anti-patterns, extraction candidates
# ---------------------------------------------------------------------------


def _strip_attrs(tag):
    """Return tag-name plus canonical class attribute for fingerprinting."""
    name_m = re.match(r"<(\w+)", tag)
    if not name_m:
        return None
    cls_m = re.search(r'class(?:Name)?\s*=\s*["\']([^"\']+)["\']', tag)
    cls = " ".join(sorted(cls_m.group(1).split())) if cls_m else ""
    return f"{name_m.group(1).lower()}#{cls}"


def check_components(html, source):
    findings = []

    # Divitis: deepest consecutive <div> chain
    div_chain_re = re.compile(r"(?:<div\b[^>]*>\s*){3,}", re.IGNORECASE)
    worst_chain = 0
    for m in div_chain_re.finditer(html):
        depth = len(re.findall(r"<div\b", m.group(0)))
        if depth > worst_chain:
            worst_chain = depth
    total_divs = len(re.findall(r"<div\b", html, re.IGNORECASE))
    total_semantic = sum(
        len(re.findall(rf"<{t}\b", html, re.IGNORECASE))
        for t in (
            LANDMARKS + SECTIONING + ["button", "a", "li", "ul", "ol", "table", "form", "label"]
        )
    )
    div_ratio = total_divs / (total_divs + total_semantic) if (total_divs + total_semantic) else 0
    if worst_chain >= 5:
        findings.append(
            {
                "issue": f"deep div nesting — {worst_chain}-level consecutive <div> chain",
                "severity": "medium",
                "note": "Flatten with semantic elements (<section>, <article>, <header>) or extract to a component.",
            }
        )
    if total_divs >= 20 and div_ratio > 0.7:
        findings.append(
            {
                "issue": f"div-heavy markup ({total_divs} divs vs {total_semantic} semantic tags)",
                "severity": "medium",
                "note": "Tag soup — reach for semantic HTML first, divs for pure layout only.",
            }
        )

    # <div role="button"> / clickable divs / non-semantic nav
    role_button = len(
        re.findall(r'<(?:div|span)\b[^>]*\brole\s*=\s*["\']button["\']', html, re.IGNORECASE)
    )
    onclick_div = len(re.findall(r"<(?:div|span)\b[^>]*\bonclick\s*=", html, re.IGNORECASE))
    onclick_jsx = len(
        re.findall(
            r"<(?:div|span)\b[^>]*\bonClick\s*=\s*\{",
            html,
        )
    )
    clickable_non_button = role_button + onclick_div + onclick_jsx
    if clickable_non_button:
        findings.append(
            {
                "issue": f"{clickable_non_button} clickable <div>/<span> (role=button or onClick)",
                "severity": "high",
                "note": "Use <button type='button'> — free keyboard access, focus ring, aria semantics.",
            }
        )

    # <a> without href (common anti-pattern for fake buttons)
    a_no_href = len(re.findall(r"<a\b(?:(?!href=)[^>])*>", html, re.IGNORECASE))
    if a_no_href >= 3:
        findings.append(
            {
                "issue": f"{a_no_href} <a> tags without href",
                "severity": "medium",
                "note": "Anchors without href aren't focusable. Use <button> for actions, <a href> for navigation.",
            }
        )

    # Inline style blobs
    inline_styles = re.findall(r'\bstyle\s*=\s*["\']([^"\']{20,})["\']', html)
    if len(inline_styles) >= 5:
        findings.append(
            {
                "issue": f"{len(inline_styles)} inline style='' attributes (20+ chars each)",
                "severity": "medium",
                "note": "One-off inline styles dodge your design system. Move to classes or component styles.",
            }
        )

    # Repeated structural patterns (extraction candidates)
    fingerprints = []
    for tag in re.findall(r"<\w+\b[^>]*>", html):
        fp = _strip_attrs(tag)
        if fp and "#" in fp and len(fp.split("#", 1)[1]) > 10:
            fingerprints.append(fp)
    repeat_counter = Counter(fingerprints)
    extraction_candidates = [
        {"fingerprint": fp, "occurrences": n} for fp, n in repeat_counter.most_common(10) if n >= 4
    ]
    if extraction_candidates:
        findings.append(
            {
                "issue": f"{len(extraction_candidates)} repeated element signatures "
                f"(top: {extraction_candidates[0]['occurrences']}x)",
                "severity": "medium",
                "note": "Same tag+classes repeated 4+ times — extract to a component. "
                "Reduces drift and makes design changes one-edit.",
            }
        )

    # Oversize JSX/TSX components (only in --path mode)
    oversize_components = []
    heavy_prop_components = []
    path = source.get("source") if source.get("source_type") == "path" else None
    if path and os.path.isdir(path):
        for root, _, files in os.walk(path):
            if any(
                skip in root
                for skip in ("/node_modules/", "/.git/", "/dist/", "/build/", "/.next/")
            ):
                continue
            for f in files:
                if not f.endswith((".jsx", ".tsx", ".vue", ".svelte")):
                    continue
                fp = os.path.join(root, f)
                try:
                    with open(fp, encoding="utf-8", errors="replace") as fh:
                        content = fh.read()
                except OSError:
                    continue
                lines = content.count("\n") + 1
                if lines > 300:
                    oversize_components.append(
                        {
                            "file": os.path.relpath(fp, path),
                            "lines": lines,
                        }
                    )
                # Heavy props: a function/arrow component destructuring 10+ props
                for m in re.finditer(
                    r"(?:function|const)\s+\w+\s*=?\s*(?:\([^)]*\)\s*=>\s*)?"
                    r"\(\s*\{([^}]{150,})\}",
                    content,
                ):
                    props = [p.strip() for p in m.group(1).split(",") if p.strip()]
                    if len(props) >= 10:
                        heavy_prop_components.append(
                            {
                                "file": os.path.relpath(fp, path),
                                "prop_count": len(props),
                            }
                        )
                        break

    oversize_components.sort(key=lambda x: -x["lines"])
    if oversize_components:
        findings.append(
            {
                "issue": f"{len(oversize_components)} component file(s) over 300 lines",
                "severity": "medium",
                "note": "Oversize components usually do several jobs. Split by concern (container/presenter, or by sub-feature).",
            }
        )
    if heavy_prop_components:
        findings.append(
            {
                "issue": f"{len(heavy_prop_components)} component(s) taking 10+ props",
                "severity": "polish",
                "note": "10+ props often means two components fused. Consider composition (children/slots) or a config object.",
            }
        )

    return {
        "findings": findings,
        "total_divs": total_divs,
        "total_semantic": total_semantic,
        "div_ratio": round(div_ratio, 2),
        "deepest_div_chain": worst_chain,
        "clickable_non_button": clickable_non_button,
        "inline_style_blobs": len(inline_styles),
        "extraction_candidates": extraction_candidates[:5],
        "oversize_components": oversize_components[:5],
        "heavy_prop_components": heavy_prop_components[:5],
    }


# ---------------------------------------------------------------------------
# W3C validation (the shock section)
# ---------------------------------------------------------------------------


def w3c_html_validate(source, html_text=None, url=None, timeout=20):
    """Call Nu Html Checker. Returns summary dict or {'error': ...}."""
    endpoint = "https://validator.nu/?out=json"
    try:
        if url:
            u = f"{endpoint}&doc={urllib.parse.quote(url, safe='')}"
            req = urllib.request.Request(u, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8", errors="replace"))
        else:
            body = (html_text or "").encode("utf-8", errors="replace")
            req = urllib.request.Request(
                endpoint,
                data=body,
                headers={"User-Agent": UA, "Content-Type": "text/html; charset=utf-8"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8", errors="replace"))
        messages = data.get("messages", [])
        errors = [m for m in messages if m.get("type") == "error"]
        warnings = [m for m in messages if m.get("type") == "info" or m.get("subType") == "warning"]
        top = Counter(
            re.sub(r"[\"'`][^\"'`]{1,80}[\"'`]", "<...>", m.get("message", ""))[:140]
            for m in errors
        ).most_common(5)
        return {
            "endpoint": "validator.nu",
            "errors": len(errors),
            "warnings": len(warnings),
            "top_errors": [{"message": msg, "count": c} for msg, c in top],
        }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def w3c_css_validate(url=None, css_text=None, timeout=20):
    """Call Jigsaw CSS validator. SOAP output has a clean counts tag."""
    try:
        if url:
            u = (
                "https://jigsaw.w3.org/css-validator/validator?"
                f"uri={urllib.parse.quote(url, safe='')}&profile=css3svg"
                "&output=soap12&warning=1"
            )
        else:
            # POST form with CSS text
            form = urllib.parse.urlencode(
                {
                    "text": css_text or "",
                    "profile": "css3svg",
                    "output": "soap12",
                    "warning": "1",
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                "https://jigsaw.w3.org/css-validator/validator",
                data=form,
                headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read().decode("utf-8", errors="replace")
            return _parse_css_soap(body)
        req = urllib.request.Request(u, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", errors="replace")
        return _parse_css_soap(body)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def _parse_css_soap(body):
    errs = re.search(r"<m:errorcount>(\d+)</m:errorcount>", body)
    warns = re.search(r"<m:warningcount>(\d+)</m:warningcount>", body)
    messages = re.findall(
        r"<m:message>(.*?)</m:message>",
        body,
        re.DOTALL,
    )
    top = Counter(re.sub(r"\s+", " ", m).strip()[:140] for m in messages).most_common(5)
    return {
        "endpoint": "jigsaw.w3.org",
        "errors": int(errs.group(1)) if errs else 0,
        "warnings": int(warns.group(1)) if warns else 0,
        "top_errors": [{"message": msg, "count": c} for msg, c in top],
    }


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def score(results):
    """0–100. Deductions weighted toward colorblind-critical issues."""
    s = 100
    s -= min(30, len(results["contrast"]) * 3)
    s -= min(20, len(results["color_signaling"]["findings"]) * 5)
    s -= min(5, results["color_signaling"]["red_green_pairs"] * 5)
    if results["palette"]["flagged"]:
        s -= 5
    if results["typography"]["flagged_count"]:
        s -= 5
    s -= len(results["typography"]["blacklist_hits"]) * 5
    if results["typography"]["body_size_below_16px"]:
        s -= 3
    if not results["spacing"]["scale_ok"]:
        s -= 5
    s -= min(
        20,
        sum(
            {"high": 6, "medium": 3, "polish": 2, "info": 0}[f.get("severity", "polish")]
            for f in results["ai_slop"]
        ),
    )
    s -= min(
        15,
        sum(
            {"high": 5, "medium": 3, "info": 0}[i.get("severity", "info")]
            for i in results["hygiene"]
        ),
    )
    s -= min(
        20,
        sum(
            {"high": 5, "medium": 3, "info": 0}[f.get("severity", "info")]
            for f in results["semantics"]["findings"]
        ),
    )
    tw = results["tailwind"]
    if tw.get("detected") and tw.get("clusters_over_12", 0) >= 3:
        s -= min(8, tw["clusters_over_12"])
    s -= min(
        15,
        sum(
            {"high": 5, "medium": 3, "polish": 1, "info": 0}[f.get("severity", "info")]
            for f in results["components"]["findings"]
        ),
    )
    s -= min(
        15,
        sum(
            {"high": 5, "medium": 3, "info": 0}[f.get("severity", "info")]
            for f in results["wcag_extras"]
        ),
    )
    return max(0, s)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--path", help="Local directory to audit")
    g.add_argument("--url", help="URL to audit")
    ap.add_argument(
        "--no-validate", action="store_true", help="Skip W3C validator calls (offline mode)"
    )
    args = ap.parse_args()

    if args.url:
        src = load_from_url(args.url)
    else:
        if not os.path.isdir(args.path):
            print(json.dumps({"error": f"path not found: {args.path}"}))
            sys.exit(2)
        src = load_from_path(args.path)

    css, html = src["css"], src["html"]

    cs_findings, rg_pairs = check_color_signaling(css, html)

    results = {
        "source": {k: v for k, v in src.items() if k not in ("html", "css")},
        "bytes": {"html": len(html), "css": len(css)},
        "contrast": check_contrast(css),
        "color_signaling": {
            "findings": cs_findings,
            "red_green_pairs": rg_pairs,
        },
        "palette": check_palette(css),
        "typography": check_typography(css, html),
        "spacing": check_spacing(css),
        "ai_slop": check_ai_slop(css, html),
        "semantics": check_semantics(html),
        "tailwind": check_tailwind(html, css),
        "components": check_components(html, src),
        "hygiene": check_hygiene(css, html),
        "wcag_extras": check_wcag_extras(html, css),
    }

    if not args.no_validate:
        if args.url:
            results["validation"] = {
                "html": w3c_html_validate(src, url=args.url),
                "css": w3c_css_validate(url=args.url),
            }
        else:
            results["validation"] = {
                "html": w3c_html_validate(src, html_text=html)
                if html.strip()
                else {"skipped": "no HTML content"},
                "css": w3c_css_validate(css_text=css)
                if css.strip()
                else {"skipped": "no CSS content"},
            }
    else:
        results["validation"] = {"skipped": "disabled via --no-validate"}

    results["wcag_coverage"] = wcag_coverage(results)
    results["score"] = score(results)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
