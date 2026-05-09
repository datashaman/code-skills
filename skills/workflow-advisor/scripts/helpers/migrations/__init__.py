"""
helpers/migrations package.

Schema migrations between versions of `.workflow/`.

Each migration is a function that takes the current state and returns
the migrated state. Migrations are linear: from version N, apply
migration N → N+1, then N+1 → N+2, etc.

For v1 there's only schema_version 1, so this is mostly a placeholder.
The structure is in place for future versions.
"""

from __future__ import annotations

import logging
from typing import Callable

from .. import config_io

logger = logging.getLogger(__name__)


LATEST_VERSION = 1


# Migration registry — keyed by source version. Each function migrates
# from version N to N+1.
MIGRATIONS: dict[int, Callable[[], None]] = {}


def register_migration(from_version: int):
    """Decorator to register a migration function."""

    def wrap(fn: Callable[[], None]) -> Callable[[], None]:
        MIGRATIONS[from_version] = fn
        return fn

    return wrap


def run(from_version: int, to_version: int, dry_run: bool = False) -> None:
    """
    Apply migrations sequentially from `from_version` to `to_version`.
    """
    if from_version >= to_version:
        return

    for version in range(from_version, to_version):
        migration = MIGRATIONS.get(version)
        if migration is None:
            raise RuntimeError(
                f"No migration registered from schema version {version}; target is {to_version}"
            )

        logger.info(f"Migration {version} → {version + 1} ({'dry-run' if dry_run else 'apply'})")
        if not dry_run:
            migration()
            config_io.write_schema_version(version + 1)


# Example placeholder for a future migration:
#
# @register_migration(from_version=1)
# def migrate_1_to_2() -> None:
#     """v1 → v2: rename `cascade.preserve_in_flight` to `cascade.in_flight_protection`."""
#     config = config_io.load()
#     cascade = config.get("cascade", {})
#     if "preserve_in_flight" in cascade:
#         cascade["in_flight_protection"] = cascade.pop("preserve_in_flight")
#         config_io.save(config)
