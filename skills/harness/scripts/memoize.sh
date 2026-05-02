#!/usr/bin/env bash
# Memoize — proactive memory hygiene for ~/.claude/projects/<slug>/memory/.
# Read-only by default in spirit: emits a markdown report; never edits or
# deletes a memory file. The report goes to <memory>/_memoize-report.md.
#
# Checks:
#   1. Index sync     — every memory/*.md (except _*.md) is in MEMORY.md;
#                       every MEMORY.md entry points at a real file.
#   2. Frontmatter    — every memory has `name`, `description`, `type`.
#   3. Stale citations — path-shaped tokens in memory bodies that resolve
#                        nowhere across the search roots.
#   4. Duplicates     — pairs of memories of the same `type` whose names
#                        or descriptions are lexically close.
#
# Output is sorted and stable: running twice produces an identical report
# (no timestamps in the body).
#
# Usage:
#   bash memoize.sh                 # write the report
#   bash memoize.sh --dry-run       # print the plan, write nothing
#   bash memoize.sh --target=PATH   # explicit memory dir
#
# Env knobs (mirror snapshot.sh):
#   CLAUDE_DIR=/path/to/.claude
#   USER_PROJECT_KEY=-Users-foo
#   MEMOIZE_SEARCH_ROOTS="$HOME/.claude/projects $HOME/Projects"

set -euo pipefail

DRY_RUN=0
TARGET=""
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --target=*) TARGET="${arg#--target=}" ;;
    -h|--help)
      sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
USER_PROJECT_KEY="${USER_PROJECT_KEY:-$(printf '%s' "$HOME" | tr '/' '-')}"
if [ -z "$TARGET" ]; then
  TARGET="$CLAUDE_DIR/projects/$USER_PROJECT_KEY/memory"
fi
SEARCH_ROOTS="${MEMOIZE_SEARCH_ROOTS:-$HOME/.claude/projects $HOME/Projects}"

if [ ! -d "$TARGET" ]; then
  echo "error: memory dir not found: $TARGET" >&2
  echo "       set --target=PATH or USER_PROJECT_KEY" >&2
  exit 2
fi

REPORT="$TARGET/_memoize-report.md"

green() { printf '\033[32m%s\033[0m' "$1"; }
yellow() { printf '\033[33m%s\033[0m' "$1"; }
dim() { printf '\033[90m%s\033[0m' "$1"; }
if ! [ -t 1 ]; then
  green() { printf '%s' "$1"; }
  yellow() { printf '%s' "$1"; }
  dim() { printf '%s' "$1"; }
fi

echo "memoize — target=$TARGET"
[ "$DRY_RUN" -eq 1 ] && echo "$(yellow '(dry-run)') no file will be written"
echo

# Resolve PYBIN once.
if command -v python3 >/dev/null 2>&1; then
  PYBIN=python3
elif command -v python >/dev/null 2>&1; then
  PYBIN=python
else
  echo "error: python3 not on PATH (needed for frontmatter parsing)" >&2
  exit 2
fi

# Hand off to python for the analysis. Keeps the bash thin and the parsing safe.
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

TARGET="$TARGET" SEARCH_ROOTS="$SEARCH_ROOTS" "$PYBIN" - <<'PY' > "$TMP"
import os, re, sys, hashlib
from pathlib import Path

target = Path(os.environ["TARGET"])
roots = [Path(p) for p in os.environ["SEARCH_ROOTS"].split() if p]

REPORT_NAME = "_memoize-report.md"
INDEX = "MEMORY.md"
REQUIRED = ("name", "description", "type")

def memory_files():
    out = []
    for p in sorted(target.iterdir()):
        if not p.is_file():
            continue
        if p.suffix != ".md":
            continue
        if p.name == INDEX or p.name.startswith("_"):
            continue
        out.append(p)
    return out

def parse_frontmatter(text):
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return None, text
    block = text[4:end]
    body = text[end+5:]
    fm = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        fm[k.strip()] = v.strip()
    return fm, body

def index_entries():
    p = target / INDEX
    if not p.exists():
        return [], None
    entries = []
    pat = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    raw = p.read_text(encoding="utf-8")
    for line in raw.splitlines():
        m = pat.search(line)
        if m:
            entries.append((m.group(1), m.group(2)))
    return entries, raw

def shorten(s, n=80):
    s = s.strip().replace("\n", " ")
    return s if len(s) <= n else s[:n-1] + "…"

# ---- 1. Index sync ----
files = memory_files()
file_names = {p.name for p in files}
entries, _ = index_entries()
indexed = {name for _, name in entries}

missing_in_index = sorted(file_names - indexed)
broken_in_index = sorted({name for _, name in entries if name not in file_names})

# ---- 2. Frontmatter ----
fm_issues = []  # (filename, problem)
parsed = {}     # filename -> (fm, body)
for p in files:
    text = p.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    parsed[p.name] = (fm, body)
    if fm is None:
        fm_issues.append((p.name, "no frontmatter block"))
        continue
    for k in REQUIRED:
        if not fm.get(k):
            fm_issues.append((p.name, f"missing or empty `{k}`"))
fm_issues.sort()

# ---- 3. Stale citations ----
# Conservative — flag a token only if it's *unambiguously* a real filesystem
# path. Two ways to qualify:
#   (a) starts with a hard prefix that's almost always a path: ~/, /Users/,
#       /home/, /etc/, /opt/, /var/, /tmp/, ./, ../
#   (b) ends in a recognised source-file extension.
# This drops slash-commands (/verify, /grade), brace expansions
# ({a,b,c}), regex-ish strings, and similar false positives.
PATH_PREFIXES = ("~/", "/Users/", "/home/", "/etc/", "/opt/", "/var/", "/tmp/",
                 "./", "../")
PATH_EXTS = (".md", ".sh", ".py", ".ts", ".tsx", ".js", ".jsx", ".json",
             ".yml", ".yaml", ".toml", ".php", ".go", ".rb", ".rs",
             ".html", ".css", ".sql", ".lock", ".env")
path_pat = re.compile(r"`(?P<bt>[^`\n]+)`|(?P<bare>(?:~|\.{1,2})?/[^\s`)\]\"',]+)")
known_existing_cache = {}

def looks_like_path(tok):
    if not tok or "/" not in tok:
        return False
    if tok.startswith(("http://", "https://", "//")):
        return False
    if tok.startswith("<") or tok.endswith(">"):
        return False
    if "{" in tok or "}" in tok or "*" in tok:
        return False
    if tok.startswith(PATH_PREFIXES):
        return True
    if any(tok.endswith(ext) for ext in PATH_EXTS):
        return True
    return False

def candidate_paths(text):
    out = []
    for m in path_pat.finditer(text):
        tok = (m.group("bt") or m.group("bare") or "").strip()
        tok = tok.rstrip(".,;:)")
        if looks_like_path(tok):
            out.append(tok)
    return out

def resolves(tok):
    if tok in known_existing_cache:
        return known_existing_cache[tok]
    # Expand ~/
    if tok.startswith("~/"):
        candidates = [Path(os.path.expanduser(tok))]
    elif tok.startswith("/"):
        candidates = [Path(tok)]
    elif tok.startswith("./"):
        candidates = [Path(tok)]
    else:
        # Treat as a relative project-ish path: try under each search root.
        candidates = [r / tok for r in roots]
        # also try as a basename match under any root (one level only)
        # (skipped — too broad; conservatism wins)
    found = any(c.exists() for c in candidates)
    if not found:
        # last-ditch: a basename-only suffix match under search roots, depth 4
        base = tok.rstrip("/").split("/")[-1]
        if base and len(base) > 2:
            for r in roots:
                if not r.exists():
                    continue
                # single-shot find: walk up to depth 4
                hit = False
                for dirpath, dirnames, filenames in os.walk(r):
                    depth = len(Path(dirpath).relative_to(r).parts)
                    if depth > 4:
                        dirnames[:] = []
                        continue
                    if base in filenames or base in dirnames:
                        hit = True
                        break
                if hit:
                    found = True
                    break
    known_existing_cache[tok] = found
    return found

stale = []  # (filename, token)
for p in files:
    fm, body = parsed[p.name]
    seen = set()
    for tok in candidate_paths(body or ""):
        if tok in seen:
            continue
        seen.add(tok)
        if not resolves(tok):
            stale.append((p.name, tok))
stale.sort()

# ---- 4. Duplicate detection (lexical, by type) ----
def normalize(s):
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return set(t for t in s.split() if len(t) > 2)

def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)

by_type = {}
for p in files:
    fm, _ = parsed[p.name]
    t = (fm or {}).get("type", "<unknown>")
    by_type.setdefault(t, []).append((p.name, fm or {}))

dupes = []  # (type, file_a, file_b, score)
for t, items in by_type.items():
    items.sort()
    for i in range(len(items)):
        for j in range(i+1, len(items)):
            a_name, a_fm = items[i]
            b_name, b_fm = items[j]
            score = max(
                jaccard(normalize(a_fm.get("name")), normalize(b_fm.get("name"))),
                jaccard(normalize(a_fm.get("description")), normalize(b_fm.get("description"))),
            )
            if score >= 0.5:
                dupes.append((t, a_name, b_name, round(score, 2)))
dupes.sort()

# ---- Render ----
out = []
def section(title):
    out.append(f"## {title}\n")

out.append("# Memory consolidation report\n")
out.append("Generated by `harness memoize`. Report-only — no memory files were modified.\n")
out.append(f"Memory dir: `{target}`\n")
out.append(f"Files scanned: {len(files)}\n")
out.append("")

section("Index sync")
if not missing_in_index and not broken_in_index:
    out.append("OK — every memory file is indexed and every index entry resolves.\n")
else:
    if missing_in_index:
        out.append("**Files not listed in MEMORY.md:**\n")
        for n in missing_in_index:
            out.append(f"- `{n}`")
        out.append("")
    if broken_in_index:
        out.append("**MEMORY.md entries pointing at missing files:**\n")
        for n in broken_in_index:
            out.append(f"- `{n}`")
        out.append("")
out.append("")

section("Frontmatter hygiene")
if not fm_issues:
    out.append("OK — every memory has `name`, `description`, and `type`.\n")
else:
    for name, problem in fm_issues:
        out.append(f"- `{name}` — {problem}")
    out.append("")
out.append("")

section("Stale citations")
if not stale:
    out.append("OK — no path-shaped tokens that fail to resolve under the search roots.\n")
else:
    out.append(f"Search roots: `{os.environ['SEARCH_ROOTS']}`\n")
    out.append("Conservative — only flags tokens with an explicit `~/`, `/`, or `./` prefix or backtick-wrapped path. False positives possible; verify before acting.\n")
    cur = None
    for name, tok in stale:
        if name != cur:
            out.append(f"- `{name}`")
            cur = name
        out.append(f"  - `{tok}`")
    out.append("")
out.append("")

section("Possible duplicates")
if not dupes:
    out.append("OK — no near-duplicate name/description pairs within a `type`.\n")
else:
    out.append("Lexical Jaccard ≥ 0.5 on `name` or `description`. Review and decide whether to merge.\n")
    for t, a, b, score in dupes:
        out.append(f"- _{t}_ — `{a}` ↔ `{b}` (score {score})")
    out.append("")
out.append("")

# Final summary line
total_findings = len(missing_in_index) + len(broken_in_index) + len(fm_issues) + len(stale) + len(dupes)
out.append("---")
out.append(f"Findings: {total_findings} "
           f"(index {len(missing_in_index)+len(broken_in_index)}, "
           f"frontmatter {len(fm_issues)}, "
           f"stale {len(stale)}, "
           f"duplicates {len(dupes)})")

text = "\n".join(out).rstrip() + "\n"
sys.stdout.write(text)

# Also emit a one-line summary to stderr for the bash wrapper.
sys.stderr.write(f"SUMMARY findings={total_findings}\n")
PY

# Read the python summary off stderr — but we already piped to TMP only, so
# re-run is wasteful. Cheaper: tail the report's last line for the summary.
SUMMARY="$(tail -n 1 "$TMP")"

if [ "$DRY_RUN" -eq 1 ]; then
  dim 'plan:'; echo
  echo "  would write: $REPORT"
  echo
  dim '── report preview ──'; echo
  cat "$TMP"
  dim '── end ──'; echo
  exit 0
fi

# Atomic write so the report is byte-stable on equal runs.
mkdir -p "$TARGET"
mv "$TMP" "$REPORT"
trap - EXIT

echo "$(green 'wrote:') $REPORT"
echo "  $SUMMARY"
