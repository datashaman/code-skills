#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from helpers import state_io  # noqa: E402
from helpers.transport import receiver  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "processed_events.yml"
        state_io.save_processed_events(path, {"a", "b"})
        assert state_io.load_processed_events(path) == {"a", "b"}
        path.write_text("- c\n- d\n")
        assert state_io.load_processed_events(path) == {"c", "d"}
        path.write_text("delivery_ids:\n- e\n- f\n")
        assert state_io.load_processed_events(path) == {"e", "f"}

        receiver_path = Path(tmp) / "receiver_processed_events.yml"
        original = receiver.PROCESSED_EVENTS_FILE
        receiver.PROCESSED_EVENTS_FILE = receiver_path
        try:
            receiver_path.write_text("- delivery-1\n")
            assert receiver._already_processed("delivery-1")
            receiver._mark_processed("delivery-2")
            assert state_io.load_processed_events(receiver_path) == {
                "delivery-1",
                "delivery-2",
            }
        finally:
            receiver.PROCESSED_EVENTS_FILE = original
    print("state io smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
