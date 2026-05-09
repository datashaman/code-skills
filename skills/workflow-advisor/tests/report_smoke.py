#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from helpers import metrics  # noqa: E402


def main() -> int:
    previous = Path.cwd()
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        os.chdir(repo)
        try:
            active = repo / ".workflow" / "lifecycle" / "active"
            active.mkdir(parents=True)
            (active / "pr-42.yml").write_text(
                """
type: pr
id: 42
stage: review
owner: "@lead"
reviewers:
  requested:
    - "@reviewer"
approvals:
  received:
    - "@approver"
linked_artifacts:
  specs:
    - demo
  adrs:
    - adr-001
instrumentation:
  metrics: true
metrics:
  baseline_captured: true
  post_release_reviewed: false
""".lstrip()
            )

            events = repo / ".workflow" / "metrics" / "events.jsonl"
            events.parent.mkdir(parents=True)
            events.write_text(
                json.dumps(
                    {
                        "ts": "2026-05-09T00:00:00+00:00",
                        "artifacts_observed": 2,
                        "artifacts_changed": 1,
                        "lifecycle_items_observed": 1,
                        "sidecars_written": 1,
                        "lifecycle_updated": 1,
                        "cascades_failed": 0,
                    }
                )
                + "\n"
            )

            role = metrics.compute_report("role-load")
            docs = metrics.compute_report("documentation")
            obs = metrics.compute_report("observability")

            assert "not implemented" not in role.lower()
            assert "@lead" in role
            assert "specs: 1" in docs
            assert "Baseline metrics captured: 1" in obs

            parsed = json.loads(metrics.compute_report("observability", render_as="json"))
            assert parsed["metrics_enabled_items"] == 1
        finally:
            os.chdir(previous)

    print("report smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
