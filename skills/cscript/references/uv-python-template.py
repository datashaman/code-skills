#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   # Add runtime deps here, e.g. "requests>=2.32", "pillow>=10.4".
#   # `uv run` resolves and caches these the first time the script runs.
# ]
# ///
"""NAME: example-name
DESC: One-line description in present tense, no trailing period
USAGE: example-name <required-arg> [--flag]

Keep the NAME / DESC / USAGE lines at the top of the docstring. `cscript show`
surfaces them above the source. The DESC line is what `cscript which` matches.
"""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="example-name",
        description="One-line description.",
    )
    p.add_argument("required", help="What this positional is for.")
    p.add_argument("--flag", action="store_true", help="What this flag does.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # --- implementation below ---
    _ = args
    return 0


if __name__ == "__main__":
    sys.exit(main())
