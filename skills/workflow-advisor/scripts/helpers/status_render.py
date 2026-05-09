"""
Read-only status rendering for workflow-advisor.

This is intentionally folder-first. Provider freshness checks can be layered in
later, but the CLI should always be able to explain the committed `.workflow/`
state without network access.
"""

from __future__ import annotations

import json
from pathlib import Path

from helpers import lifecycle
import yaml

ACTIVE_DIR = Path(".workflow/lifecycle/active")
ARTIFACTS_DIR = Path(".workflow/artifacts")


def render_item(config: dict, item: dict, format: str = "text") -> str:
    kind = item["kind"]
    ident = item["id"]
    if kind in {"pr", "issue"}:
        sidecar = _load_yaml(ACTIVE_DIR / f"{kind}-{ident}.yml")
        if not sidecar:
            return _render_missing(kind, ident, format)
        gates = lifecycle.evaluate_gates_for_item(sidecar, config)
        payload = {"kind": kind, "id": ident, "sidecar": sidecar, "gates": gates}
        return _render_payload(payload, format)

    artifact_type = _artifact_kind(kind)
    sidecar = _load_yaml(ARTIFACTS_DIR / f"{artifact_type}s" / f"{ident}.yml")
    if not sidecar:
        return _render_missing(kind, ident, format)
    payload = {"kind": kind, "id": ident, "sidecar": sidecar, "gates": []}
    return _render_payload(payload, format)


def render_repo(config: dict, format: str = "text") -> str:
    active = []
    if ACTIVE_DIR.is_dir():
        for path in sorted(ACTIVE_DIR.glob("*.yml")):
            sidecar = _load_yaml(path)
            if sidecar:
                active.append(sidecar)
    payload = {
        "repo": config.get("repo", {}).get("identifier"),
        "active_count": len(active),
        "active_by_stage": _count_by(active, "stage"),
        "active_by_type": _count_by(active, "type"),
    }
    if format == "json":
        return json.dumps(payload, indent=2)

    lines = [f"Workflow status — {payload['repo'] or 'repo'}", ""]
    lines.append(f"Active items: {payload['active_count']}")
    lines.append("")
    lines.append("By stage:")
    for stage, count in sorted(payload["active_by_stage"].items()):
        lines.append(f"- {stage}: {count}")
    lines.append("")
    lines.append("By type:")
    for kind, count in sorted(payload["active_by_type"].items()):
        lines.append(f"- {kind}: {count}")
    return "\n".join(lines)


def _render_payload(payload: dict, format: str) -> str:
    if format == "json":
        return json.dumps(payload, indent=2)

    sidecar = payload["sidecar"]
    title = f"Workflow status — {payload['kind']} #{payload['id']}"
    lines = [title, ""]
    lines.append(f"Stage: {sidecar.get('stage', 'n/a')}")
    labels = sidecar.get("current_labels") or sidecar.get("target_labels") or []
    if labels:
        lines.append(f"Labels: {', '.join(labels)}")
    linked = sidecar.get("linked_artifacts") or {}
    if linked:
        lines.append("Linked artifacts:")
        for artifact_type, ids in sorted(linked.items()):
            lines.append(f"- {artifact_type}: {', '.join(map(str, ids))}")
    gates = payload.get("gates") or []
    if gates:
        lines.append("")
        lines.append("Gates:")
        for gate in gates:
            lines.append(f"- {gate['gate']}: {gate['result']} ({gate['reason']})")
    return "\n".join(lines)


def _render_missing(kind: str, ident: str, format: str) -> str:
    payload = {"kind": kind, "id": ident, "status": "missing"}
    if format == "json":
        return json.dumps(payload, indent=2)
    return f"No workflow status found for {kind}-{ident}."


def _artifact_kind(kind: str) -> str:
    return {"spec": "spec", "adr": "adr", "impl": "impl-plan"}.get(kind, kind)


def _count_by(items: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open() as f:
        return yaml.safe_load(f) or {}
