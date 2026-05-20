# compile-task

Compile one-off LLM tasks into reusable, self-contained executables so you stop paying tokens to redo deterministic work.

## What it does

When you describe a task ("rename these photos by their EXIF date", "pull this GitHub issue's comments as markdown"), the skill:

1. Checks a catalogue of previously-compiled scripts and offers to re-run an existing one if it matches.
2. Otherwise picks the simplest language for the job — **bash** for POSIX shell ops, **PowerShell** for Windows-native or shell-y tasks on Windows, **single-file uv Python** (PEP 723 inline deps) as the cross-platform default for anything needing libraries.
3. Writes the script, smoke-tests it, registers it in the catalogue, and runs it.

From then on, the script is one command:

```sh
cscript run rename-by-exif-date ./photos
```

## The `cscript` dispatcher

A single Python script installed on first use into a user-writable directory on `PATH` (on Windows, paired with a small `cscript.cmd` wrapper). It stores everything in an OS-correct appdata directory: `~/Library/Application Support/cscript/` on macOS, `~/.local/share/cscript/` on Linux, `%LOCALAPPDATA%\cscript\` on Windows. Bash scripts on Windows require Git Bash or WSL.

```
cscript list                       # show all registered scripts
cscript which "<description>"      # fuzzy-match catalogue
cscript run [--yes] <name> [args]  # execute (prompts on TTY unless --yes)
cscript show <name>                # print source + metadata
cscript edit <name>                # open in $EDITOR
cscript rm <name>                  # archive and unregister
cscript state-dir <name>           # print per-script state dir
cscript where                      # print the data directory
```

## Design choices

- **Self-contained scripts.** No project-local imports, no relative paths. A script written for one repo can run from anywhere.
- **One catalogue, one PATH entry.** Instead of dumping 30 scripts into `~/.local/bin`, you get one `cscript` binary and tab-completable subcommands.
- **Confirm before running.** The skill always shows the matched script and asks before executing, including for previously-registered scripts. Wrong matches don't clobber files.
- **Archive, never delete.** `cscript rm` and re-registration both move the prior version into `scripts/.archive/<name>.<timestamp>` rather than deleting.
- **Eat your own dog food.** The dispatcher itself is a `uv` single-file script with PEP 723 inline deps — exactly the pattern it produces.

## When the skill stays out

It won't compile one-off explorations, judgement-laden tasks (refactoring, PR descriptions), one-line shell commands, or anything tightly coupled to the current repo. For those, the LLM answers directly.

## Usage

```
/compile-task rename JPGs in this directory by the EXIF date they were shot
/compile-task pull all comments from GitHub PR https://github.com/foo/bar/pull/42 as markdown
/compile-task strip EXIF from every image under a folder
```

Or just describe a task and let the skill decide whether to compile it.
