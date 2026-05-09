"""
helpers/transport/poll.py

Polling pass implementation. Used when `transport.mode: polling`.

The poll cursor (`.workflow/state/poll_cursor.yml`) tracks the last-
processed timestamp per resource. Each pass:

1. Read cursor.
2. For each resource (issues, PRs, comments, pushes), call `gh api`
   with `since={cursor}`.
3. For each new item observed, normalize via `transport.normalize` and
   dispatch via `reconcile`.
4. Update cursor on success.

This module is a thin orchestrator. The heavy lifting is in
`transport.normalize` and the reconcile loop.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import subprocess

import yaml

from .. import config_io
from ..reconcile import checkpoint
from . import normalize

logger = logging.getLogger(__name__)

CURSOR_FILE = Path(".workflow/state/poll_cursor.yml")
OVERLAP_SECONDS = 60  # re-poll a small overlap to avoid missed events


def run_poll_pass() -> dict:
    """
    Run one polling pass. Returns a summary dict.
    """
    config = config_io.load()
    repo = config["repo"]["identifier"]
    cursor = _load_cursor()
    new_cursor = dict(cursor)
    summary = {"events_processed": 0, "errors": []}

    for resource in ("pull_requests", "issues", "comments", "pushes"):
        since = cursor.get(resource) or _now_iso()
        try:
            items = _fetch_since(repo, resource, since)
            for item in items:
                events = _items_to_events(resource, item)
                for event in events:
                    checkpoint.reconcile_with_checkpoint(
                        intent="event_driven",
                        context={"event": event},
                    )
                    summary["events_processed"] += 1
            new_cursor[resource] = _now_iso()
        except Exception as e:
            logger.error(f"Polling {resource} failed: {e}")
            summary["errors"].append({"resource": resource, "error": str(e)})

    _save_cursor(new_cursor)
    return summary


def _fetch_since(repo: str, resource: str, since: str) -> list[dict]:
    """Fetch items updated since the cursor via `gh api`."""
    if resource == "pull_requests":
        url = f"repos/{repo}/pulls?state=all&sort=updated&direction=asc&since={since}"
    elif resource == "issues":
        url = f"repos/{repo}/issues?state=all&sort=updated&direction=asc&since={since}"
    elif resource == "comments":
        url = f"repos/{repo}/issues/comments?sort=updated&direction=asc&since={since}"
    elif resource == "pushes":
        # Pushes don't have an updated-since API; use commits on default branch.
        url = f"repos/{repo}/commits?since={since}"
    else:
        return []

    result = subprocess.run(
        ["gh", "api", "--paginate", url],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def _items_to_events(resource: str, item: dict) -> list[dict]:
    """
    Convert a polled item into the closest GitHub-style event payload
    so `normalize` can translate it. This is a coarser path than webhooks
    because polled APIs don't carry the full webhook envelope.
    """
    if resource == "pull_requests":
        # Treat all polled PRs as "synchronized" — playbook is idempotent.
        return normalize.normalize_event(
            "pull_request",
            {
                "action": "synchronize",
                "pull_request": item,
                "before": None,
                "after": item.get("head", {}).get("sha"),
            },
        )
    if resource == "issues":
        # If the issue has a state change relative to our last sidecar, the
        # `issues.opened/closed/reopened` distinction is made downstream.
        # For polling, dispatch a generic `issue.opened` if new; reconcile
        # idempotency handles the rest.
        return normalize.normalize_event(
            "issues",
            {
                "action": "opened",
                "issue": item,
            },
        )
    if resource == "comments":
        return normalize.normalize_event(
            "issue_comment",
            {
                "action": "created",
                "comment": item,
                "issue": {"number": _issue_number_from_comment(item)},
            },
        )
    if resource == "pushes":
        return normalize.normalize_event(
            "push",
            {
                "ref": "refs/heads/" + (item.get("branch") or "main"),
                "before": item.get("parents", [{}])[0].get("sha"),
                "after": item.get("sha"),
                "commits": [
                    {"id": item.get("sha"), "message": item.get("commit", {}).get("message")}
                ],
            },
        )
    return []


def _issue_number_from_comment(comment: dict) -> int | None:
    """Extract issue number from a comment's issue_url."""
    url = comment.get("issue_url", "")
    if "/issues/" in url:
        try:
            return int(url.rsplit("/", 1)[-1])
        except ValueError:
            return None
    return None


def _load_cursor() -> dict:
    if not CURSOR_FILE.exists():
        return {}
    with CURSOR_FILE.open() as f:
        return yaml.safe_load(f) or {}


def _save_cursor(cursor: dict) -> None:
    CURSOR_FILE.parent.mkdir(parents=True, exist_ok=True)
    with CURSOR_FILE.open("w") as f:
        yaml.dump(cursor, f, sort_keys=False)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
