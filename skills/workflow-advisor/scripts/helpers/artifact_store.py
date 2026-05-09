"""
helpers/artifact_store.py

Read and write artifact sidecars. Sidecars live at
`.workflow/artifacts/{type}s/{id}.yml` and mirror the markdown
artifact's state.

This helper is the only correct place to read or write sidecars.
Direct yaml.safe_load() in playbooks is discouraged because:

- Sidecars have invariants (revision monotonic, hash matches file).
- Front-matter sync is paired with sidecar writes when configured.
- Read paths cache to avoid repeated disk hits per reconcile pass.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import logging
from pathlib import Path
import re

import yaml

logger = logging.getLogger(__name__)

ARTIFACTS_DIR = Path(".workflow/artifacts")


def load(artifact_type: str, artifact_id: str) -> dict | None:
    """Load a sidecar by type and ID."""
    path = sidecar_path(artifact_type, artifact_id)
    if not path.exists():
        return None
    with path.open() as f:
        return yaml.safe_load(f) or {}


def save(artifact_type: str, artifact_id: str, sidecar: dict) -> None:
    """Save a sidecar atomically (write to temp, rename)."""
    path = sidecar_path(artifact_type, artifact_id)
    path.parent.mkdir(parents=True, exist_ok=True)

    sidecar.setdefault("id", artifact_id)
    sidecar["last_observed"] = _now_iso()
    sidecar["revision"] = (sidecar.get("revision") or 0) + 1

    tmp = path.with_suffix(".yml.tmp")
    with tmp.open("w") as f:
        yaml.dump(sidecar, f, sort_keys=False, default_flow_style=False)
    tmp.replace(path)


def update_state(
    artifact_type: str, artifact_id: str, new_state: str, actor: str | None = None
) -> dict:
    """
    Update an artifact's state. Records history with actor and timestamp.
    Returns the updated sidecar.
    """
    sidecar = load(artifact_type, artifact_id) or {"id": artifact_id}
    old_state = sidecar.get("state")
    if old_state != new_state:
        history = sidecar.setdefault("approvals", {}).setdefault("history", [])
        history.append(
            {
                "actor": actor or "skill",
                "at": _now_iso(),
                "state_before": old_state,
                "state_after": new_state,
            }
        )
    sidecar["state"] = new_state
    save(artifact_type, artifact_id, sidecar)
    return sidecar


def hash_file(path: Path) -> str:
    """Compute the canonical content hash for a file."""
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def detect_drift(artifact_type: str, artifact_id: str) -> dict | None:
    """
    Compare the file's current hash to the sidecar's recorded hash.
    Returns None if no drift, or a dict describing the drift.
    """
    sidecar = load(artifact_type, artifact_id)
    if not sidecar or not sidecar.get("file"):
        return None
    file_path = Path(sidecar["file"])
    if not file_path.exists():
        return {"kind": "file_missing", "expected_hash": sidecar.get("content_hash")}
    actual = hash_file(file_path)
    if actual != sidecar.get("content_hash"):
        return {
            "kind": "hash_mismatch",
            "expected_hash": sidecar.get("content_hash"),
            "actual_hash": actual,
        }
    return None


def sync_front_matter(artifact_type: str, artifact_id: str) -> bool:
    """
    Update the markdown's front-matter from the sidecar. Returns True
    if a change was made.
    """
    sidecar = load(artifact_type, artifact_id)
    if not sidecar or not sidecar.get("file"):
        return False
    file_path = Path(sidecar["file"])
    if not file_path.exists():
        return False

    fm_fields = {
        "id": sidecar.get("id"),
        "title": sidecar.get("title"),
        "state": sidecar.get("state"),
        "last_updated": _now_iso()[:10],
    }
    fm_block = "---\n" + yaml.dump(fm_fields, sort_keys=False) + "---\n"

    content = file_path.read_text()
    if re.match(r"^---\n.*?\n---\n", content, re.DOTALL):
        new_content = re.sub(r"^---\n.*?\n---\n", fm_block, content, count=1, flags=re.DOTALL)
    else:
        new_content = fm_block + content

    if new_content == content:
        return False
    file_path.write_text(new_content)
    return True


def list_artifacts(artifact_type: str) -> list[dict]:
    """List all sidecars of a given type."""
    type_dir = ARTIFACTS_DIR / f"{artifact_type}s"
    if not type_dir.is_dir():
        return []
    out = []
    for f in sorted(type_dir.glob("*.yml")):
        with f.open() as fp:
            sidecar = yaml.safe_load(fp) or {}
        out.append(sidecar)
    return out


def sidecar_path(artifact_type: str, artifact_id: str) -> Path:
    return ARTIFACTS_DIR / f"{artifact_type}s" / f"{artifact_id}.yml"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
