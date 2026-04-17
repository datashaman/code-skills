#!/usr/bin/env python3
"""
Inspect Claude Code's per-project MCP connection logs to surface servers
whose tool schemas load every turn but which never actually connect.

Also reads ~/.claude/mcp-needs-auth-cache.json to surface claude.ai MCP
servers that are configured but not authenticated.

Usage:  scan_mcp_logs.py [days=30]
"""

import glob
import json
import os
import sys
import time


def find_log_root(home, slug):
    for candidate in (
        os.path.join(home, "Library/Caches/claude-cli-nodejs", slug),
        os.path.join(home, ".cache/claude-cli-nodejs", slug),
    ):
        if os.path.isdir(candidate):
            return candidate
    return None


def load_user_configured_servers(home):
    """Return the set of MCP server names the user has added to
    ~/.claude.json (mcpServers). Anything NOT in this set and
    appearing in the log dirs is a built-in (claude.ai *) server."""
    path = os.path.join(home, ".claude.json")
    if not os.path.isfile(path):
        return set()
    try:
        with open(path) as f:
            d = json.load(f)
    except Exception:
        return set()
    names = set((d.get("mcpServers") or {}).keys())
    # also per-project mcpServers
    proj = d.get("projects", {}).get(os.getcwd(), {}) or {}
    names.update((proj.get("mcpServers") or {}).keys())
    return names


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    home = os.path.expanduser("~")
    cwd = os.getcwd()
    slug = cwd.replace("/", "-")
    root = find_log_root(home, slug)
    user_configured = load_user_configured_servers(home)
    out = {
        "root": root,
        "user_configured_servers": sorted(user_configured),
        "servers": {},
        "needs_auth": [],
    }

    if root:
        cutoff = time.time() - days * 86400
        for d in sorted(glob.glob(os.path.join(root, "mcp-logs-*"))):
            server = os.path.basename(d).replace("mcp-logs-", "")
            files = [
                f for f in glob.glob(os.path.join(d, "*.jsonl")) if os.path.getmtime(f) >= cutoff
            ]
            errors = conn_fail = 0
            for fp in files:
                try:
                    with open(fp) as f:
                        for line in f:
                            try:
                                j = json.loads(line)
                            except Exception:
                                continue
                            if "error" in j:
                                errors += 1
                            if "Connection failed" in json.dumps(j):
                                conn_fail += 1
                except Exception:
                    pass
            # Log dir names use dashes; user-configured names in
            # ~/.claude.json may use dots/spaces. Normalize for lookup.
            normalized = server.replace("-", "").replace(".", "").replace(" ", "").lower()
            is_user_configured = any(
                normalized == n.replace("-", "").replace(".", "").replace(" ", "").lower()
                for n in user_configured
            )
            out["servers"][server] = {
                "sessions": len(files),
                "errors": errors,
                "connection_failures": conn_fail,
                "broken": len(files) > 0 and conn_fail >= len(files),
                "origin": "user" if is_user_configured else "builtin",
            }

    auth_cache = os.path.join(home, ".claude/mcp-needs-auth-cache.json")
    if os.path.isfile(auth_cache):
        try:
            with open(auth_cache) as f:
                out["needs_auth"] = sorted(json.load(f).keys())
        except Exception:
            pass

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
