"""
Small state-file helpers for workflow-advisor.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def load_processed_events(path: Path | str) -> set[str]:
    target = Path(path)
    if not target.exists():
        return set()
    with target.open() as f:
        data = yaml.safe_load(f) or []
    if isinstance(data, dict):
        data = data.get("events", [])
    return {str(item) for item in data}


def save_processed_events(path: Path | str, events: set[str]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w") as f:
        yaml.dump({"events": sorted(events)}, f, sort_keys=False)
