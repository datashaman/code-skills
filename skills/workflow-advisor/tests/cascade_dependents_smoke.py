#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import tempfile

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from helpers.reconcile import cascade  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        cwd = Path.cwd()
        root = Path(tmp)
        try:
            import os

            os.chdir(root)
            for dirname in ("impl-plans", "test-plans", "obs-plans", "threat-models"):
                path = root / ".workflow" / "artifacts" / dirname
                path.mkdir(parents=True, exist_ok=True)
                with (path / "demo.yml").open("w") as f:
                    yaml.dump({"id": "demo", "state": "approved"}, f)

            artifact = {"type": "spec", "id": "demo"}
            deps = cascade.find_dependents(artifact, {})
            categories = {dep["category"] for dep in deps}
            assert {"impl_plan", "test_plan", "obs_plan", "threat_model"} <= categories

            plan = cascade.compute(
                {"artifacts": [{**artifact, "changed": True}]},
                {"artifact:spec:demo": {"classification": "substantive"}},
                {
                    "cascade": {
                        "spec_substantive_change": {
                            "impl_plan": "revert_to_draft",
                            "test_plan": "revert_to_draft",
                            "obs_plan": "revert_to_draft",
                            "threat_model": "revert_to_draft",
                        }
                    }
                },
            )
            targets = {(action["target"]["type"], action["action"]) for action in plan["actions"]}
            assert ("impl_plan", "revert_to_draft") in targets
            assert ("test_plan", "revert_to_draft") in targets
            assert ("obs_plan", "revert_to_draft") in targets
            assert ("threat_model", "revert_to_draft") in targets
        finally:
            os.chdir(cwd)

    print("cascade dependents smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
