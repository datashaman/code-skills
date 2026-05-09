"""
helpers/lifecycle.py

Lifecycle composition and gate evaluation.

Composition: given enabled profiles, compute the composed sequence of
stages with parallel/sequential arrangement. Cached at config-write
time in `.workflow/lifecycle/composed.yml`.

Gate evaluation: given a lifecycle item and its current stage, evaluate
the gates required to advance. Returns pass/fail per gate with reasons.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


# Profile contributions to the lifecycle. Source of truth for what each
# profile adds. Should match the corresponding references/profiles/*.md.
PROFILE_CONTRIBUTIONS: dict[str, dict] = {
    "spec-driven": {
        "stages": ["spec", "arch-review", "impl-plan", "implementation", "review", "merge-ready"],
        "depends_on": [],
    },
    "testability": {
        "stages": ["test-plan"],  # parallel with impl-plan
        "depends_on": ["spec-driven"],
        "parallel_with": "impl-plan",
    },
    "observability": {
        "stages": [
            "obs-plan",
            "released",
            "validated",
        ],  # obs-plan parallel; released/validated post-merge
        "depends_on": ["spec-driven"],
        "parallel_with": "impl-plan",  # obs-plan
        "post_merge_stages": ["released", "validated"],
    },
    "documentation": {
        "stages": [],  # gates only; no dedicated stages
        "depends_on": ["spec-driven"],
    },
    "security": {
        "stages": [],
        "depends_on": ["spec-driven"],
    },
    "accessibility": {
        "stages": [],
        "depends_on": ["spec-driven"],
    },
    "compliance": {
        "stages": [],
        "depends_on": ["spec-driven"],
    },
}


def compose(config: dict) -> dict:
    """
    Compose the lifecycle from enabled profiles.

    Returns:
        composed: {
            "sequence": [...],
            "post_merge": [...],
            "stages_owned_by_profiles": {...},
        }
    """
    enabled = [name for name, p in config.get("profiles", {}).items() if p.get("enabled")]
    arrangement = (
        config.get("lifecycle", {}).get("composition", {}).get("planning_arrangement", "parallel")
    )

    # Start with spec-driven's canonical sequence
    if "spec-driven" not in enabled:
        # Minimal lifecycle if spec-driven is off
        sequence = ["implementation", "review", "merge-ready"]
    else:
        sequence = list(PROFILE_CONTRIBUTIONS["spec-driven"]["stages"])

    # Slot in planning stages from other profiles
    planning_stages = []
    post_merge_stages = []
    stages_owned: dict[str, str] = {s: "spec-driven" for s in sequence}

    for profile in enabled:
        if profile == "spec-driven":
            continue
        contrib = PROFILE_CONTRIBUTIONS.get(profile, {})
        for stage in contrib.get("stages", []):
            if stage in contrib.get("post_merge_stages", []):
                post_merge_stages.append(stage)
                stages_owned[stage] = profile
            elif contrib.get("parallel_with"):
                planning_stages.append(stage)
                stages_owned[stage] = profile

    # Insert planning_stages
    if planning_stages:
        if "impl-plan" in sequence:
            idx = sequence.index("impl-plan")
            if arrangement == "parallel":
                # Bracket impl-plan with the others
                parallel_block = ["impl-plan"] + planning_stages
                sequence[idx : idx + 1] = [parallel_block]
            else:
                # Sequential: impl-plan, then test-plan, then obs-plan
                sequence[idx + 1 : idx + 1] = planning_stages

    # Append post-merge stages
    sequence.extend(post_merge_stages)

    return {
        "sequence": sequence,
        "post_merge": post_merge_stages,
        "stages_owned_by_profiles": stages_owned,
        "enabled_profiles": enabled,
    }


def render_ascii(composed: dict) -> str:
    """Render the lifecycle as a simple ASCII flow."""
    lines = []
    for idx, stage in enumerate(composed["sequence"]):
        if isinstance(stage, list):
            # Parallel block
            lines.append(" → ".join(["[" + " | ".join(stage) + "]"]))
        else:
            lines.append(stage)
    return " → ".join(lines)


def render(composed: dict, format: str = "text") -> str:
    """Render lifecycle composition for the CLI."""
    if format == "mermaid":
        flat = []
        for stage in composed["sequence"]:
            if isinstance(stage, list):
                flat.append("_".join(stage))
            else:
                flat.append(stage)
        lines = ["flowchart LR"]
        for left, right in zip(flat, flat[1:]):
            lines.append(f"  {left} --> {right}")
        return "\n".join(lines)
    return render_ascii(composed)


def validate(composed: dict) -> list[str]:
    """Validate a composed lifecycle enough for CLI smoke checks."""
    issues: list[str] = []
    sequence = composed.get("sequence")
    if not isinstance(sequence, list) or not sequence:
        issues.append("lifecycle sequence is empty")
    return issues


def evaluate_gates_for_item(sidecar: dict, config: dict | None = None) -> list[dict]:
    """
    Evaluate gates for a lifecycle item's current stage.

    Returns a list of { "gate": name, "result": "pass"|"fail", "reason": str }.
    """
    if config is None:
        from . import config_io

        config = config_io.load()

    stage = sidecar.get("stage")
    if not stage:
        return []

    gates_for_stage = config.get("lifecycle", {}).get("gates", {}).get(stage, [])
    if isinstance(gates_for_stage, dict):
        # Conditional form: { condition: ..., gates: [...], else: ... }
        gates_for_stage = gates_for_stage.get("gates", [])

    results = []
    for gate_name in gates_for_stage:
        results.append(evaluate_single_gate(gate_name, sidecar, config))
    return results


def evaluate_single_gate(gate_name: str, sidecar: dict, config: dict) -> dict:
    """
    Evaluate one gate. Subjective gates may use LLM judgment; mechanical
    gates evaluate from sidecar fields.
    """
    if gate_name == "stage_advance_no_gate":
        return {"gate": gate_name, "result": "pass", "reason": "no gate configured"}

    if gate_name == "spec_drafted":
        return _linked_artifact_gate(gate_name, sidecar, "specs", "spec")

    if gate_name == "impl_plan_drafted":
        return _linked_artifact_gate(gate_name, sidecar, "impl_plans", "implementation plan")

    if gate_name == "test_plan_drafted":
        return _linked_artifact_gate(gate_name, sidecar, "test_plans", "test plan")

    if gate_name == "obs_plan_drafted_if_required":
        if not _is_required(sidecar, config, "observability", "obs_plan_required"):
            return {
                "gate": gate_name,
                "result": "pass",
                "reason": "observability plan not required",
            }
        return _linked_artifact_gate(gate_name, sidecar, "obs_plans", "observability plan")

    if gate_name == "spec_approved_by_architect":
        return _approval_gate(gate_name, sidecar, artifact="specs", role="architect")

    if gate_name == "impl_plan_approved":
        return _approval_gate(gate_name, sidecar, artifact="impl_plans", role="tech_lead")

    if gate_name == "test_plan_approved":
        return _approval_gate(gate_name, sidecar, artifact="test_plans", role="test_lead")

    if gate_name == "obs_plan_approved_if_required":
        if not _is_required(sidecar, config, "observability", "obs_plan_required"):
            return {
                "gate": gate_name,
                "result": "pass",
                "reason": "observability plan not required",
            }
        return _approval_gate(gate_name, sidecar, artifact="obs_plans", role="sre")

    if gate_name == "min_approvals_met":
        min_required = config.get("review_policy", {}).get("min_approvals", 1)
        received = sidecar.get("approvals", {}).get("received", [])
        if len(received) >= min_required:
            return {
                "gate": gate_name,
                "result": "pass",
                "reason": f"{len(received)}/{min_required} approvals",
            }
        return {
            "gate": gate_name,
            "result": "fail",
            "reason": f"{len(received)}/{min_required} approvals",
        }

    if gate_name == "no_unresolved_review_threads":
        unresolved = sidecar.get("review_threads_unresolved", 0)
        if unresolved == 0:
            return {"gate": gate_name, "result": "pass", "reason": "all threads resolved"}
        return {"gate": gate_name, "result": "fail", "reason": f"{unresolved} unresolved threads"}

    if gate_name == "tests_pass":
        ci_status = sidecar.get("last_ci_status")
        if ci_status == "success":
            return {"gate": gate_name, "result": "pass", "reason": "CI passed"}
        return {"gate": gate_name, "result": "fail", "reason": f"CI: {ci_status or 'unknown'}"}

    if gate_name == "coverage_threshold_met":
        coverage = sidecar.get("coverage", {})
        required = config.get("testing", {}).get("coverage", {})
        line_target = required.get("lines", 0)
        branch_target = required.get("branches", 0)
        line_actual = coverage.get("lines", 0)
        branch_actual = coverage.get("branches", 0)
        if line_actual >= line_target and branch_actual >= branch_target:
            return {
                "gate": gate_name,
                "result": "pass",
                "reason": f"coverage lines {line_actual}/{line_target}, branches {branch_actual}/{branch_target}",
            }
        return {
            "gate": gate_name,
            "result": "fail",
            "reason": f"coverage lines {line_actual}/{line_target}, branches {branch_actual}/{branch_target}",
        }

    if gate_name == "codeowners_approved":
        if not config.get("review_policy", {}).get("codeowners_required", False):
            return {
                "gate": gate_name,
                "result": "pass",
                "reason": "CODEOWNERS approval not required",
            }
        approvals = sidecar.get("approvals", {})
        if sidecar.get("codeowners_approved") or approvals.get("codeowners"):
            return {"gate": gate_name, "result": "pass", "reason": "CODEOWNERS approved"}
        return {"gate": gate_name, "result": "fail", "reason": "CODEOWNERS approval missing"}

    if gate_name == "no_open_blockers":
        labels = sidecar.get("current_labels", [])
        blockers = [label for label in labels if label.startswith("blocked:")]
        if not blockers:
            return {"gate": gate_name, "result": "pass", "reason": "no blockers"}
        return {"gate": gate_name, "result": "fail", "reason": f"blocked by: {', '.join(blockers)}"}

    if gate_name == "instrumentation_present_if_required":
        if not _is_required(sidecar, config, "observability", "instrumentation_required"):
            return {"gate": gate_name, "result": "pass", "reason": "instrumentation not required"}
        instrumentation = sidecar.get("instrumentation", {})
        if (
            instrumentation.get("present")
            or instrumentation.get("metrics")
            or instrumentation.get("logs")
        ):
            return {"gate": gate_name, "result": "pass", "reason": "instrumentation present"}
        return {
            "gate": gate_name,
            "result": "fail",
            "reason": "instrumentation required but missing",
        }

    if gate_name == "deployed":
        status = sidecar.get("deployment_status") or sidecar.get("deployment", {}).get("status")
        if status in {"success", "deployed"}:
            return {"gate": gate_name, "result": "pass", "reason": f"deployment {status}"}
        return {"gate": gate_name, "result": "fail", "reason": f"deployment {status or 'unknown'}"}

    if gate_name == "baseline_metrics_captured":
        metrics = sidecar.get("metrics", {})
        if metrics.get("baseline_captured"):
            return {"gate": gate_name, "result": "pass", "reason": "baseline metrics captured"}
        return {"gate": gate_name, "result": "fail", "reason": "baseline metrics missing"}

    if gate_name == "post_release_metrics_reviewed":
        metrics = sidecar.get("metrics", {})
        if metrics.get("post_release_reviewed"):
            return {"gate": gate_name, "result": "pass", "reason": "post-release metrics reviewed"}
        return {
            "gate": gate_name,
            "result": "fail",
            "reason": "post-release metrics review missing",
        }

    if gate_name == "validation_window_elapsed":
        window = sidecar.get("validation_window", {})
        if window.get("elapsed"):
            return {"gate": gate_name, "result": "pass", "reason": "validation window elapsed"}
        ends_at = _parse_time(window.get("ends_at"))
        if ends_at and ends_at <= datetime.now(timezone.utc):
            return {"gate": gate_name, "result": "pass", "reason": "validation window elapsed"}
        return {"gate": gate_name, "result": "fail", "reason": "validation window still open"}

    # Default: unknown gate; pass with caveat
    return {"gate": gate_name, "result": "unknown", "reason": "no evaluator defined"}


def _linked_artifact_gate(gate_name: str, sidecar: dict, key: str, label: str) -> dict:
    linked = sidecar.get("linked_artifacts", {}).get(key, [])
    if linked:
        return {"gate": gate_name, "result": "pass", "reason": f"{label} linked: {linked[0]}"}
    return {"gate": gate_name, "result": "fail", "reason": f"no {label} linked"}


def _approval_gate(gate_name: str, sidecar: dict, artifact: str, role: str) -> dict:
    approvals = sidecar.get("approvals", {})
    artifact_approvals = approvals.get("artifacts", {})
    role_approvals = approvals.get("by_role", {})
    if artifact_approvals.get(artifact):
        return {"gate": gate_name, "result": "pass", "reason": f"{artifact} approved"}
    if role_approvals.get(role):
        return {"gate": gate_name, "result": "pass", "reason": f"{role} approved"}
    return {"gate": gate_name, "result": "fail", "reason": f"{role} approval missing"}


def _is_required(sidecar: dict, config: dict, profile: str, sidecar_key: str) -> bool:
    if sidecar_key in sidecar:
        return bool(sidecar[sidecar_key])
    return bool(config.get("profiles", {}).get(profile, {}).get("enabled"))


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def can_advance_stage(sidecar: dict, config: dict | None = None) -> tuple[bool, list[dict]]:
    """
    Returns (can_advance, failing_gates).
    """
    gates = evaluate_gates_for_item(sidecar, config)
    failing = [g for g in gates if g["result"] != "pass"]
    return (len(failing) == 0, failing)


def next_stage(current_stage: str, composed: dict) -> str | None:
    """Find the next stage in the composed sequence."""
    sequence = composed["sequence"]
    flat = []
    for s in sequence:
        if isinstance(s, list):
            flat.extend(s)
        else:
            flat.append(s)

    if current_stage not in flat:
        return None

    idx = flat.index(current_stage)
    if idx >= len(flat) - 1:
        return None
    return flat[idx + 1]
