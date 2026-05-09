#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from helpers.transport import poll  # noqa: E402


def main() -> int:
    since = poll._cursor_since("2026-05-09T12:00:00+00:00")
    parsed = datetime.fromisoformat(since)
    assert parsed == datetime(2026, 5, 9, 11, 59, tzinfo=timezone.utc)
    assert poll._cursor_since("not-a-date") == "not-a-date"
    print("poll smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
