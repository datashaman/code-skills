#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
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
        record = provider_actions.queue_action(
            "labels.apply_diff",
            {"repo": "example/repo", "item_number": 42},
            reason="smoke",
            queue_path=queue_path,
        )
        line = json.loads(queue_path.read_text())
        assert line["action"] == record["action"] == "labels.apply_diff"
        assert line["status"] == "pending"

    print("provider actions smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
