"""
helpers/reconcile/classify.py

Step 2 of the reconcile loop. Categorize observed changes.

Two main classification operations:
1. PR/item type classification (feature, bugfix, breaking, etc.)
2. Artifact change classification (editorial, substantive, structural)

The pipeline is mechanical-first then LLM:
- Mechanical signals from `config.classification.{type,area}_triggers`
  produce a tentative label.
- For artifact change classifications where mechanical signals are
  ambiguous (or for spec amendments where `ai_usage.spec_amendment_classify:
  always_llm`), call the LLM with the diff and rubric.
- Honor any prior `/reclassify` overrides.
"""

from __future__ import annotations

import logging
from pathlib import Path
import re
from typing import Literal

logger = logging.getLogger(__name__)

ChangeClass = Literal["editorial", "substantive", "structural"]
ItemType = Literal["feature", "bugfix", "breaking", "refactor", "docs", "dependency", "chore"]


def classify_pr_type(pr: dict, config: dict) -> str:
    """
    Classify a PR's type using config-defined triggers.
    """
    triggers = config.get("classification", {}).get("type_triggers", {})
    title = (pr.get("title") or "").lower()
    branch = pr.get("head", {}).get("ref", "")
    labels = [lbl.lower() for lbl in pr.get("labels", [])]

    # Manual label takes precedence
    for type_name, cfg in triggers.items():
        if any(lbl == f"type:{type_name}" for lbl in labels):
            return type_name

    # Title keyword match
    for type_name, cfg in triggers.items():
        keywords = cfg.get("keywords_in_title", [])
        if any(kw.lower() in title for kw in keywords):
            return type_name

    # Branch prefix match
    for type_name, cfg in triggers.items():
        prefixes = cfg.get("branch_prefixes", [])
        if any(branch.startswith(p) for p in prefixes):
            return type_name

    # Path-based fallback
    files = pr.get("files", [])
    for type_name, cfg in triggers.items():
        path_patterns = cfg.get("paths", [])
        if any(any(_match_glob(f, p) for p in path_patterns) for f in files):
            return type_name

    # Default
    return "chore"


def classify_pr_areas(pr: dict, config: dict) -> list[str]:
    """
    Classify a PR's areas (multi-applicable). Path patterns and diff
    keywords from area_triggers.
    """
    triggers = config.get("classification", {}).get("area_triggers", {})
    files = pr.get("files", [])
    diff_text = pr.get("diff_summary", "")

    matched: list[str] = []
    for area_name, cfg in triggers.items():
        path_patterns = cfg.get("paths", [])
        if any(any(_match_glob(f, p) for p in path_patterns) for f in files):
            matched.append(area_name)
            continue
        keywords = cfg.get("keywords_in_diff", [])
        if any(kw in diff_text for kw in keywords):
            matched.append(area_name)

    return matched


def run(config: dict, observed: dict) -> dict:
    """CLI compatibility wrapper for observed artifact classification."""
    classifications: dict = {}
    for art in observed.get("artifacts", []):
        if not art.get("changed"):
            continue
        path = Path(art["path"])
        after = path.read_text() if path.exists() else ""
        cls = classify_artifact_change(
            diff="",
            artifact_content_before=None,
            artifact_content_after=after,
            config=config,
        )
        classifications[f"artifact:{art['type']}:{art['id']}"] = cls
    return classifications


def classify_artifact_change(
    diff: str,
    artifact_content_before: str | None,
    artifact_content_after: str,
    config: dict,
    prior_override: ChangeClass | None = None,
) -> dict:
    """
    Classify an artifact change as editorial / substantive / structural.

    Returns:
        {
          "classification": "editorial" | "substantive" | "structural",
          "rationale": str,
          "method": "override" | "mechanical" | "llm",
        }
    """
    # Honor prior override
    if prior_override:
        return {
            "classification": prior_override,
            "rationale": "prior /reclassify override",
            "method": "override",
        }

    # Structural detection (mechanical)
    if _is_structural_change(artifact_content_before, artifact_content_after):
        return {
            "classification": "structural",
            "rationale": "front-matter id or supersedes field changed",
            "method": "mechanical",
        }

    # Mechanical pre-pass
    mechanical_signal = _mechanical_classify(diff)

    ai_policy = config.get("ai_usage", {}).get("spec_amendment_classify", "always_llm")

    if ai_policy == "mechanical_only":
        return {
            "classification": mechanical_signal["class"],
            "rationale": mechanical_signal["rationale"],
            "method": "mechanical",
        }

    # Otherwise, LLM judgment
    return classify_with_llm(diff, artifact_content_after, mechanical_signal)


def _is_structural_change(before: str | None, after: str) -> bool:
    """Detect supersession or id change via front-matter."""
    if before is None:
        return True  # net-new artifact: structural
    before_fm = _read_front_matter(before)
    after_fm = _read_front_matter(after)
    if before_fm.get("id") != after_fm.get("id"):
        return True
    if before_fm.get("supersedes") != after_fm.get("supersedes"):
        return True
    return False


def _read_front_matter(content: str) -> dict:
    """Extract YAML front-matter."""
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    import yaml

    try:
        return yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}


def _mechanical_classify(diff: str) -> dict:
    """
    Quick heuristic classification from diff stats.
    Used as input signal to LLM, or as final answer in mechanical_only.
    """
    lines = diff.splitlines()
    additions = sum(1 for line in lines if line.startswith("+") and not line.startswith("+++"))
    deletions = sum(1 for line in lines if line.startswith("-") and not line.startswith("---"))
    total = additions + deletions

    # Touching code blocks or front-matter is more likely substantive
    in_code_block = any(re.match(r"[+-]```", line) for line in lines)
    front_matter_changed = any(
        re.match(r"[+-](?!--)", line) and "---" in line
        for line in lines[:30]  # front matter is at the top
    )

    if total < 5 and not in_code_block and not front_matter_changed:
        return {
            "class": "editorial",
            "rationale": f"small diff ({total} lines, no code/front-matter)",
        }
    if total < 20 and not in_code_block:
        return {
            "class": "editorial",
            "rationale": f"small prose-only diff ({total} lines)",
            "ambiguous": True,
        }

    return {
        "class": "substantive",
        "rationale": f"larger or structural diff ({total} lines, code={in_code_block})",
    }


def classify_with_llm(diff: str, content: str, mechanical_signal: dict) -> dict:
    """
    Call the LLM with the rubric. Implementation depends on the
    runtime — here we expect an `LLM_CALL` callable provided by the
    runtime, or a fallback to the mechanical signal.
    """
    rubric = """
    Classify the artifact change as one of:

    EDITORIAL — surface-level changes that don't alter behavior, contracts,
      or design. Typos, formatting, clearer wording with same meaning.

    SUBSTANTIVE — changes that alter behavior, contracts, design choices,
      acceptance criteria, scope, or any decision downstream artifacts depend on.
      Default to substantive when in doubt.

    STRUCTURAL — wholesale replacement, supersession, or fundamental rewrite.

    Return JSON: { "classification": "...", "rationale": "..." }
    """

    try:
        from ..llm import classify_via_llm  # provided by runtime

        return {
            **classify_via_llm(diff=diff, content=content, rubric=rubric, hint=mechanical_signal),
            "method": "llm",
        }
    except ImportError:
        # No LLM available; fall back to mechanical
        return {
            "classification": mechanical_signal["class"],
            "rationale": f"{mechanical_signal['rationale']} (LLM unavailable)",
            "method": "mechanical",
        }


def _match_glob(path: str, pattern: str) -> bool:
    """Match a path against a glob pattern (with ** support)."""
    import fnmatch

    if "**" in pattern:
        # Convert ** to a regex equivalent
        regex = re.escape(pattern).replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
        return bool(re.match(regex + r"$", path))
    return fnmatch.fnmatch(path, pattern)
