"""
helpers/reconcile/log.py

Step 5 of the reconcile loop. Append decision log entries and metrics
events.

Two log streams:
- Decisions log (`.workflow/decisions/{YYYY-MM-DD}.md`) — for humans.
  Markdown. One file per UTC day.
- Metrics events (`.workflow/metrics/events.jsonl`) — for machines.
  JSONL, append-only.

Whether either is committed to git or gitignored is controlled by the
`observability_reports` config block. Compliance profile forces both
to be committed.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DECISIONS_DIR = Path(".workflow/decisions")
METRICS_DIR = Path(".workflow/metrics")
EVENTS_FILE = METRICS_DIR / "events.jsonl"


def log_decisions(
    observation: dict,
    classifications: dict,
    apply_result: dict,
    cascade_result: dict,
    context: dict,
) -> list[str]:
    """
    Append decision entries for non-trivial actions in this reconcile pass.

    Returns the list of decision IDs created.
    """
    DECISIONS_DIR.mkdir(parents=True, exist_ok=True)
    today_file = DECISIONS_DIR / f"{_today_iso()}.md"

    entries: list[dict] = []

    # Classifications worth logging
    for key, cls in (classifications or {}).items():
        if cls.get("method") == "llm" or cls.get("method") == "override":
            entries.append(
                {
                    "kind": "classification",
                    "subject": key,
                    "classification": cls.get("classification"),
                    "rationale": cls.get("rationale"),
                    "method": cls.get("method"),
                }
            )

    # Cascades
    for action in cascade_result.get("applied", []):
        entries.append(
            {
                "kind": "cascade",
                "target": action.get("target"),
                "action": action.get("action"),
                "reason": action.get("reason"),
            }
        )

    # In-flight conflicts
    for conflict in cascade_result.get("in_flight_conflicts", []):
        entries.append(
            {
                "kind": "in_flight_conflict",
                "source": conflict.get("source"),
                "conflict_with": conflict.get("conflict_with"),
                "would_have_done": conflict.get("would_have_done"),
                "resolution": "label_and_notify",
            }
        )

    if not entries:
        return []

    decision_ids = []
    next_id = _next_decision_id(today_file)
    with today_file.open("a") as f:
        if today_file.stat().st_size == 0:
            f.write(f"# Decisions — {_today_iso()}\n\n")

        for entry in entries:
            decision_id = f"decision-{next_id}"
            decision_ids.append(decision_id)
            next_id += 1

            f.write(f"## {decision_id}: {_summarize(entry)}\n\n")
            for k, v in entry.items():
                if k == "kind":
                    continue
                f.write(f"**{k.replace('_', ' ').title()}:** {v}\n")
            f.write(f"**Logged at:** {_now_iso()}\n\n")

    return decision_ids


def log_metrics(
    observation: dict,
    classifications: dict,
    apply_result: dict,
    cascade_result: dict,
    context: dict,
) -> None:
    """Append structured event records for metrics computation."""
    METRICS_DIR.mkdir(parents=True, exist_ok=True)

    event = {
        "ts": _now_iso(),
        "scope": observation.get("scope"),
        "trigger_event": context.get("event", {}).get("name"),
        "artifacts_observed": len(observation.get("artifacts", [])),
        "artifacts_changed": sum(1 for a in observation.get("artifacts", []) if a.get("changed")),
        "lifecycle_items_observed": len(observation.get("lifecycle_items", [])),
        "classifications": {k: v.get("classification") for k, v in (classifications or {}).items()},
        "sidecars_written": len(apply_result.get("sidecars_written", [])),
        "lifecycle_updated": len(apply_result.get("lifecycle_updated", [])),
        "cascades_applied": len(cascade_result.get("applied", [])),
        "cascades_failed": len(cascade_result.get("failed", [])),
        "in_flight_conflicts": len(cascade_result.get("in_flight_conflicts", [])),
    }

    with EVENTS_FILE.open("a") as f:
        f.write(json.dumps(event) + "\n")


def run(
    config: dict,
    event: dict | None,
    observed: dict,
    classification: dict,
    applied: dict,
    cascaded: dict,
    session: Any | None = None,
) -> dict:
    """CLI compatibility wrapper for the log phase."""
    context = {"config": config, "event": event or {}}
    decision_ids = log_decisions(observed, classification, applied, cascaded, context)
    log_metrics(observed, classification, applied, cascaded, context)
    if session is not None and decision_ids:
        state_dir = session.workflow_dir / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "last_decision_ref.txt").write_text(decision_ids[-1] + "\n")
    return {"decision_ids": decision_ids}


def _summarize(entry: dict) -> str:
    """One-line summary for a decision entry's heading."""
    kind = entry.get("kind")
    if kind == "classification":
        return f"{entry.get('subject')} classified as {entry.get('classification')}"
    if kind == "cascade":
        target = entry.get("target", {})
        return f"cascade {entry.get('action')} on {target.get('type')}/{target.get('id')}"
    if kind == "in_flight_conflict":
        return f"in-flight conflict preserved: {entry.get('conflict_with')}"
    return f"{kind}"


def _next_decision_id(today_file: Path) -> int:
    """Find the next available decision-N number in today's file."""
    if not today_file.exists():
        return 1
    import re

    content = today_file.read_text()
    matches = re.findall(r"## decision-(\d+):", content)
    if not matches:
        return 1
    return max(int(m) for m in matches) + 1


def _today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
