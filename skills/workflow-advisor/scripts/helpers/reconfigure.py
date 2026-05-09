"""
Dry-run-first reconfiguration helpers.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from helpers import config_io


def profile_change(config: dict, profile: str, enabled: bool) -> dict:
    """Return a structured profile enable/disable diff."""
    if profile not in config_io.KNOWN_PROFILES:
        raise ValueError(f"Unknown profile {profile!r}")

    before = bool(config.get("profiles", {}).get(profile, {}).get("enabled", False))
    after_config = deepcopy(config)
    after_config.setdefault("profiles", {}).setdefault(profile, {})["enabled"] = enabled

    return {
        "kind": "profile_change",
        "profile": profile,
        "before": before,
        "after": enabled,
        "changed": before != enabled,
        "config": after_config,
        "summary": f"{profile}: {'enabled' if before else 'disabled'} -> {'enabled' if enabled else 'disabled'}",
    }


def apply(diff: dict, path: Path | str | None = None) -> None:
    """Apply a config diff produced by this module."""
    if diff.get("kind") != "profile_change":
        raise ValueError(f"Unsupported reconfigure diff kind: {diff.get('kind')}")
    config_io.save(diff["config"], path=path)


def format_diff(diff: dict) -> str:
    """Render a compact JSON diff for CLI output."""
    return json.dumps(
        {
            "kind": diff.get("kind"),
            "profile": diff.get("profile"),
            "before": diff.get("before"),
            "after": diff.get("after"),
            "changed": diff.get("changed"),
            "summary": diff.get("summary"),
        },
        indent=2,
    )
