"""
helpers/config_io.py

Load, save, and validate .workflow/config.yml against the schema.

The config file is the team's process declaration. It must be valid
YAML, conform to the schema, and reference only known profiles, roles,
and labels. Validation runs on every read in non-trusted contexts (CI)
and on every save.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

WORKFLOW_DIR = Path(".workflow")
CONFIG_FILE = WORKFLOW_DIR / "config.yml"
SCHEMA_VERSION_FILE = WORKFLOW_DIR / "schema_version"

# Mirrors the schema shape; kept simple so it can be checked without a
# heavy validation library.
REQUIRED_TOP_LEVEL_FIELDS = ["repo", "profiles", "lifecycle", "roles", "transport"]
KNOWN_PROFILES = [
    "spec-driven",
    "testability",
    "observability",
    "documentation",
    "security",
    "accessibility",
    "compliance",
]
KNOWN_TRANSPORTS = [
    "github_actions",
    "gh_forward",
    "self_hosted_webhook",
    "github_app",
    "polling",
    "on_demand_only",
]


class ConfigError(Exception):
    """Raised on validation failure."""


def load() -> dict[str, Any]:
    """Load and validate the active config."""
    if not CONFIG_FILE.exists():
        raise ConfigError(
            f"{CONFIG_FILE} not found. Run `workflow-advisor interview` to bootstrap."
        )
    return load_from_path(CONFIG_FILE)


def load_from_path(path: Path | str) -> dict[str, Any]:
    """Load and validate config at an explicit path (used by simulate)."""
    path = Path(path)
    with path.open() as f:
        config = yaml.safe_load(f)
    validate(config)
    return config


def load_or_default(path: Path | str | None = None) -> dict[str, Any]:
    """Load a config if present; otherwise return a minimal interview scaffold."""
    path = Path(path) if path is not None else CONFIG_FILE
    if path.exists():
        return load_from_path(path)
    return {
        "schema_version": 1,
        "repo": {"provider": "github", "identifier": "unknown/unknown"},
        "profiles": {},
        "lifecycle": {"composition": {}},
        "roles": {},
        "transport": {"mode": "on_demand_only"},
    }


def save(config: dict[str, Any], path: Path | str | None = None) -> None:
    """Validate and save the config."""
    validate(config)
    target = Path(path) if path is not None else CONFIG_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w") as f:
        yaml.dump(config, f, sort_keys=False, default_flow_style=False)
    logger.info(f"Saved config to {target}")


def read_schema_version() -> int:
    """Read the schema version. Defaults to 1 if not present."""
    if not SCHEMA_VERSION_FILE.exists():
        return 1
    return int(SCHEMA_VERSION_FILE.read_text().strip())


def write_schema_version(version: int) -> None:
    """Write the schema version after migration."""
    SCHEMA_VERSION_FILE.write_text(f"{version}\n")


def validate(config: dict[str, Any]) -> None:
    """
    Validate config structure. Raises ConfigError with a clear message
    on failure. Does not validate semantic correctness (e.g., that
    referenced roles exist) — that's done by validators in the relevant
    helpers.
    """
    if not isinstance(config, dict):
        raise ConfigError("Config must be a YAML mapping at the top level.")

    # Required top-level fields
    missing = [f for f in REQUIRED_TOP_LEVEL_FIELDS if f not in config]
    if missing:
        raise ConfigError(f"Missing required fields: {', '.join(missing)}")

    # Profiles
    profiles = config.get("profiles", {})
    for name in profiles:
        if name not in KNOWN_PROFILES:
            raise ConfigError(f"Unknown profile {name!r}. Known: {', '.join(KNOWN_PROFILES)}.")

    # Transport
    transport = config.get("transport", {})
    mode = transport.get("mode")
    if mode not in KNOWN_TRANSPORTS:
        raise ConfigError(f"Unknown transport.mode {mode!r}. Known: {', '.join(KNOWN_TRANSPORTS)}.")

    # Repo
    repo = config.get("repo", {})
    if not repo.get("identifier"):
        raise ConfigError("repo.identifier is required (e.g., 'org/repo').")
    if repo.get("provider") not in ("github",):
        raise ConfigError(f"Unsupported provider {repo.get('provider')!r}. v1 supports 'github'.")

    # Lifecycle
    lifecycle = config.get("lifecycle", {})
    if "composition" not in lifecycle:
        raise ConfigError("lifecycle.composition is required.")

    logger.debug("Config validation passed.")


def diff(before: dict, after: dict) -> dict[str, Any]:
    """
    Compute a structural diff between two config states. Returns a dict
    with 'added', 'removed', 'changed' keys, scoped per top-level
    section. Used by repo.config_changed handler to determine what
    cascade is needed.
    """
    result: dict[str, Any] = {"added": {}, "removed": {}, "changed": {}}

    all_keys = set(before) | set(after)
    for k in all_keys:
        if k not in before:
            result["added"][k] = after[k]
        elif k not in after:
            result["removed"][k] = before[k]
        elif before[k] != after[k]:
            result["changed"][k] = {"before": before[k], "after": after[k]}

    return result
