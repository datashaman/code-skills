"""
helpers/reconcile/cascade.py

Step 4 of the reconcile loop. Compute and apply cascade effects.

Cascade has two phases: compute and apply. Compute is pure (returns a
plan). Apply executes the plan with in-flight protection.

In-flight protection: when a cascade would disrupt active work, prefer
label-and-notify over silent revert. The default is `preserve_in_flight:
true`, configurable per cascade rule.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from helpers import provider_actions
import yaml

logger = logging.getLogger(__name__)

ARTIFACTS_DIR = Path(".workflow/artifacts")
LIFECYCLE_DIR = Path(".workflow/lifecycle/active")


def compute(observation: dict, classifications: dict, config: dict) -> dict:
    """
    Build the cascade plan. Pure; no writes.

    Returns:
        plan: {
            "actions": [{ target, action, reason, ... }, ...],
            "in_flight_conflicts": [...],
            "preserved_items": [...],
        }
    """
    plan: dict = {"actions": [], "in_flight_conflicts": [], "preserved_items": []}
    cascade_cfg = config.get("cascade", {})
    preserve = cascade_cfg.get("preserve_in_flight", True)

    # For each substantively/structurally changed artifact, look up rule
    for art in observation.get("artifacts", []):
        if not art["changed"]:
            continue
        cls = classifications.get(f"artifact:{art['type']}:{art['id']}")
        if not cls:
            continue
        classification = cls["classification"]

        rule_key = _rule_key_for(art["type"], classification)
        rule = cascade_cfg.get(rule_key, {})
        if not rule:
            continue

        # Find dependents
        dependents = find_dependents(art, config)

        for dependent in dependents:
            action = rule.get(dependent["category"])
            if not action or action == "no_change":
                continue

            # In-flight protection check
            if preserve and is_in_flight(dependent):
                plan["in_flight_conflicts"].append(
                    {
                        "source": f"{art['type']}/{art['id']}",
                        "conflict_with": f"{dependent['type']}/{dependent['id']}",
                        "would_have_done": action,
                        "actual": "label_and_notify",
                    }
                )
                plan["preserved_items"].append(dependent)
                # Add notify-only action
                plan["actions"].append(
                    {
                        "target": dependent,
                        "action": "label_and_notify",
                        "reason": f"in-flight protection — would have {action}",
                    }
                )
            else:
                plan["actions"].append(
                    {
                        "target": dependent,
                        "action": action,
                        "reason": f"cascade from {art['type']}/{art['id']} ({classification})",
                    }
                )

    return plan


def run(
    config: dict,
    observed: dict,
    classification: dict,
    applied: dict | None = None,
    session: Any | None = None,
) -> dict:
    """CLI compatibility wrapper for the cascade phase."""
    plan = compute(observed, classification, config)
    result = apply_plan(plan, config)
    result["in_flight_conflicts"] = plan.get("in_flight_conflicts", [])
    result["preserved_items"] = plan.get("preserved_items", [])
    if session is not None:
        for action in result.get("applied", []):
            target = action.get("target", {})
            session.record_cascade_effect(
                f"{target.get('type')}/{target.get('id')}",
                action.get("action", ""),
                action.get("reason", ""),
            )
    return result


def dry_run(
    config: dict, observed: dict, classification: dict, proposed: dict | None = None
) -> dict:
    """Return cascade effects without writing files."""
    plan = compute(observed, classification, config)
    effects = []
    for action in plan.get("actions", []):
        target = action.get("target", {})
        effects.append(
            {
                "target": f"{target.get('type')}/{target.get('id')}",
                "action": action.get("action"),
                "reason": action.get("reason"),
            }
        )
    return {"effects": effects, "plan": plan}


def apply_plan(plan: dict, config: dict) -> dict:
    """
    Execute the cascade plan. Folder + provider effects.

    Returns:
        result: { "applied": [...], "failed": [...] }
    """
    result: dict = {"applied": [], "failed": []}

    for action in plan["actions"]:
        try:
            execute_action(action, config)
            result["applied"].append(action)
        except Exception as e:
            logger.error(f"Cascade action failed: {action} — {e}")
            result["failed"].append({"action": action, "error": str(e)})

    return result


def execute_action(action: dict, config: dict) -> None:
    """
    Execute one cascade action. Dispatches to the right helper based on
    action type.
    """
    target = action["target"]
    name = action["action"]

    if name == "label_and_notify":
        # Update lifecycle sidecar with blocked label and notify
        update_lifecycle_label(target, "blocked:in-flight-conflict")
        queue_label(target, "blocked:in-flight-conflict", config, action.get("reason", ""))

    elif name == "revert_to_draft":
        update_artifact_state(target, "draft")

    elif name == "revert_to_arch_review":
        update_lifecycle_stage(target, "arch-review")

    elif name == "archive":
        archive_target(target)

    elif name == "flag_for_review":
        update_lifecycle_label(target, "needs:review-update")
        queue_label(target, "needs:review-update", config, action.get("reason", ""))

    elif name == "notify_only":
        # Pure notification — handled by notification queue
        pass

    elif name == "link_to_new_spec_and_notify":
        # Cross-reference update
        update_lifecycle_link(target, action.get("new_spec_id"))

    elif name == "append_supersession_note":
        # ADR-specific: append a note to the markdown (low-touch)
        append_artifact_note(target, "Superseded; see new spec.")

    else:
        raise ValueError(f"Unknown cascade action: {name}")


def find_dependents(artifact: dict, config: dict) -> list[dict]:
    """
    Find items that cascade rules might affect.

    Returns a list of { "type", "id", "category" } where category is
    one of: "impl_plan", "test_plan", "obs_plan", "threat_model",
    "open_prs", "related_adrs", "audience_docs".
    """
    deps: list[dict] = []
    art_type = artifact["type"]
    art_id = artifact["id"]

    if art_type == "spec":
        deps.extend(
            _same_id_plan_dependents(
                art_id,
                {
                    "impl-plans": ("impl_plan", "impl_plan"),
                    "test-plans": ("test_plan", "test_plan"),
                    "obs-plans": ("obs_plan", "obs_plan"),
                    "threat-models": ("threat_model", "threat_model"),
                },
            )
        )

        # open PRs that link to this spec
        for lifecycle_file in LIFECYCLE_DIR.glob("pr-*.yml"):
            with lifecycle_file.open() as f:
                sidecar = yaml.safe_load(f) or {}
            linked = sidecar.get("linked_artifacts", {}).get("specs", [])
            if art_id in linked and sidecar.get("stage") not in ("merged", "closed"):
                deps.append(
                    {
                        "type": "pr",
                        "id": sidecar.get("id"),
                        "category": "open_prs",
                        "current_stage": sidecar.get("stage"),
                        "approvals": sidecar.get("approvals", {}),
                    }
                )

        # ADRs that reference this spec
        adrs_dir = ARTIFACTS_DIR / "adrs"
        if adrs_dir.is_dir():
            for adr_file in adrs_dir.glob("*.yml"):
                with adr_file.open() as f:
                    adr_sidecar = yaml.safe_load(f) or {}
                if art_id in adr_sidecar.get("references", {}).get("specs", []):
                    deps.append(
                        {
                            "type": "adr",
                            "id": adr_sidecar.get("id"),
                            "category": "related_adrs",
                        }
                    )

        # audience docs (documentation profile)
        for audience in ("operator", "support", "end_user", "security", "product", "developer"):
            audience_dir = ARTIFACTS_DIR / "audience-docs" / audience
            if not audience_dir.is_dir():
                continue
            for doc_file in audience_dir.glob("*.yml"):
                with doc_file.open() as f:
                    doc_sidecar = yaml.safe_load(f) or {}
                if art_id in doc_sidecar.get("references", {}).get("specs", []):
                    deps.append(
                        {
                            "type": f"doc_{audience}",
                            "id": doc_sidecar.get("id"),
                            "category": "audience_docs",
                        }
                    )

    return deps


def _same_id_plan_dependents(art_id: str, mappings: dict[str, tuple[str, str]]) -> list[dict]:
    """Find plan sidecars that conventionally share a spec id."""
    deps = []
    for dirname, (target_type, category) in mappings.items():
        path = ARTIFACTS_DIR / dirname / f"{art_id}.yml"
        if path.exists():
            deps.append({"type": target_type, "id": art_id, "category": category})
    return deps


def is_in_flight(dependent: dict) -> bool:
    """
    Determine if a dependent is mid-flight (active work that should
    not be silently disrupted).
    """
    stage = dependent.get("current_stage")
    if stage in ("review", "merge-ready"):
        return True
    approvals = dependent.get("approvals", {})
    if approvals.get("received"):
        return True
    return False


def _rule_key_for(art_type: str, classification: str) -> str:
    """Map (artifact_type, classification) to cascade rule key."""
    return {
        ("spec", "substantive"): "spec_substantive_change",
        ("spec", "editorial"): "spec_editorial_change",
        ("spec", "structural"): "spec_supersession",
    }.get((art_type, classification), f"{art_type}_{classification}_change")


# Stub action implementations — real provider/folder effects live in
# the provider-action helpers and lifecycle_store.


def update_lifecycle_label(target: dict, label: str) -> None:
    """Add a label to a lifecycle item's target_labels list."""
    path = LIFECYCLE_DIR / f"{target['type']}-{target['id']}.yml"
    if not path.exists():
        return
    with path.open() as f:
        sidecar = yaml.safe_load(f) or {}
    labels = sidecar.setdefault("target_labels", [])
    if label not in labels:
        labels.append(label)
    with path.open("w") as f:
        yaml.dump(sidecar, f, sort_keys=False)


def queue_label(target: dict, label: str, config: dict, reason: str = "") -> None:
    """Queue provider label application for PR/issue targets."""
    if target.get("type") not in {"pr", "issue"}:
        return
    repo = config.get("repo", {}).get("identifier")
    item_id = target.get("id")
    if not repo or item_id is None:
        return
    provider_actions.queue_action(
        "labels.apply_diff",
        {
            "repo": repo,
            "item_number": item_id,
            "diff": {"add": [label], "remove": []},
        },
        reason=reason,
    )


def update_lifecycle_stage(target: dict, stage: str) -> None:
    path = LIFECYCLE_DIR / f"{target['type']}-{target['id']}.yml"
    if not path.exists():
        return
    with path.open() as f:
        sidecar = yaml.safe_load(f) or {}
    if sidecar.get("stage") != stage:
        sidecar.setdefault("stage_history", []).append(
            {
                "from": sidecar.get("stage"),
                "to": stage,
                "reason": "cascade",
            }
        )
        sidecar["stage"] = stage
    with path.open("w") as f:
        yaml.dump(sidecar, f, sort_keys=False)


def update_artifact_state(target: dict, state: str) -> None:
    path = ARTIFACTS_DIR / f"{target['type']}s" / f"{target['id']}.yml"
    if not path.exists():
        return
    with path.open() as f:
        sidecar = yaml.safe_load(f) or {}
    sidecar["state"] = state
    with path.open("w") as f:
        yaml.dump(sidecar, f, sort_keys=False)


def archive_target(target: dict) -> None:
    """Move a target's sidecar to archive/."""
    src_dir = ARTIFACTS_DIR / f"{target['type']}s"
    dst_dir = Path(".workflow/lifecycle/archive") / target["type"]
    dst_dir.mkdir(parents=True, exist_ok=True)
    src = src_dir / f"{target['id']}.yml"
    if src.exists():
        src.rename(dst_dir / f"{target['id']}.yml")


def update_lifecycle_link(target: dict, new_id: str | None) -> None:
    if new_id is None:
        return
    path = LIFECYCLE_DIR / f"{target['type']}-{target['id']}.yml"
    if not path.exists():
        return
    with path.open() as f:
        sidecar = yaml.safe_load(f) or {}
    sidecar.setdefault("supersedes_link", []).append(new_id)
    with path.open("w") as f:
        yaml.dump(sidecar, f, sort_keys=False)


def append_artifact_note(target: dict, note: str) -> None:
    """Append a marker note to an artifact's markdown file (low-touch)."""
    sidecar_path = ARTIFACTS_DIR / f"{target['type']}s" / f"{target['id']}.yml"
    if not sidecar_path.exists():
        return
    with sidecar_path.open() as f:
        sidecar = yaml.safe_load(f) or {}
    file_path = Path(sidecar.get("file") or "")
    if file_path.exists():
        with file_path.open("a") as f:
            f.write(f"\n\n---\n*Note: {note}*\n")
