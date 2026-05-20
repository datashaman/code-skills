---
name: cscript
description: |
  Compile a one-off task description into a reusable, self-contained
  executable script so the LLM doesn't have to do the same work again.
  Picks bash for trivial file/shell ops, single-file uv Python (PEP 723)
  for anything needing libraries, or PowerShell for Windows-native work.
  Registers scripts in an OS-correct appdata directory and exposes them
  through a `cscript` dispatcher installed on PATH. Future invocations
  match the description against the index and re-run the existing script
  instead of regenerating. Use when the user says "compile this", "make
  a script for X", "stash this as a script", "save this so I don't have
  to ask again", or describes a task that sounds like it will recur.
user-invocable: true
---

# cscript — turn prompts into reusable executables

The point of this skill is to **stop paying an LLM to redo deterministic work**. Each time the user describes a task that could be a script, compile it once, register it in the catalogue, and run the registered script from then on. Generation is the exception; execution is the rule.

## Hard rules

1. **Check the catalogue first.** Before designing anything, run `cscript which "<short description>"` and `cscript list`. If a registered script matches the intent, propose running it. Never silently regenerate something that already exists.
2. **Confirm before running.** Show the matched script's name, description, and the exact command you're about to run. Wait for user confirmation. Apply this to both freshly generated and previously registered scripts. Auto-run is never on.
3. **Self-contained.** Generated scripts must run on their own — no project-local imports, no relative paths, no assumed cwd. Bash uses only POSIX tools (or tools you've checked are installed). Python uses PEP 723 inline deps so `uv run` handles everything.
4. **One file.** No sibling helpers, no companion config files. If a script needs persistent state, ask the dispatcher for its slot: `cscript state-dir <name>` prints (and creates on first call) a per-script directory inside the appdata dir.
5. **`--help` is mandatory.** Every script supports `-h`/`--help` and exits non-zero on missing required args with a usage message.
6. **Idempotent registration.** Re-registering the same `--name` archives the old version into `scripts/.archive/<name>.<timestamp>` and replaces it. Never silently overwrite.
7. **Don't generate destructive scripts without `--dry-run`.** If a script deletes, force-pushes, drops a table, sends an email, or modifies shared state, it must support `--dry-run` and default-print-what-it-would-do for unfamiliar inputs. Pass `--read-only` to `cscript register` only for scripts that truly cannot modify state (the dispatcher tags those with `[ro]` in `list`); leave it off for everything else.

## Workflow

### 1. Bootstrap (first run only)

In order, before anything else:

1. **Check `uv` is installed.** Run `command -v uv >/dev/null 2>&1`. If missing, stop and tell the user to install it (`curl -LsSf https://astral.sh/uv/install.sh | sh` on macOS/Linux, or via Homebrew). The dispatcher's shebang is `#!/usr/bin/env -S uv run --script`, so nothing else will work without it.

2. **Check whether the dispatcher is installed and on PATH.** Run `command -v cscript >/dev/null 2>&1`.

   If installed, also check it is not stale: compare `cscript version` against the source's version. The source's version is the `VERSION = "..."` line near the top of `scripts/cscript`. If they differ (or the installed binary predates `version` and errors), treat it as missing and re-install it the same way as a fresh install — copying over the existing file. Tell the user you are upgrading their dispatcher.

3. **If `cscript` is missing (or stale), install it.** The source lives at `scripts/cscript` relative to this `SKILL.md`. Resolve the path from wherever this file was loaded; if you cannot find it, ask the user for the skill directory rather than guessing.

   Pick a destination directory that is **user-writable and already on `PATH`**:

   - Inspect existing `PATH` entries under the user's home directory and prefer one they already maintain.
   - If none is on `PATH`, ask the user where to put the binary rather than picking one for them.

   Then install per OS:

   - **macOS / Linux:** copy `scripts/cscript` to `<chosen-dir>/cscript` and make it executable.
   - **Windows:** copy **both** `scripts/cscript` and `scripts/cscript.cmd` into the chosen directory. Windows resolves `cscript.cmd` via `PATHEXT`; the wrapper hands the extensionless source to `uv run --script`. Note: Windows ships `cscript.exe` (Windows Script Host) in `System32`; for our `cscript.cmd` to win, the chosen directory must appear in `PATH` before `C:\Windows\System32`. Verify by running this in PowerShell (substitute the chosen directory):

     ```powershell
     $paths = $env:Path -split ';'
     $user = $paths.IndexOf('<chosen-dir>')
     $sys  = $paths.IndexOf("$env:SystemRoot\System32")
     if ($user -lt 0)                  { 'chosen dir not on PATH' }
     elseif ($sys -ge 0 -and $user -gt $sys) { 'PATH ordering would let cscript.exe shadow cscript.cmd' }
     else                              { 'OK' }
     ```

     If the check reports anything other than `OK`, tell the user how to fix it (add/reorder the entry in User PATH) and stop until they confirm.

4. **Verify the install worked.** After copying, run `cscript --help` in a fresh shell invocation. If it does not resolve, the chosen directory is not on `PATH` in interactive shells — tell the user how to add it for their shell and stop. Do not proceed until they confirm `cscript --help` works.

The dispatcher itself is a uv single-file script — it bootstraps its own Python deps the first time it runs.

### 2. Match against the catalogue

```sh
cscript which "<user's request, condensed to keywords>"
cscript list
```

`cscript which` prints up to five ranked candidates. Treat the top result as a **clear match** only if both hold:

- the top hit's first column (the name) reads as a plausible verb-object for the request, *and*
- the next candidate (if any) is obviously about a different task — not just a near-duplicate score.

If clear match: confirm the script + args with the user, then `cscript run <name> [args...]`. Done.

If ambiguous (multiple plausible candidates) or no hits: show what you found and either ask which to use or proceed to step 3.

### 3. Design (only if no match)

Pick the language using this decision rule, in order:

1. **PowerShell** — if the task is Windows-native (registry, services, COM, Windows-specific filesystem APIs) **or** if the user is on Windows without Git Bash/WSL and the task is shell-y enough that bash would be the POSIX choice. `pwsh` (PowerShell Core) runs on macOS and Linux too, so this is also fine for cross-platform shell tasks if the user already uses PowerShell.
2. **Bash** — if the task is purely file system, git, text munging with standard Unix tools (`jq`, `awk`, `sed`, `grep`, `find`, `rsync`), or a thin wrapper around an existing CLI the user has. No HTTP, no parsing structured formats beyond what `jq`/`yq` handle. On Windows, bash scripts need Git Bash or WSL.
3. **uv Python** — anything else. HTTP, HTML/XML parsing, image processing, anything pulling a library, anything where bash quoting would make you cry. The cross-platform default when in doubt.

Pick a name: short verb-object, kebab-case, no language suffix. `resize-pngs`, not `resize_pngs.sh`. `rename-by-exif-date`, not `photo_renamer.py`. The dispatcher hides the extension.

Read the matching template from `references/` before writing:

- `references/bash-template.sh`
- `references/uv-python-template.py`
- `references/powershell-template.ps1`

All three templates have the structural skeleton (shebang, header comment with NAME/DESC/USAGE, `--help`/`-Help`, arg parsing, error handling). Fill in the implementation only.

### 4. Write and smoke-test

- Write the script to a temp path.
- Smoke test: run it with `--help` (must exit 0 and print usage) and with no args (must exit non-zero with usage to stderr).
- If the task is read-only and the user supplied inputs, run it once on those inputs in the temp location and show the output.
- If the task is destructive, do a `--dry-run` first.

### 5. Register

```sh
cscript register \
  --source <temp-path> \
  --name <name> \
  --description "<one-line, present tense, no trailing period>" \
  --language <bash|python|powershell> \
  --args-help "<one-line usage>" \
  [--read-only]
```

The dispatcher derives the filename automatically (`<name>.sh` for bash, `<name>.py` for python, `<name>.ps1` for powershell), moves the file from `--source` into the appdata `scripts/` directory, makes it executable on POSIX, archives any prior version, and prints the final path.

### 6. Run

Always run the freshly registered script through the dispatcher, never by direct path. Pass `--yes` since you have already confirmed the run with the user:

```sh
cscript run --yes <name> [args...]
```

Direct (human) invocations omit `--yes`; the dispatcher will then prompt before running non-read-only scripts on a TTY. This proves the dispatcher works and gives the user the muscle-memory invocation they'll use next time.

### 7. Report

Tell the user, in one or two sentences:

- The script's name and what it does.
- How to invoke it next time: `cscript run <name> ...` (and `cscript list` to see everything).
- Whether it's marked read-only.

Do not paste the full source. They can `cscript show <name>` if they want it.

## Dispatcher reference

The dispatcher is installed wherever the user keeps personal binaries on `PATH` (see bootstrap). It stores everything under the OS appdata directory (resolved via `platformdirs.user_data_dir("cscript")`, or `$CSCRIPT_DATA_DIR` if set):

- macOS: `~/Library/Application Support/cscript/`
- Linux: `~/.local/share/cscript/`
- Windows: `%LOCALAPPDATA%\cscript\`

Subcommands:

| Command | What it does |
| --- | --- |
| `cscript list` | List all registered scripts with descriptions. |
| `cscript which <query>` | Fuzzy match across names and descriptions. Used by this skill before generating. |
| `cscript run [--yes] <name> [args...]` | Execute the registered script. Prompts before non-read-only runs on a TTY unless `--yes`. Args after the name are passed through. |
| `cscript show <name>` | Print the script's source plus its index metadata. |
| `cscript edit <name>` | Open the script in `$EDITOR`. |
| `cscript rm <name>` | Archive the file to `scripts/.archive/` and drop its index entry and state directory. |
| `cscript state-dir <name>` | Print (creating if missing) the per-script state directory under the appdata dir. |
| `cscript where` | Print the data directory path. |
| `cscript version` | Print the dispatcher version. |
| `cscript mine` | Rank repeated catalogue misses from the `which` log to surface things worth compiling. |
| `cscript register …` | Used by this skill at compile time; not normally hand-invoked. |

## Surfacing candidates from history

`cscript which` appends every query to a local invocation log (`which.log` under the data dir). `cscript mine` reads it back and ranks queries that have been asked 2+ times but never matched anything in the catalogue — direct "I tried to reuse but couldn't" signal.

Run it on-demand:

```sh
cscript mine            # repeated misses, default threshold 2
cscript mine --min 1    # every miss
```

When you (the agent) see repeated patterns in your conversation that the user hasn't asked to compile yet, suggest `cscript mine` so they can review what's worth stashing.

## Regeneration

When the user asks to "redo", "rewrite", or "regenerate" an existing script (or when running it reveals a bug):

1. `cscript show <name>` to see the current source.
2. Decide whether the rewrite is small enough to edit in place (`cscript edit`) or large enough to regenerate.
3. For full regeneration, write the new version, then `cscript register --name <same-name> …`. The dispatcher archives the previous version.

Do not invent new names like `resize-pngs-v2`. Keep one name per task; let the archive hold history.

## When NOT to compile a task

- **One-off explorations.** "Show me the top 10 largest files in this dir." Just answer it. If the user runs it twice, then compile.
- **Tasks that need judgement.** "Refactor this function." "Write a PR description." LLM judgement is the value; a script would be wrong.
- **Anything that's a one-line shell command.** `du -sh * | sort -h | tail` doesn't need a script.
- **Tasks tightly coupled to the current repo or cwd.** If the script wouldn't make sense in a different project, it belongs as a project script (committed in the repo), not in the global catalogue.

If you're unsure whether a task is worth compiling, ask the user: "Want me to stash this as a `cscript` so it's one command next time?" — then proceed or not based on their answer.
