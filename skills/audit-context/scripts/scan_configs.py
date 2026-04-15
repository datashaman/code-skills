#!/usr/bin/env python3
"""
Inventory static Claude Code configuration that contributes to context:
skills, agents, commands, plugins, MCP config files, CLAUDE.md health,
and miscellaneous settings that matter for per-turn cost.

Usage:  scan_configs.py
"""
import os, re, sys, json, glob, time


HOME = os.path.expanduser("~")
CWD = os.getcwd()


# Registry of MCP servers where a CLI alternative is usually a
# better trade-off: zero token cost when idle, the agent only pays
# for the specific command output it requests.
#
# Each entry matches by one or more of:
#   - `name`: substrings to match against the MCP server name
#     (case-insensitive)
#   - `pkg`: substrings to match against the server's command/args
#     (npm package names, docker images, URL hostnames)
#
# Match patterns are deliberately loose — a single hit flags the
# server as a CLI-alternative candidate.
CLI_ALTERNATIVES = [
    {"name": ["github"], "pkg": ["server-github", "github-mcp"],
     "cli": "gh", "reason": "GitHub MCP ships ~40+ tools. `gh` covers almost all of it (issues, PRs, workflows, releases, repos) at zero context cost when idle."},
    {"name": ["gitlab"], "pkg": ["server-gitlab", "gitlab-mcp"],
     "cli": "glab", "reason": "GitLab MCP is similarly heavy; `glab` is the official CLI."},
    {"name": ["aws"], "pkg": ["aws-mcp", "server-aws"],
     "cli": "aws", "reason": "AWS MCP wraps the SDK; the `aws` CLI has the same surface area with no per-turn cost."},
    {"name": ["gcp", "google-cloud", "googlecloud"], "pkg": ["gcp-mcp", "server-gcp"],
     "cli": "gcloud", "reason": "`gcloud` covers GCP resource management at zero idle cost."},
    {"name": ["kubernetes", "k8s", "kubectl"], "pkg": ["kubernetes-mcp", "k8s-mcp"],
     "cli": "kubectl", "reason": "`kubectl` is the canonical K8s CLI; the MCP adds latency and context for no functional gain."},
    {"name": ["docker"], "pkg": ["docker-mcp", "server-docker"],
     "cli": "docker", "reason": "`docker` CLI covers images, containers, compose — MCP is pure overhead."},
    {"name": ["terraform"], "pkg": ["terraform-mcp"],
     "cli": "terraform", "reason": "Terraform CLI is the standard interface; MCP wrappers duplicate it."},
    {"name": ["stripe"], "pkg": ["stripe-mcp"],
     "cli": "stripe", "reason": "Stripe CLI is lightweight and offers the same functionality."},
    {"name": ["sentry"], "pkg": ["sentry-mcp"],
     "cli": "sentry-cli", "reason": "`sentry-cli` covers release + event management."},
    {"name": ["postgres", "postgresql"], "pkg": ["postgres-mcp", "server-postgres"],
     "cli": "psql", "reason": "`psql` is the canonical Postgres CLI; MCP wrappers rarely add value."},
    {"name": ["jira", "atlassian"], "pkg": ["jira-mcp", "atlassian-mcp"],
     "cli": "acli", "reason": "Atlassian's `acli` (or jira-cli) is the usual replacement."},
    {"name": ["trello"], "pkg": ["trello-mcp"],
     "cli": "trello", "reason": "`trello` CLI (mheap/trello-cli) covers board / list / card ops."},
    {"name": ["linear"], "pkg": ["linear-mcp"],
     "cli": "linear", "reason": "Linear CLI + API work well; MCP adds per-turn schema load."},
    {"name": ["playwright"], "pkg": ["playwright-mcp"],
     "cli": "playwright", "reason": "Playwright CLI (via `npx playwright`) drives the same browser automation."},
    {"name": ["puppeteer"], "pkg": ["puppeteer-mcp"],
     "cli": "puppeteer (node script)", "reason": "Direct puppeteer usage from a node script keeps context clean."},
    {"name": ["brave-search", "bravesearch"], "pkg": ["brave-search"],
     "cli": "WebSearch tool", "reason": "Claude Code's built-in WebSearch tool already covers general search."},
    {"name": ["fetch", "server-fetch"], "pkg": ["server-fetch"],
     "cli": "WebFetch tool", "reason": "Claude Code's built-in WebFetch tool already covers URL retrieval."},
    {"name": ["filesystem"], "pkg": ["server-filesystem"],
     "cli": "native Read/Write/Bash", "reason": "Claude Code's built-in file tools are strictly cheaper."},
    {"name": ["memory"], "pkg": ["server-memory"],
     "cli": "auto-memory / CLAUDE.md", "reason": "Claude Code's auto-memory system covers the same ground without per-turn cost."},
]


def match_cli_alternatives(name, command, args):
    """Return matching CLI-alternative entries for an MCP server."""
    haystack_name = (name or "").lower()
    haystack_cmd = " ".join([command or ""] + (args or [])).lower()
    matches = []
    for entry in CLI_ALTERNATIVES:
        if any(p in haystack_name for p in entry["name"]):
            matches.append(entry)
            continue
        if any(p in haystack_cmd for p in entry["pkg"]):
            matches.append(entry)
    return matches


def read_text(path):
    try:
        with open(path) as f:
            return f.read()
    except Exception:
        return ""


def count_lines(path):
    try:
        with open(path) as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def body_lines(path):
    """Count lines in a markdown body, excluding YAML frontmatter."""
    try:
        with open(path) as f:
            text = f.read()
    except Exception:
        return 0
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            text = parts[2]
    return len([l for l in text.splitlines() if l.strip() or True])


def inventory_markdown_dir(base, scope):
    """Inventory a directory of .md files or <name>/SKILL.md-style entries."""
    out = []
    if not os.path.isdir(base):
        return out
    for name in sorted(os.listdir(base)):
        full = os.path.join(base, name)
        if os.path.isdir(full):
            for cand in ("SKILL.md", "AGENT.md", "COMMAND.md", f"{name}.md"):
                p = os.path.join(full, cand)
                if os.path.isfile(p):
                    out.append({
                        "name": name, "scope": scope, "path": p,
                        "body_lines": body_lines(p),
                        "mtime": int(os.path.getmtime(p)),
                    })
                    break
        elif full.endswith(".md"):
            out.append({
                "name": os.path.splitext(name)[0], "scope": scope, "path": full,
                "body_lines": body_lines(full),
                "mtime": int(os.path.getmtime(full)),
            })
    return out


def follow_imports(path, seen=None):
    """Return list of (path, line_count) for a CLAUDE.md and any @imports."""
    if seen is None:
        seen = set()
    results = []
    if not path or path in seen or not os.path.isfile(path):
        return results
    seen.add(path)
    results.append({
        "path": path,
        "lines": count_lines(path),
        "mtime": int(os.path.getmtime(path)),
    })
    base = os.path.dirname(path)
    try:
        with open(path) as f:
            for line in f:
                m = re.match(r"\s*@([^\s]+)", line)
                if m:
                    ref = m.group(1)
                    candidate = ref if os.path.isabs(ref) else os.path.join(base, ref)
                    candidate = os.path.expanduser(candidate)
                    results.extend(follow_imports(candidate, seen))
    except Exception:
        pass
    return results


def ghost_refs_in_claude_md(files, known_slash_names):
    """Find /slash-name references in CLAUDE.md files that don't resolve."""
    ghosts = []
    pattern = re.compile(r"(?:^|\s)/([a-zA-Z][a-zA-Z0-9_-]{1,40})\b")
    for entry in files:
        text = read_text(entry["path"])
        for m in pattern.finditer(text):
            name = m.group(1)
            if name.lower() in {"help", "clear", "context", "mcp", "memory",
                                "skills", "exit", "compact", "login", "logout",
                                "model", "cost", "config", "init", "bug"}:
                continue
            if name not in known_slash_names:
                ghosts.append({"file": entry["path"], "ref": f"/{name}"})
    return ghosts


def load_settings(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def managed_settings_paths():
    """Managed settings locations across platforms. These are enterprise
    / MDM settings that take highest precedence and cannot be overridden."""
    return [
        "/Library/Application Support/ClaudeCode/managed-settings.json",  # macOS
        "/etc/claude-code/managed-settings.json",                          # Linux/WSL
        r"C:\Program Files\ClaudeCode\managed-settings.json",              # Windows
    ]


def find_mcp_json_files(start):
    """Walk from cwd up to $HOME looking for .mcp.json files."""
    found = []
    cur = os.path.abspath(start)
    home = os.path.abspath(HOME)
    while True:
        cand = os.path.join(cur, ".mcp.json")
        if os.path.isfile(cand):
            found.append(cand)
        parent = os.path.dirname(cur)
        if parent == cur or cur == home:
            break
        cur = parent
    return found


def main():
    out = {"cwd": CWD}

    # Settings files across all scopes. Merge precedence (lowest to
    # highest, per https://code.claude.com/docs/en/settings.md):
    #   user < user_local < project < project_local < managed
    # user_local isn't in the official precedence table but Claude Code
    # reads it in practice; managed takes effect across all platforms.
    user_settings = load_settings(os.path.join(HOME, ".claude/settings.json"))
    user_local = load_settings(os.path.join(HOME, ".claude/settings.local.json"))
    project_settings = load_settings(os.path.join(CWD, ".claude/settings.json"))
    project_local = load_settings(os.path.join(CWD, ".claude/settings.local.json"))

    managed = {}
    managed_found_at = None
    for p in managed_settings_paths():
        if os.path.isfile(p):
            managed = load_settings(p)
            managed_found_at = p
            break

    out["settings"] = {
        "user": user_settings,
        "user_local": user_local,
        "project": project_settings,
        "project_local": project_local,
        "managed": managed,
        "managed_path": managed_found_at,
    }

    # Misc settings that matter for context cost — merged in precedence
    # order so later sources override earlier ones.
    merged = {}
    for s in (user_settings, user_local, project_settings, project_local, managed):
        merged.update(s)
    out["misc"] = {
        "disableAllHooks": merged.get("disableAllHooks", False),
        "disableSkillShellExecution": merged.get("disableSkillShellExecution", False),
        "autoCompactWindow": merged.get("autoCompactWindow"),
        "env_BASH_MAX_OUTPUT_LENGTH": (merged.get("env") or {}).get("BASH_MAX_OUTPUT_LENGTH"),
        "advisorModel": merged.get("advisorModel"),
        "fastMode": merged.get("fastMode"),
        "agent": merged.get("agent"),
        "outputStyle": merged.get("outputStyle"),
        "skillListingBudgetFraction": merged.get("skillListingBudgetFraction"),
        "skillListingMaxDescChars": merged.get("skillListingMaxDescChars"),
    }

    # Hooks (all scopes, including managed)
    hook_sources = {
        "user": (user_settings.get("hooks") or {}),
        "user_local": (user_local.get("hooks") or {}),
        "project": (project_settings.get("hooks") or {}),
        "project_local": (project_local.get("hooks") or {}),
        "managed": (managed.get("hooks") or {}),
    }
    hook_counts = {}
    for scope, hooks in hook_sources.items():
        count = sum(len(v) for v in hooks.values() if isinstance(v, list))
        if count:
            hook_counts[scope] = count
    out["hooks"] = hook_counts

    # Plugins
    out["plugins_enabled"] = list((merged.get("enabledPlugins") or {}).keys())

    # MCP servers with CLI alternatives. Read user-configured servers
    # from ~/.claude.json (global + per-project) and any .mcp.json files
    # walked from cwd; match each against the CLI_ALTERNATIVES registry.
    mcp_servers = {}
    claude_json = load_settings(os.path.join(HOME, ".claude.json"))
    mcp_servers.update(claude_json.get("mcpServers") or {})
    proj = claude_json.get("projects", {}).get(CWD, {}) or {}
    mcp_servers.update(proj.get("mcpServers") or {})
    # Project .mcp.json files (already discovered below; iterate eagerly)
    for path in find_mcp_json_files(CWD):
        data = load_settings(path)
        mcp_servers.update(data.get("mcpServers") or {})

    cli_candidates = []
    for sname, scfg in mcp_servers.items():
        if not isinstance(scfg, dict):
            continue
        matches = match_cli_alternatives(
            sname,
            scfg.get("command", ""),
            scfg.get("args") or [],
        )
        for m in matches:
            cli_candidates.append({
                "server": sname,
                "suggested_cli": m["cli"],
                "reason": m["reason"],
            })
    out["cli_alternative_candidates"] = cli_candidates

    # Permissions (concatenate allow/deny across all scopes)
    allow, deny = [], []
    for s in (user_settings, user_local, project_settings, project_local, managed):
        p = s.get("permissions") or {}
        allow.extend(p.get("allow") or [])
        deny.extend(p.get("deny") or [])
    out["permissions"] = {"allow": allow, "deny": deny}

    # Skills (user + project)
    out["skills"] = (
        inventory_markdown_dir(os.path.join(HOME, ".claude/skills"), "user")
        + inventory_markdown_dir(os.path.join(CWD, ".claude/skills"), "project")
    )

    # Agents (user + project)
    out["agents"] = (
        inventory_markdown_dir(os.path.join(HOME, ".claude/agents"), "user")
        + inventory_markdown_dir(os.path.join(CWD, ".claude/agents"), "project")
    )

    # Slash commands (user + project)
    out["commands"] = (
        inventory_markdown_dir(os.path.join(HOME, ".claude/commands"), "user")
        + inventory_markdown_dir(os.path.join(CWD, ".claude/commands"), "project")
    )

    # CLAUDE.md files + imports
    claude_md_paths = []
    for candidate in (
        os.path.join(HOME, ".claude/CLAUDE.md"),
        os.path.join(CWD, ".claude/CLAUDE.md"),
        os.path.join(CWD, "CLAUDE.md"),
    ):
        claude_md_paths.extend(follow_imports(candidate))
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for entry in claude_md_paths:
        if entry["path"] not in seen:
            seen.add(entry["path"])
            unique.append(entry)
    out["claude_md"] = {
        "files": unique,
        "total_lines": sum(e["lines"] for e in unique),
    }

    # Ghost slash references in CLAUDE.md
    known = {s["name"] for s in out["skills"]} | {c["name"] for c in out["commands"]}
    out["ghost_refs"] = ghost_refs_in_claude_md(unique, known)

    # .mcp.json files discovered walking up from cwd
    out["mcp_json_files"] = find_mcp_json_files(CWD)

    # Bloat directories present in cwd
    bloat_markers = {
        "package.json": ["node_modules", "dist", "build", ".next", "coverage"],
        "Cargo.toml": ["target"],
        "go.mod": ["vendor"],
        "pyproject.toml": ["__pycache__", ".venv"],
        "requirements.txt": ["__pycache__", ".venv"],
    }
    bloat = []
    for marker, dirs in bloat_markers.items():
        if os.path.isfile(os.path.join(CWD, marker)):
            for d in dirs:
                if os.path.isdir(os.path.join(CWD, d)):
                    bloat.append(d)
    out["bloat_dirs_present"] = sorted(set(bloat))

    # Size flags for quick filtering
    out["flags"] = {
        "claude_md_over_200_lines": out["claude_md"]["total_lines"] > 200,
        "claude_md_over_500_lines": out["claude_md"]["total_lines"] > 500,
        "skills_oversize": [s["name"] for s in out["skills"] if s["body_lines"] > 200],
        "skills_critical": [s["name"] for s in out["skills"] if s["body_lines"] > 500],
        "agents_oversize": [a["name"] for a in out["agents"] if a["body_lines"] > 200],
        "commands_oversize": [c["name"] for c in out["commands"] if c["body_lines"] > 200],
    }

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
