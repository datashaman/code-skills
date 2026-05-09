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
    # Mechanical gates — examples
    if gate_name == "spec_drafted":
        linked = sidecar.get("linked_artifacts", {}).get("specs", [])
        if linked:
            return {"gate": gate_name, "result": "pass", "reason": f"spec linked: {linked[0]}"}
        return {"gate": gate_name, "result": "fail", "reason": "no spec linked"}

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

    if gate_name == "no_open_blockers":
        labels = sidecar.get("current_labels", [])
        blockers = [label for label in labels if label.startswith("blocked:")]
        if not blockers:
            return {"gate": gate_name, "result": "pass", "reason": "no blockers"}
        return {"gate": gate_name, "result": "fail", "reason": f"blocked by: {', '.join(blockers)}"}

    # Default: unknown gate; pass with caveat
    return {"gate": gate_name, "result": "unknown", "reason": "no evaluator defined"}


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
