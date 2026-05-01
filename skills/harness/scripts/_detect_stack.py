#!/usr/bin/env python3
"""
Detect the stack of a project from its manifest files. Emits a Markdown bullet
list suitable for dropping into the `## Stack signals` section of CLAUDE.md.

Usage: _detect_stack.py [project-dir]   (defaults to $PWD)

Reads (best-effort):
- composer.json  → PHP/Laravel ecosystem
- package.json   → Node/JS/TS ecosystem (incl. React, Next, Vue, Svelte hints)
- pyproject.toml → Python (ruff, mypy, pytest hints)
- go.mod         → Go
- Cargo.toml     → Rust
- Gemfile        → Ruby/Rails
- mix.exs        → Elixir/Phoenix

Output format: one bullet per stack family, plus a few "useful commands" hints
derived from script entries. Never raises — degrades to empty output if no
manifests are found.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys


def _safe_read(p: Path) -> str | None:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _safe_json(p: Path) -> dict | None:
    txt = _safe_read(p)
    if not txt:
        return None
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        return None


def _composer_packages(j: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for key in ("require", "require-dev"):
        for name, ver in (j.get(key) or {}).items():
            if name == "php":
                continue
            # Strip carets / tildes / wildcards for display.
            v = re.sub(r"^[\^~>=<\s]+", "", str(ver)).split("|")[0].strip()
            out[name] = v
    return out


def _node_packages(j: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for key in ("dependencies", "devDependencies"):
        for name, ver in (j.get(key) or {}).items():
            v = re.sub(r"^[\^~>=<\s]+", "", str(ver)).split("|")[0].strip()
            out[name] = v
    return out


def detect(root: Path) -> list[str]:
    bullets: list[str] = []

    # PHP / Laravel.
    composer = _safe_json(root / "composer.json")
    if composer:
        pkgs = _composer_packages(composer)
        php_ver = (composer.get("require") or {}).get("php", "")
        php_ver = re.sub(r"^[\^~>=<\s]+", "", php_ver).split("|")[0].strip()
        line_parts = []
        if php_ver:
            line_parts.append(f"PHP {php_ver}")
        if "laravel/framework" in pkgs:
            line_parts.append(f"Laravel {pkgs['laravel/framework']}")
        if "livewire/livewire" in pkgs:
            line_parts.append(f"Livewire {pkgs['livewire/livewire']}")
        if "laravel/pint" in pkgs:
            line_parts.append("Pint")
        if "larastan/larastan" in pkgs or "nunomaduro/larastan" in pkgs:
            line_parts.append("Larastan")
        if "pestphp/pest" in pkgs:
            line_parts.append("Pest")
        if "phpunit/phpunit" in pkgs and "pestphp/pest" not in pkgs:
            line_parts.append("PHPUnit")
        if line_parts:
            bullets.append("- " + ", ".join(line_parts))
        scripts = composer.get("scripts") or {}
        cmds = [s for s in ("lint:check", "lint", "test", "types:check") if s in scripts]
        if cmds:
            bullets.append("- Composer scripts: " + ", ".join(f"`composer {c}`" for c in cmds))

    # Node / JS / TS.
    pkgjson = _safe_json(root / "package.json")
    if pkgjson:
        deps = _node_packages(pkgjson)
        line_parts = []
        if "typescript" in deps:
            line_parts.append(f"TypeScript {deps['typescript']}")
        if "next" in deps:
            line_parts.append(f"Next {deps['next']}")
        elif "react" in deps:
            line_parts.append(f"React {deps['react']}")
        if "vue" in deps:
            line_parts.append(f"Vue {deps['vue']}")
        if "svelte" in deps or "@sveltejs/kit" in deps:
            line_parts.append(
                "SvelteKit" if "@sveltejs/kit" in deps else f"Svelte {deps['svelte']}"
            )
        if "tailwindcss" in deps:
            line_parts.append(f"Tailwind {deps['tailwindcss']}")
        if "vitest" in deps:
            line_parts.append("Vitest")
        elif "jest" in deps:
            line_parts.append("Jest")
        if not line_parts and (deps or pkgjson.get("scripts")):
            line_parts.append("Node + npm")
        if line_parts:
            bullets.append("- " + ", ".join(line_parts))
        scripts = pkgjson.get("scripts") or {}
        cmds = [
            s
            for s in ("lint:check", "lint", "types:check", "typecheck", "test", "format:check")
            if s in scripts
        ]
        if cmds:
            bullets.append("- npm scripts: " + ", ".join(f"`npm run {c}`" for c in cmds))

    # Python.
    pyproj = root / "pyproject.toml"
    if pyproj.exists():
        txt = _safe_read(pyproj) or ""
        line_parts = ["Python"]
        py_match = re.search(r'^\s*requires-python\s*=\s*"([^"]+)"', txt, re.MULTILINE)
        if py_match:
            line_parts.append(py_match.group(1).strip())
        for tool in ("ruff", "mypy", "pytest", "black"):
            if re.search(rf"^\s*\[tool\.{tool}", txt, re.MULTILINE):
                line_parts.append(tool)
        if "fastapi" in txt.lower():
            line_parts.append("FastAPI")
        if "django" in txt.lower():
            line_parts.append("Django")
        bullets.append("- " + ", ".join(line_parts))

    # Go.
    if (root / "go.mod").exists():
        txt = _safe_read(root / "go.mod") or ""
        m = re.search(r"^go\s+(\S+)", txt, re.MULTILINE)
        bullets.append(f"- Go{f' {m.group(1)}' if m else ''}")

    # Rust.
    if (root / "Cargo.toml").exists():
        txt = _safe_read(root / "Cargo.toml") or ""
        m = re.search(r'^\s*edition\s*=\s*"(\d{4})"', txt, re.MULTILINE)
        bullets.append(f"- Rust{f' (edition {m.group(1)})' if m else ''}, cargo")

    # Ruby.
    if (root / "Gemfile").exists():
        txt = _safe_read(root / "Gemfile") or ""
        line_parts = ["Ruby"]
        if "rails" in txt:
            line_parts.append("Rails")
        if "rspec" in txt:
            line_parts.append("RSpec")
        bullets.append("- " + ", ".join(line_parts))

    # Elixir.
    if (root / "mix.exs").exists():
        txt = _safe_read(root / "mix.exs") or ""
        line_parts = ["Elixir"]
        if "phoenix" in txt:
            line_parts.append("Phoenix")
        bullets.append("- " + ", ".join(line_parts))

    return bullets


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else os.getcwd()).resolve()
    bullets = detect(root)
    if not bullets:
        return 0  # silent — no manifests found
    print("\n".join(bullets))
    return 0


if __name__ == "__main__":
    sys.exit(main())
