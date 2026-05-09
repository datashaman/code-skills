"""
helpers/reconcile/apply.py

Step 3 of the reconcile loop. Idempotent writes to .workflow/ based
on observations and classifications.

Apply does NOT call the provider. It only writes the folder. Provider
calls happen in cascade.py and provider-action helpers, which the
checkpoint coordinates.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

WORKFLOW_DIR = Path(".workflow")
ARTIFACTS_DIR = WORKFLOW_DIR / "artifacts"
LIFECYCLE_DIR = WORKFLOW_DIR / "lifecycle" / "active"


def apply(observation: dict, classifications: dict, config: dict) -> dict:
    """
    Build and execute the apply plan.

    Returns:
        applied: {
          "sidecars_written": [...],
          "lifecycle_updated": [...],
          "front_matter_synced": [...],
        }
    """
    plan = build_apply_plan(observation, classifications, config)
    applied = {"sidecars_written": [], "lifecycle_updated": [], "front_matter_synced": []}

    for change in plan.get("artifact_changes", []):
        write_artifact_sidecar(change)
        applied["sidecars_written"].append(change["id"])
        if change.get("front_matter_sync"):
            sync_front_matter(change)
            applied["front_matter_synced"].append(change["id"])

    for change in plan.get("lifecycle_changes", []):
        write_lifecycle_sidecar(change)
        applied["lifecycle_updated"].append(f"{change['type']}/{change['id']}")

    return applied


def run(config: dict, observed: dict, classification: dict, session: Any | None = None) -> dict:
    """CLI compatibility wrapper for the apply phase."""
    applied = apply(observed, classification, config)
    if session is not None:
        for artifact_id in applied.get("sidecars_written", []):
            session.record_artifact_change(artifact_id, "sidecar written")
        for item_id in applied.get("lifecycle_updated", []):
            session.record_lifecycle_change(item_id, "sidecar updated")
        if classification:
            session.set_classification(next(iter(classification.values())))
    return applied


def dry_run(config: dict, observed: dict, classification: dict) -> dict:
    """Return the apply plan without writing files."""
    plan = build_apply_plan(observed, classification, config)
    changes = []
    for change in plan.get("artifact_changes", []):
        changes.append(
            {
                "op": "write",
                "path": str(ARTIFACTS_DIR / f"{change['type']}s" / f"{change['id']}.yml"),
                "summary": "artifact sidecar",
            }
        )
    for change in plan.get("lifecycle_changes", []):
        changes.append(
            {
                "op": "write",
                "path": str(LIFECYCLE_DIR / f"{change['type']}-{change['id']}.yml"),
                "summary": "lifecycle sidecar",
            }
        )
    return {"changes": changes, "plan": plan}


def build_apply_plan(observation: dict, classifications: dict, config: dict) -> dict:
    """
    Compute desired sidecar updates from observations + classifications.
    """
    plan: dict = {"artifact_changes": [], "lifecycle_changes": []}

    for art in observation.get("artifacts", []):
        if not art["changed"]:
            continue
        cls = classifications.get(f"artifact:{art['type']}:{art['id']}")
        artifact_cfg = config.get("artifacts", {}).get(art["type"], {})

        change = {
            "type": art["type"],
            "id": art["id"],
            "path": art["path"],
            "new_hash": art["current_hash"],
            "classification": cls.get("classification") if cls else None,
            "front_matter_sync": artifact_cfg.get("front_matter_sync", False),
            "previous_sidecar": art["sidecar"],
        }
        plan["artifact_changes"].append(change)

    for item in observation.get("lifecycle_items", []):
        # Compute target stage and labels based on current observation
        # (the heavy logic lives in lifecycle.py — this is just the write layer)
        if item.get("target_stage") and item["target_stage"] != item.get("current_stage"):
            plan["lifecycle_changes"].append(
                {
                    "type": item["type"],
                    "id": item["id"],
                    "new_stage": item["target_stage"],
                    "new_labels": item.get("target_labels", []),
                    "previous_sidecar": item["sidecar"],
                }
            )

    return plan


def write_artifact_sidecar(change: dict) -> None:
    """Update or create the artifact sidecar."""
    sidecar_path = ARTIFACTS_DIR / f"{change['type']}s" / f"{change['id']}.yml"
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)

    sidecar = dict(change.get("previous_sidecar") or {})
    sidecar["id"] = change["id"]
    sidecar["file"] = change["path"]
    sidecar["content_hash"] = change["new_hash"]
    sidecar["last_observed"] = _now_iso()
    if change.get("classification"):
        sidecar["last_change_classification"] = change["classification"]
    sidecar["revision"] = (sidecar.get("revision") or 0) + 1

    with sidecar_path.open("w") as f:
        yaml.dump(sidecar, f, sort_keys=False)


def sync_front_matter(change: dict) -> None:
    """
    Update the markdown's front-matter to mirror sidecar fields.
    Called only when front_matter_sync is true for the artifact type.
    """
    import re

    path = Path(change["path"])
    if not path.exists():
        return
    content = path.read_text()

    # Sidecar is the source of truth here
    sidecar_path = ARTIFACTS_DIR / f"{change['type']}s" / f"{change['id']}.yml"
    with sidecar_path.open() as f:
        sidecar = yaml.safe_load(f) or {}

    fm_block = (
        "---\n"
        + yaml.dump(
            {
                "id": sidecar.get("id"),
                "title": sidecar.get("title"),
                "state": sidecar.get("state"),
                "last_updated": _now_iso()[:10],
            },
            sort_keys=False,
        )
        + "---\n"
    )

    if re.match(r"^---\n.*?\n---\n", content, re.DOTALL):
        new_content = re.sub(r"^---\n.*?\n---\n", fm_block, content, count=1, flags=re.DOTALL)
    else:
        new_content = fm_block + content

    path.write_text(new_content)


def write_lifecycle_sidecar(change: dict) -> None:
    """Update or create the lifecycle sidecar."""
    sidecar_path = LIFECYCLE_DIR / f"{change['type']}-{change['id']}.yml"
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)

    sidecar = dict(change.get("previous_sidecar") or {})
    sidecar["type"] = change["type"]
    sidecar["id"] = change["id"]

    if "new_stage" in change:
        sidecar["stage_history"] = sidecar.get("stage_history", [])
        if sidecar.get("stage") != change["new_stage"]:
            sidecar["stage_history"].append(
                {
                    "from": sidecar.get("stage"),
                    "to": change["new_stage"],
                    "at": _now_iso(),
                }
            )
        sidecar["stage"] = change["new_stage"]

    if "new_labels" in change:
        sidecar["target_labels"] = change["new_labels"]

    sidecar["last_observed"] = _now_iso()

    with sidecar_path.open("w") as f:
        yaml.dump(sidecar, f, sort_keys=False)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
