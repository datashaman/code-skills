"""
helpers/llm.py

Thin wrapper over the Anthropic API for the LLM judgments the skill
needs. Used in:

- Artifact change classification (substantive vs editorial vs structural).
- Subjective gate evaluation (when explicitly enabled).
- Comment drafting when the policy is `llm` instead of template.

Cost discipline matters. Most reconcile passes don't call this. The
wrapper:

- Reads ANTHROPIC_API_KEY from the environment.
- Uses Sonnet by default; configurable per call.
- Returns structured outputs by post-parsing.
- Falls back gracefully if the API isn't reachable.
"""

from __future__ import annotations

import json
import logging
import os
import re

logger = logging.getLogger(__name__)


DEFAULT_MODEL = "claude-sonnet-4-20250514"
API_URL = "https://api.anthropic.com/v1/messages"


class LLMUnavailable(Exception):
    """Raised when LLM call cannot be made (no API key, network failure)."""


def classify_via_llm(
    diff: str,
    content: str,
    rubric: str,
    hint: dict | None = None,
    model: str = DEFAULT_MODEL,
) -> dict:
    """
    Run a classification call. Used by reconcile.classify for ambiguous
    artifact changes.

    Returns:
        { "classification": str, "rationale": str }

    Raises:
        LLMUnavailable on API failure.
    """
    prompt = (
        f"{rubric}\n\n"
        f"Mechanical hint (use as input, not as final answer): {json.dumps(hint or {})}\n\n"
        f"Current artifact content:\n```\n{content[:6000]}\n```\n\n"
        f"Diff:\n```diff\n{diff[:6000]}\n```\n\n"
        f"Respond with only a JSON object: "
        f'{{ "classification": "editorial" | "substantive" | "structural", "rationale": "..." }}'
    )

    response_text = _call_api(prompt, model=model)
    return _parse_classification(response_text)


def draft_comment(
    purpose: str,
    context: dict,
    model: str = DEFAULT_MODEL,
) -> str:
    """
    Draft a comment body for a given purpose. Used by playbooks when the
    `comment_drafting` policy is `llm`.
    """
    prompt = (
        f"Draft a brief PR/issue comment.\n\n"
        f"Purpose: {purpose}\n\n"
        f"Context:\n{json.dumps(context, indent=2)}\n\n"
        f"Constraints: Be concise. Be specific. Don't be saccharine. "
        f"Don't apologize. Use Markdown. ~100 words or less."
    )
    return _call_api(prompt, model=model).strip()


def _call_api(prompt: str, model: str) -> str:
    """Make a single Anthropic API call. Returns the text content."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise LLMUnavailable("ANTHROPIC_API_KEY environment variable not set")

    try:
        import urllib.error
        import urllib.request

        body = json.dumps(
            {
                "model": model,
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
            }
        ).encode()

        req = urllib.request.Request(
            API_URL,
            data=body,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read())

        # Extract the first text block
        for block in payload.get("content", []):
            if block.get("type") == "text":
                return block.get("text", "")
        return ""

    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
        raise LLMUnavailable(f"API call failed: {e}")


def _parse_classification(text: str) -> dict:
    """Extract the classification JSON from the model's response."""
    # Find a JSON block; the model may add prose around it
    match = re.search(r"\{[^{}]*\"classification\"[^{}]*\}", text, re.DOTALL)
    if not match:
        # Fallback: assume substantive if the LLM gave us nothing parseable
        return {"classification": "substantive", "rationale": "LLM response unparseable"}

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"classification": "substantive", "rationale": "LLM response invalid JSON"}
