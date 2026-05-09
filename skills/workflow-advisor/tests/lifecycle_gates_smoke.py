#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from helpers import lifecycle  # noqa: E402


def main() -> int:
    config = {
        "profiles": {"observability": {"enabled": True}},
        "review_policy": {"min_approvals": 2, "codeowners_required": True},
        "testing": {"coverage": {"lines": 80, "branches": 70}},
    }
    sidecar = {
        "linked_artifacts": {
            "specs": ["demo"],
            "impl_plans": ["demo"],
            "test_plans": ["demo"],
            "obs_plans": ["demo"],
        },
        "approvals": {
            "received": ["alice", "bob"],
            "by_role": {
                "architect": ["alice"],
                "tech_lead": ["bob"],
                "test_lead": ["qa"],
                "sre": ["sre"],
            },
            "codeowners": ["owner"],
        },
        "last_ci_status": "success",
        "coverage": {"lines": 85, "branches": 72},
        "current_labels": [],
        "instrumentation": {"metrics": True},
        "deployment_status": "success",
        "metrics": {"baseline_captured": True, "post_release_reviewed": True},
        "validation_window": {
            "ends_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        },
    }

    gates = [
        "spec_drafted",
        "spec_approved_by_architect",
        "impl_plan_drafted",
        "impl_plan_approved",
        "test_plan_drafted",
        "test_plan_approved",
        "obs_plan_drafted_if_required",
        "obs_plan_approved_if_required",
        "tests_pass",
        "coverage_threshold_met",
        "min_approvals_met",
        "codeowners_approved",
        "no_open_blockers",
        "instrumentation_present_if_required",
        "deployed",
        "baseline_metrics_captured",
        "post_release_metrics_reviewed",
        "validation_window_elapsed",
    ]
    results = [lifecycle.evaluate_single_gate(gate, sidecar, config) for gate in gates]
    failures = [result for result in results if result["result"] != "pass"]
    assert not failures, failures

    missing_codeowners = dict(sidecar, approvals={"received": ["alice", "bob"]})
    failed = lifecycle.evaluate_single_gate("codeowners_approved", missing_codeowners, config)
    assert failed["result"] == "fail"

    print("lifecycle gates smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
