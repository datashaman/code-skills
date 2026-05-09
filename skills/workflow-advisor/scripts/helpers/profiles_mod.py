"""
Profile metadata helpers.

This module gives the CLI a stable, lightweight view of profile contributions.
The richer composition rules live in references/profiles/ and lifecycle.py.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    name: str
    enabled: bool
    artifacts: list[str]
    gates: list[str]
    labels: list[str]

    def __iter__(self):
        yield self.name
        yield self


PROFILE_METADATA = {
    "spec-driven": {
        "artifacts": ["spec", "adr", "impl_plan"],
        "gates": ["spec_drafted", "spec_approved_by_architect", "impl_plan_approved"],
        "labels": ["stage:*", "type:*", "spec:*", "adr:*", "impl-plan:*"],
    },
    "testability": {
        "artifacts": ["test_plan"],
        "gates": ["test_plan_drafted", "test_plan_approved", "coverage_threshold_met"],
        "labels": ["test-plan:*"],
    },
    "observability": {
        "artifacts": ["obs_plan", "runbook"],
        "gates": [
            "obs_plan_drafted_if_required",
            "obs_plan_approved_if_required",
            "instrumentation_present_if_required",
            "baseline_metrics_captured",
            "post_release_metrics_reviewed",
        ],
        "labels": ["obs-plan:*"],
    },
    "documentation": {
        "artifacts": ["audience_docs", "release_notes"],
        "gates": ["required_audience_docs_drafted", "required_audience_docs_approved"],
        "labels": ["doc:*"],
    },
    "security": {
        "artifacts": ["threat_model"],
        "gates": ["threat_model_drafted", "security_review_complete", "no_high_findings"],
        "labels": ["threat-model:*", "area:security"],
    },
    "accessibility": {
        "artifacts": ["a11y_plan"],
        "gates": ["a11y_plan_drafted", "a11y_review_complete"],
        "labels": ["area:a11y"],
    },
    "compliance": {
        "artifacts": ["compliance_assessment", "attestation"],
        "gates": ["compliance_assessment_complete", "attestation_recorded"],
        "labels": ["compliance:*", "audit:*"],
    },
}


def iter_profiles(config: dict):
    configured = config.get("profiles", {})
    for name in sorted(PROFILE_METADATA):
        meta = PROFILE_METADATA[name]
        yield Profile(
            name=name,
            enabled=bool(configured.get(name, {}).get("enabled", False)),
            artifacts=list(meta["artifacts"]),
            gates=list(meta["gates"]),
            labels=list(meta["labels"]),
        )
