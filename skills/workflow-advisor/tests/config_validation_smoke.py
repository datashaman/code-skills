#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def main() -> int:
    from helpers import config_io, interview

    config = interview.build_default_config("example/config")
    config_io.validate(config)

    bad_mode = dict(config)
    bad_mode["provider_actions"] = {"mode": "now"}
    try:
        config_io.validate(bad_mode)
    except config_io.ConfigError as exc:
        assert "provider_actions.mode" in str(exc)
    else:
        raise AssertionError("invalid provider action mode passed validation")

    bad_profile = dict(config)
    bad_profile["profiles"] = {"spec-driven": {"enabled": "yes"}}
    try:
        config_io.validate(bad_profile)
    except config_io.ConfigError as exc:
        assert "profiles.spec-driven.enabled" in str(exc)
    else:
        raise AssertionError("invalid profile enabled value passed validation")

    print("config validation smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
