"""
helpers/reconcile/observe.py

Step 1 of the reconcile loop. Scan repo + provider state and build an
observation. Read-only.

The scope of observation depends on intent:
- Event-driven: bounded to the items the event references.
- Schedule-driven: broader — drift detection, stale checks, archive
  thresholds.
- Full reconcile: every active lifecycle item.

Observations are returned as structured dicts that classify.py and
apply.py consume.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

WORKFLOW_DIR = Path(".workflow")
ARTIFACTS_DIR = WORKFLOW_DIR / "artifacts"
LIFECYCLE_DIR = WORKFLOW_DIR / "lifecycle" / "active"


def observe(context: dict) -> dict:
    """
    Build an observation from current state.

    Args:
        context: {
            "event": optional normalized event,
            "scope": "event" | "schedule" | "full",
            "config": loaded config,
        }

    Returns:
        observation: {
            "artifacts": [{ id, type, path, hash, sidecar_state, ... }],
            "lifecycle_items": [{ type, id, current_stage, current_labels, ... }],
            "provider_state": cached subset of provider data,
            "drifts": [...],   # only on schedule scope
        }
    """
    scope = context.get("scope", "event")
    event = context.get("event")
    config = context.get("config", {})

    observation: dict = {
        "scope": scope,
        "artifacts": [],
        "lifecycle_items": [],
        "provider_state": {},
        "drifts": [],
    }

    if scope == "event" and event:
        # Bounded scope: only what the event references
        observation["artifacts"] = observe_artifacts_in_event(event, config)
        observation["lifecycle_items"] = observe_lifecycle_in_event(event, config)
    elif scope == "schedule":
        # Broader: drift detection
        observation["artifacts"] = observe_all_artifacts(config)
        observation["lifecycle_items"] = observe_all_lifecycle()
        observation["drifts"] = detect_drifts(observation["artifacts"])
    elif scope == "full":
        observation["artifacts"] = observe_all_artifacts(config)
        observation["lifecycle_items"] = observe_all_lifecycle()

    return observation


def run(config: dict, event: dict | None = None, scope: str | None = None) -> dict:
    """CLI compatibility wrapper for the observe phase."""
    if scope is None:
        scope = "event" if event else "full"
    return observe({"config": config, "event": event, "scope": scope})


def observe_artifacts_in_event(event: dict, config: dict) -> list[dict]:
    """For event-driven scope, find artifacts the event touches."""
    files = event.get("payload", {}).get("files", [])
    if not files:
        return []

    artifact_dirs = collect_artifact_dirs(config)
    touched = []
    for f in files:
        for artifact_type, dir_path in artifact_dirs.items():
            if f.startswith(dir_path):
                obs = observe_single_artifact(artifact_type, Path(f))
                if obs:
                    touched.append(obs)
    return touched


def observe_all_artifacts(config: dict) -> list[dict]:
    """Full scan of every tracked artifact."""
    observations = []
    artifact_dirs = collect_artifact_dirs(config)
    for artifact_type, dir_path in artifact_dirs.items():
        path = Path(dir_path)
        if not path.is_dir():
            continue
        for f in path.rglob("*.md"):
            obs = observe_single_artifact(artifact_type, f)
            if obs:
                observations.append(obs)
    return observations


def observe_single_artifact(artifact_type: str, path: Path) -> dict | None:
    """Hash the file, read sidecar, return observation."""
    if not path.is_file():
        return None

    content = path.read_bytes()
    current_hash = hashlib.sha256(content).hexdigest()

    artifact_id = path.stem
    sidecar_path = ARTIFACTS_DIR / f"{artifact_type}s" / f"{artifact_id}.yml"
    sidecar = {}
    if sidecar_path.exists():
        with sidecar_path.open() as f:
            sidecar = yaml.safe_load(f) or {}

    return {
        "type": artifact_type,
        "id": artifact_id,
        "path": str(path),
        "current_hash": current_hash,
        "sidecar_hash": sidecar.get("content_hash"),
        "sidecar_state": sidecar.get("state"),
        "sidecar": sidecar,
        "changed": current_hash != sidecar.get("content_hash"),
    }


def observe_lifecycle_in_event(event: dict, config: dict) -> list[dict]:
    """For event scope, observe the lifecycle item the event targets."""
    payload = event.get("payload", {})
    if "pr_number" in payload:
        return [observe_single_lifecycle("pr", payload["pr_number"])]
    if "issue_number" in payload:
        return [observe_single_lifecycle("issue", payload["issue_number"])]
    return []


def observe_all_lifecycle() -> list[dict]:
    """Observe every active lifecycle item."""
    if not LIFECYCLE_DIR.is_dir():
        return []

    observations = []
    for f in LIFECYCLE_DIR.glob("*.yml"):
        obs = observe_lifecycle_file(f)
        if obs:
            observations.append(obs)
    return observations


def observe_single_lifecycle(item_type: str, item_id: int | str) -> dict:
    """Read or initialize a lifecycle sidecar."""
    sidecar_path = LIFECYCLE_DIR / f"{item_type}-{item_id}.yml"
    if sidecar_path.exists():
        return observe_lifecycle_file(sidecar_path)

    return {
        "type": item_type,
        "id": item_id,
        "exists_in_folder": False,
        "current_stage": None,
        "sidecar": {},
    }


def observe_lifecycle_file(path: Path) -> dict:
    """Parse a lifecycle sidecar file."""
    with path.open() as f:
        sidecar = yaml.safe_load(f) or {}
    return {
        "type": sidecar.get("type"),
        "id": sidecar.get("id"),
        "exists_in_folder": True,
        "current_stage": sidecar.get("stage"),
        "current_labels": sidecar.get("current_labels", []),
        "sidecar": sidecar,
    }


def detect_drifts(artifact_observations: list[dict]) -> list[dict]:
    """Find artifacts whose hash doesn't match the sidecar."""
    return [
        {"type": o["type"], "id": o["id"], "drift": "hash_mismatch"}
        for o in artifact_observations
        if o["changed"] and o["sidecar_hash"] is not None
    ]


def collect_artifact_dirs(config: dict) -> dict[str, str]:
    """Map artifact type → directory from config."""
    result = {}
    for artifact_type, cfg in config.get("artifacts", {}).items():
        if cfg.get("enabled") and cfg.get("lives_in"):
            result[artifact_type] = cfg["lives_in"]
    return result
