#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from helpers import provider_actions  # noqa: E402


def main() -> int:
    labels = provider_actions.labels_apply_diff(
        "example/repo",
        42,
        {"add": ["type:feature"], "remove": ["blocked:old"]},
    )
    assert labels["dry_run"] is True
    assert len(labels["commands"]) == 2
    assert labels["commands"][0][:3] == ["gh", "api", "repos/example/repo/issues/42/labels"]

    comment = provider_actions.comment_update_or_post(
        "example/repo",
        42,
        "Status changed.",
        marker="workflow-advisor:status",
    )
    assert "<!-- workflow-advisor:status -->" in comment["commands"][0][-1]

    reviewers = provider_actions.assign_reviewers("example/repo", 42, ["@octocat"])
    assert "reviewers[]=octocat" in reviewers["commands"][0]

    with tempfile.TemporaryDirectory() as tmp:
        queue_path = Path(tmp) / "pending.jsonl"
        applied_path = Path(tmp) / "applied.jsonl"
        failed_path = Path(tmp) / "failed.jsonl"
        record = provider_actions.queue_action(
            "labels.apply_diff",
            {
                "repo": "example/repo",
                "item_number": 42,
                "diff": {"add": ["type:feature"], "remove": []},
            },
            reason="smoke",
            queue_path=queue_path,
        )
        line = json.loads(queue_path.read_text())
        assert line["action"] == record["action"] == "labels.apply_diff"
        assert line["status"] == "pending"

        dry = provider_actions.flush_queue(
            dry_run=True,
            queue_path=queue_path,
            applied_path=applied_path,
            failed_path=failed_path,
        )
        assert dry["pending"] == 1
        assert dry["remaining"] == 1
        assert queue_path.read_text().strip()
        assert not applied_path.exists()

        calls = []

        def fake_runner(command: list[str]) -> subprocess.CompletedProcess:
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, "", "")

        applied = provider_actions.flush_queue(
            dry_run=False,
            queue_path=queue_path,
            applied_path=applied_path,
            failed_path=failed_path,
            runner=fake_runner,
        )
        assert applied["applied"] == 1
        assert applied["failed"] == 0
        assert len(calls) == 1
        assert not queue_path.read_text().strip()
        assert json.loads(applied_path.read_text())["status"] == "applied"

        provider_actions.queue_action(
            "unknown.action",
            {"repo": "example/repo"},
            queue_path=queue_path,
        )
        failed = provider_actions.flush_queue(
            dry_run=False,
            queue_path=queue_path,
            applied_path=applied_path,
            failed_path=failed_path,
            runner=fake_runner,
        )
        assert failed["failed"] == 1
        assert failed["remaining"] == 1
        assert "unknown provider action" in failed["results"][0]["error"]

    print("provider actions smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
