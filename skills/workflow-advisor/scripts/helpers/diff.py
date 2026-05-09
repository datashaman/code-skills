"""
helpers/diff.py

Unified diff rendering for proposals.

Used when:
- Bootstrap proposes provider config files (.github/...) and shows diffs.
- Reconcile dry-run renders the would-be sidecar changes.
- Cascade plans surface to users for confirmation.
"""

from __future__ import annotations

import difflib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def unified(
    before: str,
    after: str,
    label_before: str = "before",
    label_after: str = "after",
    context: int = 3,
) -> str:
    """Render a unified diff."""
    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)
    diff_lines = difflib.unified_diff(
        before_lines,
        after_lines,
        fromfile=label_before,
        tofile=label_after,
        n=context,
    )
    return "".join(diff_lines)


def file_diff(before_path: Path | str | None, after_path: Path | str) -> str:
    """Diff two files. If `before_path` is None, treat as new file."""
    after_text = Path(after_path).read_text() if Path(after_path).exists() else ""
    before_text = ""
    label_before = "/dev/null"
    if before_path is not None and Path(before_path).exists():
        before_text = Path(before_path).read_text()
        label_before = str(before_path)
    return unified(before_text, after_text, label_before, str(after_path))


def proposal_summary(
    proposals: list[dict],
) -> str:
    """
    Render a list of file proposals as a compact summary suitable for
    display before "apply or skip" confirmation.

    Each proposal: { path, before_text?, after_text }
    """
    out: list[str] = []
    for p in proposals:
        before = p.get("before_text") or ""
        after = p.get("after_text") or ""
        path = p.get("path", "<unknown>")
        if not before:
            out.append(f"NEW FILE: {path} ({len(after.splitlines())} lines)")
            continue
        diff = unified(before, after, f"a/{path}", f"b/{path}")
        out.append(diff)
    return "\n\n".join(out)
