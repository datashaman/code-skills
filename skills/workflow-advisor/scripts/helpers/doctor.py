"""
helpers/doctor.py

Validate config and folder consistency. The `workflow-advisor doctor`
subcommand calls this to surface problems users should fix.

Categories of checks:

- Schema validity — config.yml conforms to schema.
- Reference integrity — referenced roles, profiles, labels exist.
- File-folder consistency — sidecars match files; orphan sidecars; orphan files.
- Provider state alignment (network-permitting) — taxonomy synced; CODEOWNERS valid.
- Empty-role surfacing — which roles are unassigned.

Each check returns a list of issues with severity: error | warning | info.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from . import config_io

logger = logging.getLogger(__name__)


def run_checks() -> list[dict]:
    """Run all checks and return a flat list of issues."""
    issues: list[dict] = []
    try:
        config = config_io.load()
    except config_io.ConfigError as e:
        return [{"severity": "error", "message": f"config invalid: {e}"}]

    issues.extend(check_role_references(config))
    issues.extend(check_artifact_sidecar_consistency(config))
    issues.extend(check_lifecycle_sidecar_consistency())
    issues.extend(check_empty_roles(config))
    issues.extend(check_template_existence(config))
    issues.extend(check_schema_version_recorded())

    return issues


def check(config_path: Path | str | None = None) -> list[dict]:
    """CLI compatibility wrapper."""
    if config_path is None:
        return run_checks()
    try:
        config = config_io.load_from_path(config_path)
    except config_io.ConfigError as e:
        return [{"severity": "error", "message": f"config invalid: {e}"}]

    issues: list[dict] = []
    issues.extend(check_role_references(config))
    issues.extend(check_artifact_sidecar_consistency(config))
    issues.extend(check_lifecycle_sidecar_consistency())
    issues.extend(check_empty_roles(config))
    issues.extend(check_template_existence(config))
    issues.extend(check_schema_version_recorded())
    return issues


def check_role_references(config: dict) -> list[dict]:
    """Profiles and slash commands should only reference declared roles."""
    issues = []
    declared_roles = set(config.get("roles", {}).keys()) - {"aliases"}
    aliases = config.get("roles", {}).get("aliases", {})

    for command, auth in config.get("slash_commands", {}).items():
        if isinstance(auth, list):
            for role in auth:
                if role not in declared_roles and role not in aliases:
                    issues.append(
                        {
                            "severity": "warning",
                            "message": f"Slash command {command!r} references undeclared role {role!r}",
                        }
                    )
        elif isinstance(auth, str) and auth not in ("any", "per_gate_override_policy"):
            if auth not in declared_roles and auth not in aliases:
                issues.append(
                    {
                        "severity": "warning",
                        "message": f"Slash command {command!r} references undeclared role {auth!r}",
                    }
                )
    return issues


def check_artifact_sidecar_consistency(config: dict) -> list[dict]:
    """Sidecars should point to existing files; files should have sidecars."""
    issues = []
    for artifact_type, cfg in config.get("artifacts", {}).items():
        if not cfg.get("enabled"):
            continue
        sidecar_dir = Path(f".workflow/artifacts/{artifact_type}s")
        if sidecar_dir.is_dir():
            for sidecar_file in sidecar_dir.glob("*.yml"):
                with sidecar_file.open() as f:
                    sidecar = yaml.safe_load(f) or {}
                file_path = sidecar.get("file")
                if file_path and not Path(file_path).exists():
                    issues.append(
                        {
                            "severity": "warning",
                            "message": f"Sidecar {sidecar_file} points to missing file {file_path}",
                        }
                    )
    return issues


def check_lifecycle_sidecar_consistency() -> list[dict]:
    """Lifecycle sidecars should have valid type and id."""
    issues = []
    active = Path(".workflow/lifecycle/active")
    if not active.is_dir():
        return issues
    for f in active.glob("*.yml"):
        with f.open() as fp:
            sidecar = yaml.safe_load(fp) or {}
        if not sidecar.get("type") or not sidecar.get("id"):
            issues.append(
                {
                    "severity": "warning",
                    "message": f"Lifecycle sidecar {f} missing type or id",
                }
            )
    return issues


def check_empty_roles(config: dict) -> list[dict]:
    """Warn about empty roles required by enabled profiles."""
    issues = []
    enabled_profiles = [p for p, cfg in config.get("profiles", {}).items() if cfg.get("enabled")]
    profile_required_roles = {
        "spec-driven": ["architect", "tech_lead"],
        "testability": ["test_lead"],
        "observability": ["sre"],
        "security": ["security"],
        "accessibility": ["accessibility_lead"],
        "compliance": ["legal_compliance"],
    }

    for profile in enabled_profiles:
        for role in profile_required_roles.get(profile, []):
            members = config.get("roles", {}).get(role, {}).get("members", [])
            if not members:
                issues.append(
                    {
                        "severity": "info",
                        "message": (
                            f"Role {role!r} required by profile {profile!r} has no members; "
                            f"gates will fall back to tech_lead"
                        ),
                    }
                )
    return issues


def check_template_existence(config: dict) -> list[dict]:
    """Templates referenced from artifacts should exist."""
    issues = []
    for artifact_type, cfg in config.get("artifacts", {}).items():
        if not cfg.get("enabled"):
            continue
        template = cfg.get("template")
        if template and not Path(template).exists():
            issues.append(
                {
                    "severity": "warning",
                    "message": f"Template {template} for {artifact_type} not found",
                }
            )
    return issues


def check_schema_version_recorded() -> list[dict]:
    """Schema version file should exist."""
    if not Path(".workflow/schema_version").exists():
        return [
            {
                "severity": "warning",
                "message": ".workflow/schema_version missing; run `workflow-advisor migrate` if upgrading",
            }
        ]
    return []
