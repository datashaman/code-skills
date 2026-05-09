#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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
    print("templates smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
