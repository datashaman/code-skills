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
APPLIED_FILE = Path(".workflow/provider-actions/applied.jsonl")
FAILED_FILE = Path(".workflow/provider-actions/failed.jsonl")

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


def list_pending(queue_path: Path | str = QUEUE_FILE) -> list[dict]:
    """Read pending provider actions from JSONL."""
    path = Path(queue_path)
    if not path.exists():
        return []
    records = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def flush_queue(
    dry_run: bool = True,
    queue_path: Path | str = QUEUE_FILE,
    applied_path: Path | str = APPLIED_FILE,
    failed_path: Path | str = FAILED_FILE,
    runner: Runner | None = None,
) -> dict:
    """
    Execute or preview pending provider actions.

    Dry-run leaves the queue untouched. Apply mode appends successful records to
    applied_path, failed records to failed_path, and rewrites pending with only
    records that did not complete.
    """
    pending = list_pending(queue_path)
    results = []
    remaining = []
    applied = []
    failed = []

    for record in pending:
        result = execute_record(record, dry_run=dry_run, runner=runner)
        results.append(result)
        if dry_run:
            continue
        if result.get("ok"):
            applied.append(
                {**record, "status": "applied", "result": result, "applied_at": _now_iso()}
            )
        else:
            failed_record = {
                **record,
                "status": "failed",
                "result": result,
                "failed_at": _now_iso(),
            }
            failed.append(failed_record)
            remaining.append(record)

    if not dry_run:
        _append_jsonl(applied_path, applied)
        _append_jsonl(failed_path, failed)
        _write_jsonl(queue_path, remaining)

    return {
        "dry_run": dry_run,
        "pending": len(pending),
        "applied": len(applied),
        "failed": len(failed),
        "remaining": len(remaining) if not dry_run else len(pending),
        "results": results,
    }


def execute_record(record: dict, dry_run: bool = True, runner: Runner | None = None) -> dict:
    """Execute one provider action record."""
    action = record.get("action")
    payload = record.get("payload") or {}

    try:
        if action == "labels.apply_diff":
            result = labels_apply_diff(
                repo=payload["repo"],
                item_number=payload["item_number"],
                diff=payload["diff"],
                dry_run=dry_run,
                runner=runner,
            )
        elif action == "comment.update_or_post":
            result = comment_update_or_post(
                repo=payload["repo"],
                item_number=payload["item_number"],
                body=payload["body"],
                marker=payload.get("marker"),
                comment_id=payload.get("comment_id"),
                dry_run=dry_run,
                runner=runner,
            )
        elif action in {"pr.assign_reviewers", "role.assign_reviewers"}:
            result = assign_reviewers(
                repo=payload["repo"],
                pr_number=payload["pr_number"],
                reviewers=payload.get("reviewers", []),
                dry_run=dry_run,
                runner=runner,
            )
        elif action == "pr.request_changes":
            result = request_changes(
                repo=payload["repo"],
                pr_number=payload["pr_number"],
                body=payload["body"],
                dry_run=dry_run,
                runner=runner,
            )
        elif action == "pr.dismiss_review":
            result = dismiss_review(
                repo=payload["repo"],
                pr_number=payload["pr_number"],
                review_id=payload["review_id"],
                message=payload["message"],
                dry_run=dry_run,
                runner=runner,
            )
        elif action in {"pr.set_draft", "pr.mark_ready_for_review"}:
            result = set_draft(
                repo=payload["repo"],
                pr_number=payload["pr_number"],
                draft=bool(payload.get("draft", action == "pr.set_draft")),
                dry_run=dry_run,
                runner=runner,
            )
        else:
            return {"action": action, "ok": False, "error": f"unknown provider action: {action}"}
    except KeyError as exc:
        return {"action": action, "ok": False, "error": f"missing payload key: {exc.args[0]}"}

    ok = dry_run or all(code == 0 for code in result.get("completed", []))
    return {**result, "ok": ok}


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

    In apply mode, a marker without a concrete comment id is resolved against
    existing issue/PR comments before deciding whether to PATCH or POST.
    """
    if marker and marker not in body:
        body = f"{body.rstrip()}\n\n<!-- {marker} -->"

    completed: list[int] = []
    commands: list[list[str]] = []
    run = runner or _default_runner

    if marker and not comment_id and not dry_run:
        list_command = _list_comments_command(repo, item_number)
        commands.append(list_command)
        listed = run(list_command)
        completed.append(listed.returncode)
        if listed.returncode != 0:
            return {
                "action": "comment.update_or_post",
                "dry_run": dry_run,
                "commands": commands,
                "completed": completed,
                "error": listed.stderr,
            }
        comment_id = _find_marker_comment_id(listed.stdout, marker)

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
    commands.append(command)
    if dry_run:
        return {"action": "comment.update_or_post", "dry_run": True, "commands": commands}

    completed.append(run(command).returncode)
    return {
        "action": "comment.update_or_post",
        "dry_run": False,
        "commands": commands,
        "completed": completed,
    }


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
    """Mark a PR draft or ready-for-review."""
    action = "pr.set_draft" if draft else "pr.mark_ready_for_review"
    command = ["gh", "pr", "ready", str(pr_number), "--repo", repo]
    if draft:
        command.append("--undo")
    return _run_or_preview(action, [command], dry_run, runner)


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


def _list_comments_command(repo: str, item_number: int | str) -> list[str]:
    return ["gh", "api", f"repos/{repo}/issues/{item_number}/comments", "--paginate"]


def _find_marker_comment_id(comments_json: str, marker: str) -> int | str | None:
    try:
        comments = json.loads(comments_json or "[]")
    except json.JSONDecodeError:
        return None

    needle = marker if marker.startswith("<!--") else f"<!-- {marker} -->"
    for comment in comments:
        if needle in str(comment.get("body", "")):
            return comment.get("id")
    return None


def _append_jsonl(path: Path | str, records: list[dict]) -> None:
    if not records:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a") as f:
        for record in records:
            f.write(json.dumps(record, sort_keys=True) + "\n")


def _write_jsonl(path: Path | str, records: list[dict]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not records:
        target.write_text("")
        return
    with target.open("w") as f:
        for record in records:
            f.write(json.dumps(record, sort_keys=True) + "\n")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
