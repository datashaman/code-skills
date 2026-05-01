#!/usr/bin/env python3
"""
scan_docs.py — static documentation scanner for the audit-docs skill.

Reads a directory of project files (markdown, source code, top-level
hygiene files) or a directory of pre-rendered HTML pages and emits a
single JSON object on stdout. The audit-docs SKILL.md interprets the
output and writes the human-readable report.

Usage:
    python3 scan_docs.py --path <dir> [--mode project|site] [--check-links]

Output: a single JSON object with these top-level keys:
    inventory, hygiene, diataxis, api_coverage, site, agent,
    examples, score, deductions
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any

MD_EXTS = {".md", ".mdx", ".markdown"}
CODE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".php"}
SKIP_DIRS = {
    ".git",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "coverage",
    "__pycache__",
    ".venv",
    "venv",
    "target",
    "vendor",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".cache",
    "site-packages",
}

# Path-glob excludes applied against forward-slash relative paths.
# Built-ins cover well-known framework runtime artefact locations.
DEFAULT_EXCLUDE_GLOBS = (
    "storage/app/runs/*",  # Laravel/Specify per-run agent workdirs
    "storage/framework/*",  # Laravel runtime cache, sessions, views
    "storage/logs/*",  # Laravel logs
    "tmp/*",
    "temp/*",
)
STALE_DAYS = 365
NOW = time.time()


def is_excluded(rel: str, globs: tuple[str, ...]) -> bool:
    """Check whether `rel` (a forward-slash relative path) matches any glob.

    A glob matches if the file's relative path matches it directly, or if any
    of its parent directories match it — so `storage/app/runs/*` excludes
    everything under `storage/app/runs/`, not just direct children.
    """
    import fnmatch

    for g in globs:
        if fnmatch.fnmatchcase(rel, g):
            return True
        # match parent directories so `foo/*` excludes `foo/a/b/c`.
        parts = rel.split("/")
        for i in range(1, len(parts)):
            prefix = "/".join(parts[:i]) + "/*"
            if fnmatch.fnmatchcase(prefix, g):
                return True
    return False


def walk_files(root: Path, exclude_globs: tuple[str, ...] = ()) -> list[Path]:
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for f in filenames:
            p = Path(dirpath) / f
            rel = p.relative_to(root).as_posix()
            if exclude_globs and is_excluded(rel, exclude_globs):
                continue
            out.append(p)
    return out


# ---------------------------------------------------------------- hygiene

TOP_LEVEL_FILES = {
    "readme": ["README.md", "README.rst", "README.txt", "README"],
    "contributing": ["CONTRIBUTING.md", "CONTRIBUTING.rst", "CONTRIBUTING"],
    "changelog": ["CHANGELOG.md", "CHANGES.md", "HISTORY.md"],
    "license": ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"],
    "code_of_conduct": ["CODE_OF_CONDUCT.md"],
    "security": ["SECURITY.md"],
}

QUICKSTART_PATTERNS = re.compile(
    r"^#+\s*(quick\s*start|getting\s*started|installation|install|usage)\b",
    re.IGNORECASE | re.MULTILINE,
)


def check_hygiene(root: Path, md_files: list[Path]) -> dict[str, Any]:
    found: dict[str, str | None] = {}
    for kind, candidates in TOP_LEVEL_FILES.items():
        hit = None
        for c in candidates:
            p = root / c
            if p.exists():
                hit = str(p.relative_to(root))
                break
        found[kind] = hit

    readme_info: dict[str, Any] = {"present": found["readme"] is not None}
    if found["readme"]:
        rp = root / found["readme"]
        try:
            text = rp.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        readme_info["lines"] = text.count("\n") + 1
        readme_info["has_quickstart"] = bool(QUICKSTART_PATTERNS.search(text))
        readme_info["bytes"] = len(text.encode("utf-8"))

    changelog_info: dict[str, Any] = {"present": found["changelog"] is not None}
    if found["changelog"]:
        cp = root / found["changelog"]
        try:
            mtime = cp.stat().st_mtime
        except OSError:
            mtime = 0
        changelog_info["mtime_age_days"] = int((NOW - mtime) / 86400) if mtime else None

    broken = check_internal_links(root, md_files)
    stale = check_stale(md_files)

    return {
        "files": found,
        "readme": readme_info,
        "changelog": changelog_info,
        "broken_links": broken,
        "stale_files": stale,
    }


LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
ANCHOR_RE = re.compile(r"^#+\s+(.+?)\s*$", re.MULTILINE)


def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    return s


def check_internal_links(root: Path, md_files: list[Path]) -> list[dict[str, str]]:
    anchor_index: dict[Path, set[str]] = {}
    for f in md_files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        anchor_index[f] = {slugify(m.group(1)) for m in ANCHOR_RE.finditer(text)}

    broken: list[dict[str, str]] = []
    for f in md_files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in LINK_RE.finditer(text):
            target = m.group(1)
            if target.startswith(("http://", "https://", "mailto:", "tel:")):
                continue
            if target.startswith("#"):
                anchor = slugify(target.lstrip("#"))
                if anchor and anchor not in anchor_index.get(f, set()):
                    broken.append(
                        {
                            "source": str(f.relative_to(root)),
                            "target": target,
                            "kind": "anchor",
                        }
                    )
                continue
            target_path, _, anchor = target.partition("#")
            if not target_path:
                continue
            try:
                resolved = (f.parent / target_path).resolve()
            except OSError:
                continue
            if not resolved.exists():
                broken.append(
                    {
                        "source": str(f.relative_to(root)),
                        "target": target,
                        "kind": "file",
                    }
                )
            elif anchor and resolved in anchor_index:
                if slugify(anchor) not in anchor_index[resolved]:
                    broken.append(
                        {
                            "source": str(f.relative_to(root)),
                            "target": target,
                            "kind": "anchor-in-file",
                        }
                    )
    return broken[:200]


def check_stale(md_files: list[Path]) -> list[dict[str, Any]]:
    stale: list[dict[str, Any]] = []
    for f in md_files:
        try:
            mtime = f.stat().st_mtime
        except OSError:
            continue
        age_days = (NOW - mtime) / 86400
        if age_days > STALE_DAYS:
            stale.append(
                {
                    "path": str(f),
                    "age_days": int(age_days),
                }
            )
    stale.sort(key=lambda x: -x["age_days"])
    return stale[:50]


# ---------------------------------------------------------------- diataxis

TUTORIAL_HINTS = ("tutorial", "getting-started", "quickstart", "intro", "first-")
HOWTO_HINTS = ("how-to", "howto", "guide", "recipe", "cookbook")
REFERENCE_HINTS = ("reference", "api", "spec", "schema", "config", "cli")
EXPLANATION_HINTS = ("concepts", "explanation", "background", "architecture", "why", "design")


def classify_diataxis(path: Path, text: str) -> tuple[str, str]:
    name = path.name.lower()
    parent = path.parent.name.lower()
    parts = (name + " " + parent).lower()

    score = {"tutorial": 0, "how-to": 0, "reference": 0, "explanation": 0}

    if any(h in parts for h in TUTORIAL_HINTS):
        score["tutorial"] += 3
    if any(h in parts for h in HOWTO_HINTS):
        score["how-to"] += 3
    if any(h in parts for h in REFERENCE_HINTS):
        score["reference"] += 3
    if any(h in parts for h in EXPLANATION_HINTS):
        score["explanation"] += 3

    head = text[:2000].lower()

    if re.search(r"^\s*(\d+\.|step\s*\d)", head, re.MULTILINE):
        score["tutorial"] += 2
    if re.search(r"\b(let'?s|you'?ll|by the end|first,|now,)\b", head):
        score["tutorial"] += 1
    if re.search(r"\bhow to\b", head):
        score["how-to"] += 2
    if re.search(r"^\|.+\|.+\|", head, re.MULTILINE):
        score["reference"] += 2
    if re.search(r"\b(parameter|argument|return|raises|throws|signature)\b", head):
        score["reference"] += 1
    if re.search(r"\b(why|because|the reason|trade-?off|principle|philosophy)\b", head):
        score["explanation"] += 2

    code_chars = sum(len(b) for b in re.findall(r"```.*?```", text, re.DOTALL))
    prose_chars = max(1, len(text) - code_chars)
    code_ratio = code_chars / (code_chars + prose_chars)
    if code_ratio > 0.6:
        score["reference"] += 1

    best = max(score, key=lambda k: score[k])
    if score[best] == 0:
        return "unknown", "low"
    second = sorted(score.values(), reverse=True)[1]
    confidence = (
        "high" if score[best] >= second + 2 else "medium" if score[best] > second else "low"
    )
    return best, confidence


def diataxis_audit(root: Path, md_files: list[Path]) -> dict[str, Any]:
    pages: list[dict[str, Any]] = []
    counts = {"tutorial": 0, "how-to": 0, "reference": 0, "explanation": 0, "unknown": 0}
    miscategorised: list[dict[str, str]] = []

    for f in md_files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if len(text.strip()) < 100:
            continue
        cat, conf = classify_diataxis(f, text)
        counts[cat] += 1
        rel = f.relative_to(root)
        pages.append(
            {
                "path": str(rel),
                "category": cat,
                "confidence": conf,
            }
        )

        parent = f.parent.name.lower()
        for hint_cat, hints in (
            ("tutorial", TUTORIAL_HINTS),
            ("how-to", HOWTO_HINTS),
            ("reference", REFERENCE_HINTS),
            ("explanation", EXPLANATION_HINTS),
        ):
            if any(h in parent for h in hints) and cat not in (hint_cat, "unknown"):
                miscategorised.append(
                    {
                        "path": str(rel),
                        "folder_says": hint_cat,
                        "content_says": cat,
                    }
                )
                break

    gaps = [k for k in ("tutorial", "how-to", "reference", "explanation") if counts[k] == 0]

    return {
        "counts": counts,
        "pages": pages[:200],
        "gaps": gaps,
        "miscategorised": miscategorised[:50],
    }


# ---------------------------------------------------------------- api coverage

PY_DEF_RE = re.compile(r"^(\s*)(async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.MULTILINE)
PY_CLASS_RE = re.compile(r"^(\s*)class\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)
TS_EXPORT_RE = re.compile(
    r"^export\s+(?:default\s+)?(?:async\s+)?(?:function|class|const|let|var|interface|type|enum)\s+([A-Za-z_$][\w$]*)",
    re.MULTILINE,
)
GO_EXPORT_RE = re.compile(
    r"^func\s+(?:\([^)]*\)\s+)?([A-Z][\w]*)\s*\(|^type\s+([A-Z][\w]*)\s|^var\s+([A-Z][\w]*)\s|^const\s+([A-Z][\w]*)\s",
    re.MULTILINE,
)
PHP_PUBLIC_FUNC_RE = re.compile(
    r"^\s*(?:(?:final|abstract)\s+)?(?:public\s+)?(?:static\s+)?function\s+([A-Za-z_][\w]*)\s*\(",
    re.MULTILINE,
)
PHP_PRIVATE_HINT_RE = re.compile(r"^\s*(?:private|protected)\s+", re.MULTILINE)
PHP_CLASS_RE = re.compile(
    r"^\s*(?:final\s+|abstract\s+)?(?:class|interface|trait|enum)\s+([A-Za-z_][\w]*)",
    re.MULTILINE,
)


def has_python_docstring(text: str, def_pos: int) -> bool:
    after = text[def_pos:]
    body = after.split(":", 1)
    if len(body) < 2:
        return False
    rest = body[1].lstrip("\r\n")
    rest = rest.lstrip(" \t")
    return rest.startswith(('"""', "'''", '"', "'"))


def has_jsdoc_above(text: str, pos: int) -> bool:
    head = text[:pos].rstrip()
    return head.endswith("*/") and "/**" in head[-400:]


def has_go_doc_above(text: str, pos: int) -> bool:
    head = text[:pos].rstrip().split("\n")
    for line in reversed(head[-5:]):
        if line.strip().startswith("//"):
            return True
        if line.strip() == "":
            continue
        return False
    return False


def has_phpdoc_above(text: str, pos: int) -> bool:
    head = text[:pos].rstrip()
    # Skip back over any PHP #[Attribute(...)] decorations that may sit
    # between the docblock and the symbol. PHP-CS-Fixer / Pint normalises
    # docblock-then-attribute order, so the chars immediately before a
    # symbol are often `]` rather than `*/`.
    while head.endswith("]"):
        stripped = _strip_trailing_php_attribute(head)
        if stripped is None:
            break
        head = stripped.rstrip()
    if not head.endswith("*/"):
        return False
    return "/**" in head[-600:]


def _strip_trailing_php_attribute(head: str) -> str | None:
    """Return `head` with a trailing `#[...]` attribute removed, or None.

    Walks back from the final `]`, tracking bracket depth so that
    multi-line attributes (e.g. `#[Foo([\n  'a', 'b',\n])]`) are
    consumed as a unit.
    """
    if not head.endswith("]"):
        return None
    depth = 0
    for i in range(len(head) - 1, -1, -1):
        c = head[i]
        if c == "]":
            depth += 1
        elif c == "[":
            depth -= 1
            if depth == 0:
                if i > 0 and head[i - 1] == "#":
                    return head[: i - 1]
                return None
    return None


def api_coverage(root: Path, exclude_globs: tuple[str, ...] = ()) -> dict[str, Any]:
    out: dict[str, Any] = {
        "python": {"public_symbols": 0, "documented": 0, "missing": []},
        "typescript": {"exported_symbols": 0, "documented": 0, "missing": []},
        "go": {"exported_symbols": 0, "documented": 0, "missing": []},
        "php": {"public_symbols": 0, "documented": 0, "missing": []},
    }
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for f in filenames:
            p = Path(dirpath) / f
            ext = p.suffix.lower()
            if ext not in CODE_EXTS:
                continue
            rel_posix = p.relative_to(root).as_posix()
            if exclude_globs and is_excluded(rel_posix, exclude_globs):
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = str(p.relative_to(root))

            if ext == ".py":
                for m in PY_DEF_RE.finditer(text):
                    name = m.group(3)
                    if name.startswith("_"):
                        continue
                    out["python"]["public_symbols"] += 1
                    if has_python_docstring(text, m.end()):
                        out["python"]["documented"] += 1
                    else:
                        out["python"]["missing"].append(f"{rel}::{name}")
                for m in PY_CLASS_RE.finditer(text):
                    name = m.group(2)
                    if name.startswith("_"):
                        continue
                    out["python"]["public_symbols"] += 1
                    after = text[m.end() :]
                    rest = after.split(":", 1)
                    if len(rest) > 1 and rest[1].lstrip().startswith(('"""', "'''")):
                        out["python"]["documented"] += 1
                    else:
                        out["python"]["missing"].append(f"{rel}::{name}")

            elif ext in (".ts", ".tsx", ".js", ".jsx"):
                for m in TS_EXPORT_RE.finditer(text):
                    name = m.group(1)
                    out["typescript"]["exported_symbols"] += 1
                    if has_jsdoc_above(text, m.start()):
                        out["typescript"]["documented"] += 1
                    else:
                        out["typescript"]["missing"].append(f"{rel}::{name}")

            elif ext == ".go":
                for m in GO_EXPORT_RE.finditer(text):
                    name = next((g for g in m.groups() if g), None)
                    if not name:
                        continue
                    out["go"]["exported_symbols"] += 1
                    if has_go_doc_above(text, m.start()):
                        out["go"]["documented"] += 1
                    else:
                        out["go"]["missing"].append(f"{rel}::{name}")

            elif ext == ".php":
                for m in PHP_CLASS_RE.finditer(text):
                    name = m.group(1)
                    out["php"]["public_symbols"] += 1
                    if has_phpdoc_above(text, m.start()):
                        out["php"]["documented"] += 1
                    else:
                        out["php"]["missing"].append(f"{rel}::{name}")
                for m in PHP_PUBLIC_FUNC_RE.finditer(text):
                    line_start = text.rfind("\n", 0, m.start()) + 1
                    line = text[line_start : m.end()]
                    if re.search(r"\b(private|protected)\b", line):
                        continue
                    name = m.group(1)
                    out["php"]["public_symbols"] += 1
                    if has_phpdoc_above(text, m.start()):
                        out["php"]["documented"] += 1
                    else:
                        out["php"]["missing"].append(f"{rel}::{name}")

    for lang in ("python", "typescript", "go", "php"):
        out[lang]["missing"] = out[lang]["missing"][:50]
        total_key = "public_symbols" if lang in ("python", "php") else "exported_symbols"
        total = out[lang][total_key]
        documented = out[lang]["documented"]
        out[lang]["coverage_pct"] = round(100 * documented / total, 1) if total else None

    return out


# ---------------------------------------------------------------- site mode


def site_audit(root: Path) -> dict[str, Any]:
    html_files = [p for p in walk_files(root) if p.suffix.lower() in (".html", ".htm")]
    if not html_files:
        return {"present": False}

    has_nav = False
    has_search = False
    has_prev_next = False
    has_toc = False
    page_count = len(html_files)

    for p in html_files[:50]:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        low = text.lower()
        if "<nav" in low or 'role="navigation"' in low:
            has_nav = True
        if (
            'type="search"' in low
            or "search" in low
            and ("docsearch" in low or 'role="searchbox"' in low)
        ):
            has_search = True
        if "prev" in low and "next" in low and ('rel="prev"' in low or 'class="prev' in low):
            has_prev_next = True
        if "table of contents" in low or 'class="toc"' in low or 'id="toc"' in low:
            has_toc = True

    return {
        "present": True,
        "page_count": page_count,
        "has_nav": has_nav,
        "has_search": has_search,
        "has_prev_next": has_prev_next,
        "has_toc": has_toc,
    }


# ---------------------------------------------------------------- agent readiness

AGENT_ENTRY_FILES = ["CLAUDE.md", "AGENTS.md", "CONTEXT.md", ".cursorrules", ".windsurfrules"]
ADR_DIRS = ["docs/adr", "docs/decisions", "doc/adr", "adr", "decisions"]

AMBIGUOUS_PHRASES = [
    r"\bthe (api|service|database|server|client|system)\b(?!\s+(?:foo|bar|named|called))",
    r"\bconfigure (it )?appropriately\b",
    r"\bas needed\b",
    r"\betc\.?\b",
    r"\bvarious\b",
    r"\bsomehow\b",
]

REAL_LOOKING_KEY = re.compile(r"\b(sk-[A-Za-z0-9]{10,}|AKIA[0-9A-Z]{12,}|ghp_[A-Za-z0-9]{20,})\b")
PLACEHOLDER_KEY = re.compile(r"<[A-Z_]+>|\{\{[A-Z_]+\}\}|YOUR[_-][A-Z_]+")
PYTHON_BLOCK = re.compile(r"```py(?:thon)?\s*\n(.*?)```", re.DOTALL)
SHELL_BLOCK = re.compile(r"```(?:sh|bash|shell|zsh|console)\s*\n(.*?)```", re.DOTALL)
ANY_FENCED = re.compile(r"```([A-Za-z0-9_-]*)\s*\n(.*?)```", re.DOTALL)


def agent_readiness(root: Path, md_files: list[Path]) -> dict[str, Any]:
    entry_points = [f for f in AGENT_ENTRY_FILES if (root / f).exists()]
    adrs = []
    for d in ADR_DIRS:
        p = root / d
        if p.exists() and p.is_dir():
            count = sum(1 for x in p.iterdir() if x.is_file() and x.suffix == ".md")
            if count:
                adrs.append({"path": d, "count": count})

    frontmatter_pages = 0
    bad_heading_pages: list[str] = []
    bare_blocks = 0
    total_blocks = 0
    likely_incomplete: list[dict[str, str]] = []
    copy_paste_findings: list[dict[str, str]] = []
    ambiguity_findings: list[dict[str, str]] = []

    for f in md_files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(f.relative_to(root))

        if text.startswith("---\n"):
            frontmatter_pages += 1

        h1s = re.findall(r"^#\s+", text, re.MULTILINE)
        if len(h1s) > 1:
            bad_heading_pages.append(rel)

        for m in ANY_FENCED.finditer(text):
            total_blocks += 1
            lang = m.group(1).strip()
            body = m.group(2)
            if not lang:
                bare_blocks += 1
            if body.count("\n") < 3 and ("..." in body or "# ..." in body):
                likely_incomplete.append({"path": rel, "snippet": body.strip()[:80]})
            if REAL_LOOKING_KEY.search(body):
                copy_paste_findings.append(
                    {
                        "path": rel,
                        "issue": "real-looking secret/key in code block",
                        "snippet": REAL_LOOKING_KEY.search(body).group(0)[:40],
                    }
                )

        for m in SHELL_BLOCK.finditer(text):
            body = m.group(1)
            if "cd " not in body and len(body.splitlines()) >= 2 and "/" in body:
                copy_paste_findings.append(
                    {
                        "path": rel,
                        "issue": "multi-line shell snippet without explicit cd",
                        "snippet": body.strip().splitlines()[0][:80],
                    }
                )
                break
        for m in PYTHON_BLOCK.finditer(text):
            body = m.group(1)
            if "import " not in body and re.search(r"^\s*\w+\.[a-z_]+\(", body, re.MULTILINE):
                copy_paste_findings.append(
                    {
                        "path": rel,
                        "issue": "python snippet uses module call without import",
                        "snippet": body.strip().splitlines()[0][:80] if body.strip() else "",
                    }
                )
                break

        for pat in AMBIGUOUS_PHRASES:
            for m in re.finditer(pat, text, re.IGNORECASE):
                ambiguity_findings.append(
                    {
                        "path": rel,
                        "phrase": m.group(0),
                    }
                )
                if len(ambiguity_findings) >= 50:
                    break

    return {
        "entry_points": entry_points,
        "adrs": adrs,
        "machine_readable": {
            "frontmatter_pages": frontmatter_pages,
            "pages_with_multiple_h1": bad_heading_pages[:20],
        },
        "examples": {
            "total_blocks": total_blocks,
            "bare_blocks": bare_blocks,
            "bare_ratio": round(bare_blocks / total_blocks, 2) if total_blocks else 0,
            "likely_incomplete": likely_incomplete[:20],
        },
        "copy_paste_findings": copy_paste_findings[:30],
        "ambiguity_findings": ambiguity_findings[:30],
    }


# ---------------------------------------------------------------- score


def score_audit(report: dict[str, Any], mode: str) -> tuple[int, list[dict[str, Any]]]:
    deductions: list[dict[str, Any]] = []
    score = 100

    h = report["hygiene"]
    if not h["readme"]["present"]:
        deductions.append({"reason": "README missing", "points": 20})
    else:
        if h["readme"].get("lines", 0) < 50 or not h["readme"].get("has_quickstart"):
            deductions.append({"reason": "README too short or missing quickstart", "points": 10})
    if not h["files"].get("contributing"):
        deductions.append({"reason": "CONTRIBUTING missing", "points": 5})
    if not h["files"].get("changelog"):
        deductions.append({"reason": "CHANGELOG missing", "points": 5})
    elif h["changelog"].get("mtime_age_days") and h["changelog"]["mtime_age_days"] > 365:
        deductions.append({"reason": "CHANGELOG > 1 year stale", "points": 5})
    if not h["files"].get("license"):
        deductions.append({"reason": "LICENSE missing", "points": 5})

    bl = len(h["broken_links"])
    if bl:
        pts = min(20, bl * 2)
        deductions.append({"reason": f"{bl} broken internal link(s)", "points": pts})

    inv = report["inventory"]
    md_total = inv["markdown_files"]
    stale = len(h["stale_files"])
    if md_total and stale / md_total > 0.25:
        deductions.append(
            {"reason": f">{int(100 * stale / md_total)}% of docs stale (>1 year)", "points": 10}
        )

    d = report["diataxis"]
    cap = 0
    for gap in d["gaps"]:
        if cap >= 15:
            break
        deductions.append({"reason": f"Diataxis category missing: {gap}", "points": 5})
        cap += 5
    if d["counts"] and sum(d["counts"].values()):
        if len(d["miscategorised"]) > 0.3 * sum(d["counts"].values()):
            deductions.append({"reason": ">30% of pages mis-categorised vs folder", "points": 10})

    api = report["api_coverage"]
    overall_total = sum(
        api[lang]["public_symbols" if lang in ("python", "php") else "exported_symbols"]
        for lang in ("python", "typescript", "go", "php")
    )
    overall_documented = sum(
        api[lang]["documented"] for lang in ("python", "typescript", "go", "php")
    )
    if overall_total:
        pct = 100 * overall_documented / overall_total
        if pct < 40:
            deductions.append({"reason": f"API doc coverage {pct:.0f}% (<40)", "points": 20})
        elif pct < 70:
            deductions.append({"reason": f"API doc coverage {pct:.0f}% (<70)", "points": 10})

    if mode == "site":
        s = report["site"]
        if s.get("present"):
            if not s.get("has_nav"):
                deductions.append({"reason": "Site has no navigation", "points": 10})
            if not s.get("has_search") and s.get("page_count", 0) > 20:
                deductions.append({"reason": "Site has no search and >20 pages", "points": 5})

    a = report["agent"]
    if not a["entry_points"]:
        deductions.append(
            {"reason": "No agent entry point (CLAUDE.md / AGENTS.md / CONTEXT.md)", "points": 10}
        )
    if not a["adrs"]:
        deductions.append({"reason": "No ADR directory found", "points": 5})
    if a["examples"]["total_blocks"] and a["examples"]["bare_ratio"] > 0.3:
        deductions.append({"reason": ">30% of code blocks have no language tag", "points": 5})
    if len(a["ambiguity_findings"]) > 5:
        deductions.append({"reason": ">5 ambiguity findings in prose", "points": 5})

    score = max(0, 100 - sum(d["points"] for d in deductions))
    return score, deductions


# ---------------------------------------------------------------- main


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--path", required=True, help="Directory to scan")
    ap.add_argument("--mode", choices=("project", "site"), default="project")
    ap.add_argument(
        "--check-links",
        action="store_true",
        help="HEAD-check external links (online; not yet implemented)",
    )
    ap.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help=(
            "Path glob to exclude from the scan (relative to --path, forward slashes). "
            "Repeatable. Adds to built-in defaults (storage/app/runs/*, "
            "storage/framework/*, storage/logs/*, tmp/*, temp/*). "
            "Pass --no-default-excludes to drop the built-ins."
        ),
    )
    ap.add_argument(
        "--no-default-excludes",
        action="store_true",
        help="Don't apply the built-in exclude globs.",
    )
    args = ap.parse_args()

    root = Path(args.path).resolve()
    if not root.exists() or not root.is_dir():
        print(json.dumps({"error": f"path not found or not a directory: {root}"}))
        return 1

    excludes: tuple[str, ...] = tuple(
        ([] if args.no_default_excludes else list(DEFAULT_EXCLUDE_GLOBS)) + list(args.exclude)
    )

    all_files = walk_files(root, excludes)
    md_files = [p for p in all_files if p.suffix.lower() in MD_EXTS]

    inventory = {
        "root": str(root),
        "total_files_scanned": len(all_files),
        "markdown_files": len(md_files),
        "code_files": sum(1 for p in all_files if p.suffix.lower() in CODE_EXTS),
        "exclude_globs": list(excludes),
    }

    report: dict[str, Any] = {
        "mode": args.mode,
        "inventory": inventory,
        "hygiene": check_hygiene(root, md_files),
        "diataxis": diataxis_audit(root, md_files),
        "api_coverage": api_coverage(root, excludes),
        "site": site_audit(root) if args.mode == "site" else {"present": False},
        "agent": agent_readiness(root, md_files),
    }

    score, deductions = score_audit(report, args.mode)
    report["score"] = score
    report["deductions"] = deductions

    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
