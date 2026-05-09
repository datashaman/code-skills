#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from helpers import template  # noqa: E402


def main() -> int:
    expected = {
        "architect",
        "developer",
        "end_user",
        "legal",
        "operator",
        "product",
        "security",
        "sre",
        "support",
    }
    templates = ROOT / "references" / "templates"
    missing = [
        audience for audience in expected if not (templates / f"audience-{audience}.md").exists()
    ]
    assert not missing, missing
    previous = Path.cwd()
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        os.chdir(repo)
        try:
            generic = repo / ".workflow" / "templates"
            profile = generic / "security"
            profile.mkdir(parents=True)
            generic.mkdir(parents=True, exist_ok=True)
            (generic / "review.md").write_text("generic")
            (profile / "review.md").write_text("profile")
            assert template.find_template("review.md", profile="security").read_text() == "profile"
        finally:
            os.chdir(previous)
    print("templates smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
