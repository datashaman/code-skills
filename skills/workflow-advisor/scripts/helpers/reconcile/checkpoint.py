"""
helpers/reconcile/checkpoint.py

Git-based checkpointing for the reconcile loop. Wraps a reconcile pass
in a session that:

1. Verifies the working tree under .workflow/ is clean before starting
   (or surfaces dirty state to the caller for resolution).
2. Tracks writes during the pass.
3. On successful completion, commits .workflow/ as a single atomic
   commit with a structured message.
4. On failure, leaves the working tree dirty (or rolls back if the
   caller chose); never produces a partial commit.

This is what makes reverts clean: each reconcile pass is one commit
touching only .workflow/. `git revert <commit>` unwinds folder state.

The checkpoint is also where the "decisions log gitignored vs committed"
policy is enforced — files matching the gitignore are not staged.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
import logging
import os
from pathlib import Path
import subprocess
from typing import Any, Iterator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass
class Session:
    """
    A reconcile pass session. Held by `checkpoint.session()` context
    manager. Phases write through the session so we can build a
    structured commit message at the end.
    """

    config: dict
    event: Any | None
    workflow_dir: Path
    repo_root: Path

    # Populated by phases as they run.
    artifacts_changed: list[str] = field(default_factory=list)
    lifecycle_changed: list[str] = field(default_factory=list)
    cascade_summary: list[str] = field(default_factory=list)
    classification: dict | None = None
    summary_line: str | None = None

    # Set on commit.
    commit_sha: str | None = None
    no_op: bool = False

    def record_artifact_change(self, artifact_id: str, summary: str) -> None:
        self.artifacts_changed.append(f"{artifact_id}: {summary}")

    def record_lifecycle_change(self, item_id: str, summary: str) -> None:
        self.lifecycle_changed.append(f"{item_id}: {summary}")

    def record_cascade_effect(self, target: str, action: str, reason: str = "") -> None:
        line = f"{target}: {action}"
        if reason:
            line += f" ({reason})"
        self.cascade_summary.append(line)

    def set_classification(self, classification: dict) -> None:
        self.classification = classification

    def set_summary(self, summary_line: str) -> None:
        self.summary_line = summary_line


class DirtyTreeError(Exception):
    """
    Raised when the working tree under .workflow/ is dirty at session
    start. The caller decides how to proceed (interactive: prompt;
    CI: abort with clear error).
    """

    def __init__(self, dirty_files: list[str]):
        self.dirty_files = dirty_files
        super().__init__(
            f".workflow/ has uncommitted changes in: {', '.join(dirty_files)}. "
            "Resolve before running reconcile."
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def session(
    config: dict,
    event: Any | None = None,
    workflow_dir: Path | None = None,
    repo_root: Path | None = None,
    allow_dirty: bool = False,
) -> Iterator[Session]:
    """
    Open a reconcile session. On clean exit, if any .workflow/ files
    changed, produce a single commit with a structured message.

    Usage:
        with checkpoint.session(config, event) as sess:
            apply_phase.run(..., session=sess)
            cascade_phase.run(..., session=sess)
            log_phase.run(..., session=sess)

    On exception, the working tree is left as-is. Callers should decide
    whether to roll back (`git checkout -- .workflow/`) or leave for
    inspection.
    """
    repo_root = repo_root or _find_repo_root(Path.cwd())
    workflow_dir = workflow_dir or (repo_root / ".workflow")

    if not workflow_dir.exists():
        raise FileNotFoundError(f".workflow/ not found at {workflow_dir}")

    # Pre-flight: dirty-tree check.
    dirty = _list_dirty_files(repo_root, workflow_dir)
    if dirty and not allow_dirty:
        raise DirtyTreeError(dirty)

    sess = Session(
        config=config,
        event=event,
        workflow_dir=workflow_dir,
        repo_root=repo_root,
    )

    try:
        yield sess
    except Exception:
        logger.exception("reconcile pass raised; leaving working tree dirty for inspection")
        raise

    # Successful exit — commit if anything changed.
    if not _has_changes(repo_root, workflow_dir):
        sess.no_op = True
        return

    commit_message = _build_commit_message(sess)
    sha = _commit_workflow_changes(repo_root, workflow_dir, commit_message)
    sess.commit_sha = sha
    logger.info("reconcile pass committed as %s", sha[:8])


def commit_message_for(session: Session) -> str:
    """Public helper for callers that want to preview the commit message."""
    return _build_commit_message(session)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _find_repo_root(start: Path) -> Path:
    """Walk up to find the git repo root."""
    for parent in [start, *start.parents]:
        if (parent / ".git").exists():
            return parent
    raise FileNotFoundError(f"No git repo found at or above {start}")


def _git(repo_root: Path, *args: str) -> str:
    """Run a git command in the repo root, return stdout (stripped)."""
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _list_dirty_files(repo_root: Path, workflow_dir: Path) -> list[str]:
    """List staged/unstaged changes inside .workflow/."""
    rel = workflow_dir.relative_to(repo_root)
    output = _git(repo_root, "status", "--porcelain", "--", str(rel))
    if not output:
        return []
    files = []
    for line in output.splitlines():
        # porcelain format: 2-char status + space + path
        _, _, path = line.partition(" ")
        files.append(path.strip())
    return files


def _has_changes(repo_root: Path, workflow_dir: Path) -> bool:
    """Return True if .workflow/ has changes vs HEAD."""
    return bool(_list_dirty_files(repo_root, workflow_dir))


def _commit_workflow_changes(repo_root: Path, workflow_dir: Path, message: str) -> str:
    """
    Stage .workflow/ (only) and commit with the given message.
    Honors the existing .workflow/.gitignore.
    """
    rel = workflow_dir.relative_to(repo_root)
    # Stage only .workflow/. Never use `git add -A`.
    _git(repo_root, "add", str(rel))

    # Configure committer identity. In CI, the workflow file sets these
    # before invoking the CLI; this is the local-mode fallback.
    if not _committer_configured(repo_root):
        _git(repo_root, "config", "user.name", "workflow-advisor[bot]")
        _git(repo_root, "config", "user.email", "workflow-advisor@users.noreply.github.com")

    _git(repo_root, "commit", "-m", message)
    sha = _git(repo_root, "rev-parse", "HEAD")
    return sha


def _committer_configured(repo_root: Path) -> bool:
    """Check if user.name and user.email are set in this repo."""
    try:
        _git(repo_root, "config", "user.name")
        _git(repo_root, "config", "user.email")
        return True
    except subprocess.CalledProcessError:
        return False


def _build_commit_message(sess: Session) -> str:
    """
    Construct the structured commit message for this reconcile pass.

    Format:
        workflow: <summary line>

        trigger: <event name + actor>
        classification: <if any>
        artifacts: <changed artifact ids and what changed>
        cascade: <cascade effects>
        decision: <decision log entry path>
    """
    lines: list[str] = []

    # Subject line. Prefer caller-provided summary; fall back to a default.
    subject = sess.summary_line or _default_summary(sess)
    lines.append(f"workflow: {subject}")
    lines.append("")  # blank line between subject and body

    # Trigger.
    if sess.event:
        actor = getattr(sess.event, "actor", None) or "unknown"
        event_name = getattr(sess.event, "name", "manual")
        lines.append(f"trigger: {event_name} by @{actor}")

    # Classification.
    if sess.classification:
        cls = sess.classification.get("classification", "n/a")
        by = sess.classification.get("classified_by", "n/a")
        rationale = sess.classification.get("rationale", "")
        line = f"classification: {cls} ({by})"
        if rationale:
            line += f" — {rationale}"
        lines.append(line)

    # Artifacts changed.
    if sess.artifacts_changed:
        lines.append("artifacts:")
        for entry in sess.artifacts_changed:
            lines.append(f"  - {entry}")

    # Lifecycle changed.
    if sess.lifecycle_changed:
        lines.append("lifecycle:")
        for entry in sess.lifecycle_changed:
            lines.append(f"  - {entry}")

    # Cascade.
    if sess.cascade_summary:
        lines.append("cascade:")
        for entry in sess.cascade_summary:
            lines.append(f"  - {entry}")

    # Decision log link. Resolved by log phase via `state/last_decision_ref.txt`.
    decision_ref_path = sess.workflow_dir / "state" / "last_decision_ref.txt"
    if decision_ref_path.exists():
        ref = decision_ref_path.read_text().strip()
        lines.append(f"decision: {ref}")

    # Persist message to a state file so the CI workflow's commit step
    # can pick it up if the helper itself didn't commit (e.g., in
    # workflows that prefer to run `git commit` from the workflow YAML).
    last_msg_path = sess.workflow_dir / "state" / "last_commit_message"
    last_msg_path.parent.mkdir(parents=True, exist_ok=True)
    message = "\n".join(lines)
    last_msg_path.write_text(message + "\n")

    return message


def _default_summary(sess: Session) -> str:
    """Build a reasonable subject line if the caller didn't set one."""
    parts = []
    if sess.event:
        parts.append(getattr(sess.event, "name", "reconcile"))
    if sess.classification:
        cls = sess.classification.get("classification")
        if cls:
            parts.append(f"({cls})")
    if sess.artifacts_changed:
        parts.append(f"{len(sess.artifacts_changed)} artifact change(s)")
    if sess.cascade_summary:
        parts.append(f"{len(sess.cascade_summary)} cascade effect(s)")
    if not parts:
        parts.append("reconcile pass")
    return " — ".join(parts)


# ---------------------------------------------------------------------------
# Test-time hooks
# ---------------------------------------------------------------------------


def is_in_ci() -> bool:
    """Detect CI context. Used by some helpers to choose defaults
    (e.g., abort vs. prompt on dirty tree)."""
    return os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true"
