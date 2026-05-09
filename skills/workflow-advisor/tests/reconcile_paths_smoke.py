#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "minimal-repo"
EVENT = ROOT / "tests" / "fixtures" / "events" / "pr_opened.json"


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        shutil.copytree(FIXTURE, repo)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=test",
                "-c",
                "user.email=test@example.com",
                "commit",
                "-qm",
                "fixture",
            ],
            cwd=repo,
            check=True,
        )

        subdir = repo / "nested" / "subdir"
        subdir.mkdir(parents=True)
        cli = ROOT / "scripts" / "cli.py"
        config = repo / ".workflow" / "config.yml"
        subprocess.run(
            [
                sys.executable,
                str(cli),
                "--config",
                str(config),
                "reconcile",
                "--event-name",
                "pull_request",
                "--event-payload",
                str(EVENT),
            ],
            cwd=subdir,
            check=True,
            capture_output=True,
            text=True,
        )

        assert not (subdir / ".workflow").exists()
        assert (repo / ".workflow" / "state" / "processed_events.yml").exists()
        assert (repo / ".workflow" / "metrics" / "events.jsonl").exists()
        message = subprocess.run(
            ["git", "log", "-1", "--pretty=%B"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        assert "workflow: pull_request.opened" in message
        assert "trigger: pull_request.opened by @octocat" in message
        assert "trigger: manual" not in message

    print("reconcile paths smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
