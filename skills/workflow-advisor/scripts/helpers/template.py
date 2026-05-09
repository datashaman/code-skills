"""
helpers/template.py

Render skill templates with placeholder substitution.

Templates are markdown files in `.workflow/templates/` (per repo) or
`references/templates/` (skill defaults). They use a small placeholder
syntax:

  {{ id }}             — substitute a value
  {{ id | default }}   — with a default fallback
  {{ if section }}...{{ end }}   — conditional block

For most uses, this is enough. We avoid pulling in Jinja2 to keep the
skill's runtime footprint small.
"""

from __future__ import annotations

import logging
from pathlib import Path
import re
from typing import Any

logger = logging.getLogger(__name__)


PLACEHOLDER_RE = re.compile(r"\{\{\s*([\w.]+)(?:\s*\|\s*([^}]+))?\s*\}\}")
IF_BLOCK_RE = re.compile(
    r"\{\{\s*if\s+([\w.]+)\s*\}\}(.*?)\{\{\s*end\s*\}\}",
    re.DOTALL,
)


def render(template_path: Path | str, context: dict) -> str:
    """Render a template file with the given context."""
    path = Path(template_path)
    return render_string(path.read_text(), context)


def render_string(template: str, context: dict) -> str:
    """Render a template string with the given context."""

    # Resolve conditional blocks first
    def resolve_if(m: re.Match) -> str:
        key = m.group(1)
        body = m.group(2)
        if _resolve_key(key, context):
            return body
        return ""

    template = IF_BLOCK_RE.sub(resolve_if, template)

    # Then placeholders
    def resolve_placeholder(m: re.Match) -> str:
        key = m.group(1)
        default = m.group(2) or ""
        value = _resolve_key(key, context)
        if value is None:
            return default.strip()
        return str(value)

    return PLACEHOLDER_RE.sub(resolve_placeholder, template)


def _resolve_key(key: str, context: dict) -> Any:
    """Walk a dotted key into nested context."""
    value: Any = context
    for part in key.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
        if value is None:
            return None
    return value


def find_template(name: str, profile: str | None = None) -> Path:
    """
    Find a template by name. Prefers the repo's `.workflow/templates/`,
    falls back to the skill's bundled `references/templates/`.
    """
    candidates = []
    if profile:
        candidates.append(Path(".workflow/templates") / profile / name)
    candidates.append(Path(".workflow/templates") / name)
    candidates.append(Path("references/templates") / name)

    for c in candidates:
        if c.exists():
            return c

    raise FileNotFoundError(f"Template {name!r} not found in any standard location")
