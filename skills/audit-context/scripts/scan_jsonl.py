#!/usr/bin/env python3
"""
Aggregate behavioral signals from Claude Code session JSONL transcripts.

Usage:  scan_jsonl.py [days=30]

Streams ~/.claude/projects/<slug>/*.jsonl for the current working directory's
slug. Never loads whole files into memory; emits JSON aggregates only.
"""
import sys, os, json, glob, time


def percentile(sorted_vals, p):
    if not sorted_vals:
        return 0
    k = (len(sorted_vals) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(sorted_vals) - 1)
    return int(sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo))


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    cwd = os.getcwd()
    slug = cwd.replace("/", "-")
    root = os.path.join(os.path.expanduser("~/.claude/projects"), slug)

    if not os.path.isdir(root):
        print(json.dumps({"error": "no session history", "root": root}))
        return

    cutoff = time.time() - days * 86400
    files = [f for f in glob.glob(os.path.join(root, "*.jsonl"))
             if os.path.getmtime(f) >= cutoff]

    tool_counts, skill_counts = {}, {}
    tool_errors = {}
    agent_types = {}
    bash_commands = []
    read_paths = {}
    turns = cache_read = cache_create = input_tok = output_tok = 0
    per_turn_input = []
    large_results = []
    autocompact = 0
    sessions_hit_limit, sessions = set(), set()
    user_turns_text = []

    # Track recent tool_use name by id so we can map errors back to the tool.
    id_to_tool = {}

    for fp in files:
        try:
            with open(fp) as f:
                for line in f:
                    try:
                        d = json.loads(line)
                    except Exception:
                        continue
                    sid = d.get("sessionId")
                    if sid:
                        sessions.add(sid)
                    t = d.get("type")
                    m = d.get("message") or {}
                    if not isinstance(m, dict):
                        continue
                    u = m.get("usage") or {}
                    if u:
                        turns += 1
                        cr = u.get("cache_read_input_tokens", 0) or 0
                        cc = u.get("cache_creation_input_tokens", 0) or 0
                        it = u.get("input_tokens", 0) or 0
                        cache_read += cr
                        cache_create += cc
                        input_tok += it
                        output_tok += u.get("output_tokens", 0) or 0
                        per_turn_input.append(cr + cc + it)
                    content = m.get("content")
                    if isinstance(content, list):
                        for c in content:
                            if not isinstance(c, dict):
                                continue
                            ctype = c.get("type")
                            if ctype == "tool_use":
                                name = c.get("name", "")
                                tool_counts[name] = tool_counts.get(name, 0) + 1
                                tid = c.get("id")
                                if tid:
                                    id_to_tool[tid] = name
                                inp = c.get("input") or {}
                                if name == "Skill":
                                    skill = inp.get("skill")
                                    if skill:
                                        skill_counts[skill] = skill_counts.get(skill, 0) + 1
                                elif name == "Agent":
                                    st = inp.get("subagent_type") or "general-purpose"
                                    agent_types[st] = agent_types.get(st, 0) + 1
                                elif name == "Read":
                                    p = inp.get("file_path")
                                    if isinstance(p, str):
                                        read_paths[p] = read_paths.get(p, 0) + 1
                                elif name == "Bash":
                                    cmd = inp.get("command")
                                    if isinstance(cmd, str) and len(bash_commands) < 2000:
                                        bash_commands.append(cmd[:300])
                            elif ctype == "tool_result":
                                tid = c.get("tool_use_id")
                                tname = id_to_tool.get(tid, "unknown")
                                rc = c.get("content")
                                size = 0
                                if isinstance(rc, str):
                                    size = len(rc)
                                elif isinstance(rc, list):
                                    for item in rc:
                                        if isinstance(item, dict):
                                            txt = item.get("text") or ""
                                            size += len(txt) if isinstance(txt, str) else 0
                                if c.get("is_error"):
                                    tool_errors[tname] = tool_errors.get(tname, 0) + 1
                                if size > 30000:
                                    large_results.append((tname, size))
                    if t == "user" and isinstance(content, str):
                        if len(user_turns_text) < 2000:
                            user_turns_text.append(content[:200].lower())
                    if t == "system":
                        s = json.dumps(d).lower()
                        if "autocompact" in s or "auto-compact" in s or "compacted" in s:
                            autocompact += 1
                            if sid:
                                sessions_hit_limit.add(sid)
        except Exception:
            pass

    total_input = cache_read + cache_create + input_tok
    cache_hit = (cache_read / total_input) if total_input else 0.0
    corrections = sum(1 for t in user_turns_text
                      if t.lstrip().startswith(("no ", "no,", "don't", "stop ",
                                                "wrong", "that's wrong", "not ")))
    avg_turn = (cache_read + cache_create + input_tok) / turns if turns else 0

    per_turn_input.sort()
    large_results.sort(key=lambda x: -x[1])

    # Tool error rate: failures / total calls.
    tool_error_rates = {}
    for tool, count in tool_counts.items():
        errs = tool_errors.get(tool, 0)
        if count and errs:
            tool_error_rates[tool] = {
                "calls": count,
                "errors": errs,
                "rate": round(errs / count, 3),
            }

    print(json.dumps({
        "window_days": days,
        "files_scanned": len(files),
        "sessions": len(sessions),
        "assistant_turns": turns,
        "cache_hit_rate": round(cache_hit, 3),
        "avg_input_per_turn": int(avg_turn),
        "p50_input_per_turn": percentile(per_turn_input, 50),
        "p95_input_per_turn": percentile(per_turn_input, 95),
        "p99_input_per_turn": percentile(per_turn_input, 99),
        "tokens": {"cache_read": cache_read, "cache_create": cache_create,
                   "input": input_tok, "output": output_tok},
        "autocompact_events": autocompact,
        "sessions_hit_autocompact": len(sessions_hit_limit),
        "tool_top": sorted(tool_counts.items(), key=lambda x: -x[1])[:30],
        "tool_total_distinct": len(tool_counts),
        "tool_error_rates": dict(sorted(tool_error_rates.items(),
                                        key=lambda x: -x[1]["rate"])),
        "skill_top": sorted(skill_counts.items(), key=lambda x: -x[1])[:30],
        "agent_subagent_types": dict(sorted(agent_types.items(),
                                            key=lambda x: -x[1])),
        "bash_commands_sample": bash_commands[:500],
        "read_paths_top": sorted(read_paths.items(), key=lambda x: -x[1])[:20],
        "large_tool_results_top": [{"tool": t, "bytes": b} for t, b in large_results[:10]],
        "correction_user_turns": corrections,
        "user_turns_sampled": len(user_turns_text),
    }, indent=2))


if __name__ == "__main__":
    main()
