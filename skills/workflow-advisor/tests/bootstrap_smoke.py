#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        cli = ROOT / "scripts" / "cli.py"

        questions = subprocess.run(
            [sys.executable, str(cli), "interview"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        )
        assert "review_policy.codeowners_required" in questions.stdout

        out = repo / ".workflow" / "config.yml"
        subprocess.run(
            [
                sys.executable,
                str(cli),
                "interview",
                "--write-default",
                "--repo",
                "example/bootstrap",
            ],
            cwd=repo,
            check=True,
        )
        assert out.exists()
        assert (repo / ".workflow" / "schema_version").read_text().strip() == "1"

        validate = subprocess.run(
            [sys.executable, str(cli), "--config", str(out), "doctor"],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        assert validate.returncode in {0, 1}
        assert "config invalid" not in validate.stdout

        shutil.rmtree(repo / ".workflow")

    print("bootstrap smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
