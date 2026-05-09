#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "minimal-repo"
sys.path.insert(0, str(ROOT / "scripts"))

from helpers.reconcile import checkpoint  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        shutil.copytree(FIXTURE, repo, dirs_exist_ok=True)
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
        cwd = Path.cwd()
        try:
            import os

            os.chdir(repo)
            result = checkpoint.reconcile_with_checkpoint(
                "event_driven",
                {
                    "event": {
                        "id": "checkpoint-smoke",
                        "name": "pull_request.opened",
                        "payload": {"files": ["docs/specs/demo.md"], "pr_number": 42},
                    }
                },
            )
            assert result["commit"]
            assert (repo / ".workflow" / "state" / "processed_events.yml").exists()
        finally:
            os.chdir(cwd)

    print("checkpoint smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
