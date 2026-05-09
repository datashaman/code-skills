"""
Minimal simulation helpers for the workflow-advisor CLI.

These functions intentionally stay read-only. They give contributors a
stable smoke path while the richer event replay machinery is still being
implemented.
"""

from __future__ import annotations

import json
from typing import Any


def simulate_event(config: dict, event_name: str, **event_args: Any) -> dict:
    return {
        "mode": "event",
        "event_name": event_name,
        "event_args": event_args,
        "repo": config.get("repo", {}).get("identifier"),
    }


def replay_event(config: dict, run_id: str, at_stage: str | None = None) -> dict:
    return {
        "mode": "replay",
        "run_id": run_id,
        "at_stage": at_stage,
        "status": "not_implemented",
    }


def config_diff(config: dict, from_ref: str, to_ref: str | None, event_range: str) -> dict:
    return {
        "mode": "config-diff",
        "from_ref": from_ref,
        "to_ref": to_ref,
        "event_range": event_range,
        "status": "not_implemented",
    }


def format_result(result: dict, format: str = "text") -> str:
    if format == "json":
        return json.dumps(result, indent=2)
    lines = [f"Simulation: {result.get('mode')}"]
    for key, value in result.items():
        if key == "mode":
            continue
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)
