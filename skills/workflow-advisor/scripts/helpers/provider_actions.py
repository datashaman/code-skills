"""
Provider action queue and GitHub command builders.

The reconcile loop writes `.workflow/` state first. Provider mutations are
represented as explicit action records so callers can dry-run, review, queue,
or execute them without hiding network side effects inside playbook logic.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Callable, Iterable

QUEUE_FILE = Path(".workflow/provider-actions/pending.jsonl")

Runner = Callable[[list[str]], subprocess.CompletedProcess]


def queue_action(
    action: str,
    payload: dict,
    reason: str = "",
    queue_path: Path | str = QUEUE_FILE,
) -> dict:
    """Append a provider action record to the pending queue."""
    record = {
        "ts": _now_iso(),
        "provider": "github",
        "action": action,
        "payload": payload,
        "reason": reason,
        "status": "pending",
    }
    path = Path(queue_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def labels_apply_diff(
    repo: str,
    item_number: int | str,
    diff: dict[str, list[str]],
    dry_run: bool = True,
    runner: Runner | None = None,
) -> dict:
    """Apply or preview an issue/PR label diff."""
    commands: list[list[str]] = []
    for label in diff.get("add", []):
        commands.append(
            [
                "gh",
                "api",
                f"repos/{repo}/issues/{item_number}/labels",
                "--method",
                "POST",
                "-f",
                f"labels[]={label}",
            ]
        )
    for label in diff.get("remove", []):
        commands.append(
            [
                "gh",
                "api",
                f"repos/{repo}/issues/{item_number}/labels/{label}",
                "--method",
                "DELETE",
            ]
        )
    return _run_or_preview("labels.apply_diff", commands, dry_run, runner)


def comment_update_or_post(
    repo: str,
    item_number: int | str,
    body: str,
    marker: str | None = None,
    comment_id: int | str | None = None,
    dry_run: bool = True,
    runner: Runner | None = None,
) -> dict:
    """
    Update a known comment or post a new one.

    Marker-based lookup is intentionally queued for a later richer executor; the
    safe first implementation posts unless a concrete comment id is supplied.
    """
    if marker and marker not in body:
        body = f"{body.rstrip()}\n\n<!-- {marker} -->"

    if comment_id:
        command = [
            "gh",
            "api",
            f"repos/{repo}/issues/comments/{comment_id}",
            "--method",
            "PATCH",
            "-f",
            f"body={body}",
        ]
    else:
        command = [
            "gh",
            "api",
            f"repos/{repo}/issues/{item_number}/comments",
            "--method",
            "POST",
            "-f",
            f"body={body}",
        ]
    return _run_or_preview("comment.update_or_post", [command], dry_run, runner)


def assign_reviewers(
    repo: str,
    pr_number: int | str,
    reviewers: Iterable[str],
    dry_run: bool = True,
    runner: Runner | None = None,
) -> dict:
    """Request reviewers for a pull request."""
    command = [
        "gh",
        "api",
        f"repos/{repo}/pulls/{pr_number}/requested_reviewers",
        "--method",
        "POST",
    ]
    for reviewer in reviewers:
        command.extend(["-f", f"reviewers[]={reviewer.lstrip('@')}"])
    return _run_or_preview("pr.assign_reviewers", [command], dry_run, runner)


def request_changes(
    repo: str,
    pr_number: int | str,
    body: str,
    dry_run: bool = True,
    runner: Runner | None = None,
) -> dict:
    """Submit a request-changes review."""
    command = [
        "gh",
        "api",
        f"repos/{repo}/pulls/{pr_number}/reviews",
        "--method",
        "POST",
        "-f",
        "event=REQUEST_CHANGES",
        "-f",
        f"body={body}",
    ]
    return _run_or_preview("pr.request_changes", [command], dry_run, runner)


def dismiss_review(
    repo: str,
    pr_number: int | str,
    review_id: int | str,
    message: str,
    dry_run: bool = True,
    runner: Runner | None = None,
) -> dict:
    """Dismiss a stale pull request review."""
    command = [
        "gh",
        "api",
        f"repos/{repo}/pulls/{pr_number}/reviews/{review_id}/dismissals",
        "--method",
        "PUT",
        "-f",
        f"message={message}",
    ]
    return _run_or_preview("pr.dismiss_review", [command], dry_run, runner)


def set_draft(
    repo: str,
    pr_number: int | str,
    draft: bool,
    dry_run: bool = True,
    runner: Runner | None = None,
) -> dict:
    """
    Mark a PR draft or ready-for-review.

    GitHub exposes this through GraphQL. The first implementation records the
    intended transition; a later executor can resolve the PR node id and run the
    mutation.
    """
    action = "pr.set_draft" if draft else "pr.mark_ready_for_review"
    payload = {"repo": repo, "pr_number": pr_number, "draft": draft}
    if dry_run:
        return {"action": action, "dry_run": True, "commands": [], "payload": payload}
    queue_action(action, payload, reason="GraphQL node-id resolution required")
    return {"action": action, "queued": True, "commands": [], "payload": payload}


def _run_or_preview(
    action: str,
    commands: list[list[str]],
    dry_run: bool,
    runner: Runner | None,
) -> dict:
    result = {"action": action, "dry_run": dry_run, "commands": commands}
    if dry_run:
        return result
    run = runner or _default_runner
    completed = [run(command) for command in commands]
    return {**result, "completed": [process.returncode for process in completed]}


def _default_runner(command: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=False, capture_output=True, text=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
