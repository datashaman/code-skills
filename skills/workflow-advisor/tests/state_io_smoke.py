#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from helpers import state_io  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "processed_events.yml"
        state_io.save_processed_events(path, {"a", "b"})
        assert state_io.load_processed_events(path) == {"a", "b"}
        path.write_text("- c\n- d\n")
        assert state_io.load_processed_events(path) == {"c", "d"}
    print("state io smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
