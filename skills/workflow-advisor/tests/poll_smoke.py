#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from helpers.transport import poll  # noqa: E402


def main() -> int:
    since = poll._cursor_since("2026-05-09T12:00:00+00:00")
    parsed = datetime.fromisoformat(since)
    assert parsed == datetime(2026, 5, 9, 11, 59, tzinfo=timezone.utc)
    assert poll._cursor_since("not-a-date") == "not-a-date"
    assert poll._updated_after(
        {"updated_at": "2026-05-09T12:00:01+00:00"},
        datetime(2026, 5, 9, 12, 0, tzinfo=timezone.utc),
    )
    assert not poll._updated_after(
        {"updated_at": "2026-05-09T11:59:59+00:00"},
        datetime(2026, 5, 9, 12, 0, tzinfo=timezone.utc),
    )

    commands = []

    def fake_run(command: list[str], **kwargs) -> subprocess.CompletedProcess:
        commands.append(command)
        payload = [
            {"number": 1, "updated_at": "2026-05-09T11:59:00+00:00"},
            {"number": 2, "updated_at": "2026-05-09T12:01:00+00:00"},
        ]
        return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")

    original_run = poll.subprocess.run
    poll.subprocess.run = fake_run
    try:
        prs = poll._fetch_since("example/repo", "pull_requests", "2026-05-09T12:00:00+00:00")
    finally:
        poll.subprocess.run = original_run
    assert "since=" not in commands[0][-1]
    assert [pr["number"] for pr in prs] == [2]

    push_events = poll._items_to_events(
        "pushes",
        {
            "sha": "after",
            "parents": [{"sha": "before"}],
            "commit": {"message": "change"},
        },
        default_branch="trunk",
    )
    assert push_events[0]["payload"]["branch"] == "trunk"
    assert push_events[0]["name"] == "push.protected_branch"
    print("poll smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
