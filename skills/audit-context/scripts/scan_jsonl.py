#!/usr/bin/env python3
"""
Aggregate behavioral signals from Claude Code session JSONL transcripts.

Usage:  scan_jsonl.py [days=30]

Streams ~/.claude/projects/<slug>/*.jsonl for the current working directory's
slug. Never loads whole files into memory; emits JSON aggregates only.
"""
import sys, os, json, glob, time


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
    turns = cache_read = cache_create = input_tok = output_tok = 0
    autocompact = 0
    sessions_hit_limit, sessions = set(), set()
    user_turns_text = []

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
                        cache_read += u.get("cache_read_input_tokens", 0) or 0
                        cache_create += u.get("cache_creation_input_tokens", 0) or 0
                        input_tok += u.get("input_tokens", 0) or 0
                        output_tok += u.get("output_tokens", 0) or 0
                    content = m.get("content")
                    if isinstance(content, list):
                        for c in content:
                            if not isinstance(c, dict):
                                continue
                            if c.get("type") == "tool_use":
                                name = c.get("name", "")
                                tool_counts[name] = tool_counts.get(name, 0) + 1
                                if name == "Skill":
                                    skill = (c.get("input") or {}).get("skill")
                                    if skill:
                                        skill_counts[skill] = skill_counts.get(skill, 0) + 1
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

    print(json.dumps({
        "window_days": days,
        "files_scanned": len(files),
        "sessions": len(sessions),
        "assistant_turns": turns,
        "cache_hit_rate": round(cache_hit, 3),
        "avg_input_per_turn": int(avg_turn),
        "tokens": {"cache_read": cache_read, "cache_create": cache_create,
                   "input": input_tok, "output": output_tok},
        "autocompact_events": autocompact,
        "sessions_hit_autocompact": len(sessions_hit_limit),
        "tool_top": sorted(tool_counts.items(), key=lambda x: -x[1])[:30],
        "tool_total_distinct": len(tool_counts),
        "skill_top": sorted(skill_counts.items(), key=lambda x: -x[1])[:30],
        "correction_user_turns": corrections,
        "user_turns_sampled": len(user_turns_text),
    }, indent=2))


if __name__ == "__main__":
    main()
