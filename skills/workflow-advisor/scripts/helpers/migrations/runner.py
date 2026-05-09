"""
Migration runner facade used by the workflow-advisor CLI.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from helpers import config_io, migrations


@dataclass(frozen=True)
class MigrationPlanItem:
    id: str
    description: str


def get_schema_version(workflow_dir: Path) -> int:
    version_file = workflow_dir / "schema_version"
    if not version_file.exists():
        return 1
    return int(version_file.read_text().strip())


def skill_current_schema_version() -> int:
    return migrations.LATEST_VERSION


def plan(current: int, target: int) -> list[MigrationPlanItem]:
    items = []
    for version in range(current, target):
        if version not in migrations.MIGRATIONS:
            items.append(
                MigrationPlanItem(
                    id=f"{version}-to-{version + 1}",
                    description="missing migration implementation",
                )
            )
        else:
            items.append(
                MigrationPlanItem(
                    id=f"{version}-to-{version + 1}",
                    description=migrations.MIGRATIONS[version].__doc__ or "schema migration",
                )
            )
    return items


def run_migrations(workflow_dir: Path, from_version: int, to_version: int, args=None) -> None:
    if from_version >= to_version:
        return
    migrations.run(from_version, to_version, dry_run=bool(getattr(args, "dry_run", False)))
    config_io.write_schema_version(to_version)
