"""
helpers/lifecycle_store.py

Read and write lifecycle sidecars. Sidecars live at
`.workflow/lifecycle/active/{type}-{id}.yml` while items are open, and
move to `.workflow/lifecycle/archive/{type}/{id}.yml` on terminal
state.

Lifecycle items are PRs and issues. The sidecar tracks the item's
current stage, label state, gate evaluations, linked artifacts, and
stage history.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
import shutil

import yaml

logger = logging.getLogger(__name__)

ACTIVE_DIR = Path(".workflow/lifecycle/active")
ARCHIVE_DIR = Path(".workflow/lifecycle/archive")


def load(item_type: str, item_id: int | str) -> dict | None:
    """Load a lifecycle sidecar from active or archive."""
    path = active_path(item_type, item_id)
    if path.exists():
        with path.open() as f:
            return yaml.safe_load(f) or {}
    archive = archive_path(item_type, item_id)
    if archive.exists():
        with archive.open() as f:
            return yaml.safe_load(f) or {}
    return None


def save(item_type: str, item_id: int | str, sidecar: dict) -> None:
    """Save to active dir."""
    path = active_path(item_type, item_id)
    path.parent.mkdir(parents=True, exist_ok=True)

    sidecar.setdefault("type", item_type)
    sidecar.setdefault("id", item_id)
    sidecar["last_observed"] = _now_iso()

    tmp = path.with_suffix(".yml.tmp")
    with tmp.open("w") as f:
        yaml.dump(sidecar, f, sort_keys=False, default_flow_style=False)
    tmp.replace(path)


def update_stage(item_type: str, item_id: int | str, new_stage: str, reason: str = "") -> dict:
    """Move an item to a new stage, recording history."""
    sidecar = load(item_type, item_id) or {"type": item_type, "id": item_id}
    old_stage = sidecar.get("stage")

    if old_stage != new_stage:
        history = sidecar.setdefault("stage_history", [])
        history.append(
            {
                "from": old_stage,
                "to": new_stage,
                "at": _now_iso(),
                "reason": reason,
            }
        )
        sidecar["stage"] = new_stage

    save(item_type, item_id, sidecar)
    return sidecar


def archive(item_type: str, item_id: int | str, reason: str = "closed") -> Path:
    """Move active sidecar to archive. Returns the archive path."""
    src = active_path(item_type, item_id)
    if not src.exists():
        return archive_path(item_type, item_id)

    dst = archive_path(item_type, item_id)
    dst.parent.mkdir(parents=True, exist_ok=True)

    sidecar = load(item_type, item_id) or {}
    sidecar["archived_at"] = _now_iso()
    sidecar["archive_reason"] = reason

    with dst.open("w") as f:
        yaml.dump(sidecar, f, sort_keys=False)
    src.unlink()

    return dst


def restore_from_archive(item_type: str, item_id: int | str) -> dict | None:
    """Move archived sidecar back to active (used on PR/issue reopen)."""
    src = archive_path(item_type, item_id)
    if not src.exists():
        return None
    dst = active_path(item_type, item_id)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return load(item_type, item_id)


def list_active() -> list[dict]:
    """List all active lifecycle items."""
    if not ACTIVE_DIR.is_dir():
        return []
    out = []
    for f in sorted(ACTIVE_DIR.glob("*.yml")):
        with f.open() as fp:
            sidecar = yaml.safe_load(fp) or {}
        out.append(sidecar)
    return out


def link_artifact(item_type: str, item_id: int | str, artifact_type: str, artifact_id: str) -> None:
    """Add an artifact link to a lifecycle sidecar."""
    sidecar = load(item_type, item_id) or {"type": item_type, "id": item_id}
    linked = sidecar.setdefault("linked_artifacts", {})
    type_list = linked.setdefault(f"{artifact_type}s", [])
    if artifact_id not in type_list:
        type_list.append(artifact_id)
    save(item_type, item_id, sidecar)


def active_path(item_type: str, item_id: int | str) -> Path:
    return ACTIVE_DIR / f"{item_type}-{item_id}.yml"


def archive_path(item_type: str, item_id: int | str) -> Path:
    return ARCHIVE_DIR / f"{item_type}s" / f"{item_id}.yml"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
