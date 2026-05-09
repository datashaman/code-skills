"""
helpers/transport/normalize.py

Translate provider-specific events into the abstract event vocabulary.

For v1, only GitHub is supported. The mapping table is the source of
truth — see references/providers/github.md for the full catalog.

The normalizer's job:
1. Read the GitHub event name + action subfield + payload.
2. Compute the abstract event name from the registry.
3. Strip provider-specific fields and produce a normalized payload.
4. Detect derived events (slash command in a comment, approval state in
   a review, etc.) and emit them as additional events.

Output: a list (often singleton) of normalized events. Playbooks see
only normalized events.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import re
from typing import Any

logger = logging.getLogger(__name__)


# Slash command pattern: /command optional-args, possibly with --flag "value"
SLASH_COMMAND_RE = re.compile(r"^\s*/([a-z][\w-]+)\s*(.*)$", re.MULTILINE)


def normalize_event(
    github_event_name: str,
    payload: dict,
    provider: str = "github",
) -> list[dict]:
    """
    Normalize a single GitHub webhook payload into one or more abstract
    events.

    Returns:
        events: list of { "name": str, "payload": dict, "provider_meta": dict }
    """
    if provider != "github":
        raise ValueError(f"v1 supports github only; got {provider!r}")

    handler = _GITHUB_HANDLERS.get(github_event_name)
    if handler is None:
        logger.debug(f"No handler for GitHub event {github_event_name}; ignoring.")
        return []

    return handler(payload)


def translate(
    provider: str = "github_actions",
    event_name: str | None = None,
    event_action: str | None = None,
    payload_path: str | None = None,
) -> dict | None:
    """
    CLI compatibility wrapper. Reads a provider payload and returns the
    first normalized event. Multiple emitted events are handled later by
    the full dispatcher; this keeps the current smoke path deterministic.
    """
    if not event_name and not payload_path:
        return None

    payload: dict[str, Any] = {}
    if payload_path:
        with Path(payload_path).open() as f:
            payload = json.load(f)
    if event_action and "action" not in payload:
        payload["action"] = event_action

    events = normalize_event(event_name or "", payload, provider="github")
    if not events:
        return None
    event = events[0]
    delivery_id = event.get("provider_meta", {}).get("delivery_id")
    if delivery_id:
        event["id"] = delivery_id
    return event


# ---------------------------------------------------------------------------
# Per-event handlers
# ---------------------------------------------------------------------------


def _h_pull_request(payload: dict) -> list[dict]:
    action = payload.get("action")
    pr = payload.get("pull_request", {})
    base_payload = {
        "pr_number": pr.get("number"),
        "title": pr.get("title"),
        "body": pr.get("body"),
        "author": (pr.get("user") or {}).get("login"),
        "base": (pr.get("base") or {}).get("ref"),
        "head": (pr.get("head") or {}).get("ref"),
        "draft": pr.get("draft"),
        "files": [
            f["filename"] for f in payload.get("files") or []
        ],  # populated by caller if needed
        "labels": [label["name"] for label in pr.get("labels") or []],
    }

    if action == "opened":
        return [_event("pull_request.opened", base_payload, payload)]
    if action == "synchronize":
        return [
            _event(
                "pull_request.synchronized",
                {
                    **base_payload,
                    "before_sha": payload.get("before"),
                    "after_sha": payload.get("after"),
                },
                payload,
            )
        ]
    if action == "ready_for_review":
        return [_event("pull_request.ready_for_review", base_payload, payload)]
    if action == "closed":
        merged = pr.get("merged")
        if merged:
            return [
                _event(
                    "pull_request.merged",
                    {
                        **base_payload,
                        "merge_commit_sha": pr.get("merge_commit_sha"),
                    },
                    payload,
                )
            ]
        return [
            _event(
                "pull_request.closed",
                {
                    **base_payload,
                    "actor": (payload.get("sender") or {}).get("login"),
                },
                payload,
            )
        ]
    if action == "reopened":
        return [_event("pull_request.reopened", base_payload, payload)]
    if action == "labeled":
        return [
            _event(
                "pull_request.labeled",
                {
                    **base_payload,
                    "label": (payload.get("label") or {}).get("name"),
                    "actor": (payload.get("sender") or {}).get("login"),
                },
                payload,
            )
        ]
    if action == "unlabeled":
        return [
            _event(
                "pull_request.unlabeled",
                {
                    **base_payload,
                    "label": (payload.get("label") or {}).get("name"),
                    "actor": (payload.get("sender") or {}).get("login"),
                },
                payload,
            )
        ]
    if action == "assigned":
        return [
            _event(
                "pull_request.assigned",
                {
                    **base_payload,
                    "assignee": (payload.get("assignee") or {}).get("login"),
                    "actor": (payload.get("sender") or {}).get("login"),
                },
                payload,
            )
        ]
    if action == "unassigned":
        return [
            _event(
                "pull_request.unassigned",
                {
                    **base_payload,
                    "assignee": (payload.get("assignee") or {}).get("login"),
                    "actor": (payload.get("sender") or {}).get("login"),
                },
                payload,
            )
        ]
    if action == "review_requested":
        return [
            _event(
                "pull_request.review_requested",
                {
                    **base_payload,
                    "requested_reviewer": (payload.get("requested_reviewer") or {}).get("login"),
                },
                payload,
            )
        ]
    if action == "edited":
        # Could be title or body change; check `changes`
        changes = payload.get("changes") or {}
        events = []
        if "title" in changes:
            events.append(
                _event(
                    "pull_request.title_changed",
                    {
                        **base_payload,
                        "before": changes["title"].get("from"),
                        "after": pr.get("title"),
                        "actor": (payload.get("sender") or {}).get("login"),
                    },
                    payload,
                )
            )
        if "body" in changes:
            events.append(
                _event(
                    "pull_request.body_changed",
                    {
                        **base_payload,
                        "before": changes["body"].get("from"),
                        "after": pr.get("body"),
                        "actor": (payload.get("sender") or {}).get("login"),
                    },
                    payload,
                )
            )
        return events

    return []


def _h_pull_request_review(payload: dict) -> list[dict]:
    action = payload.get("action")
    if action != "submitted":
        return []

    review = payload.get("review", {})
    pr = payload.get("pull_request", {})
    state = review.get("state", "").lower()
    base = {
        "pr_number": pr.get("number"),
        "reviewer": (review.get("user") or {}).get("login"),
        "state": state,
        "body": review.get("body"),
    }

    events = [_event("pull_request.review_submitted", base, payload)]
    if state == "approved":
        events.append(_event("pull_request.approved", base, payload))
    elif state == "changes_requested":
        events.append(_event("pull_request.changes_requested", base, payload))
    return events


def _h_pull_request_review_comment(payload: dict) -> list[dict]:
    action = payload.get("action")
    if action != "created":
        return []
    comment = payload.get("comment", {})
    pr = payload.get("pull_request", {})
    return [
        _event(
            "review.thread.created",
            {
                "pr_number": pr.get("number"),
                "thread_id": comment.get("pull_request_review_id"),
                "file": comment.get("path"),
                "line": comment.get("line"),
                "body": comment.get("body"),
                "author": (comment.get("user") or {}).get("login"),
            },
            payload,
        )
    ]


def _h_issues(payload: dict) -> list[dict]:
    action = payload.get("action")
    issue = payload.get("issue", {})
    base = {
        "issue_number": issue.get("number"),
        "title": issue.get("title"),
        "body": issue.get("body"),
        "author": (issue.get("user") or {}).get("login"),
        "labels": [label["name"] for label in issue.get("labels") or []],
    }

    name_map = {
        "opened": "issue.opened",
        "closed": "issue.closed",
        "reopened": "issue.reopened",
    }
    if action in name_map:
        extra = {}
        if action == "closed":
            extra["state_reason"] = issue.get("state_reason")
            extra["actor"] = (payload.get("sender") or {}).get("login")
        if action == "reopened":
            extra["actor"] = (payload.get("sender") or {}).get("login")
        return [_event(name_map[action], {**base, **extra}, payload)]

    if action == "labeled":
        return [
            _event(
                "issue.labeled",
                {
                    **base,
                    "label": (payload.get("label") or {}).get("name"),
                    "actor": (payload.get("sender") or {}).get("login"),
                },
                payload,
            )
        ]
    if action == "unlabeled":
        return [
            _event(
                "issue.unlabeled",
                {
                    **base,
                    "label": (payload.get("label") or {}).get("name"),
                    "actor": (payload.get("sender") or {}).get("login"),
                },
                payload,
            )
        ]
    if action == "assigned":
        return [
            _event(
                "issue.assigned",
                {
                    **base,
                    "assignee": (payload.get("assignee") or {}).get("login"),
                    "actor": (payload.get("sender") or {}).get("login"),
                },
                payload,
            )
        ]
    if action == "unassigned":
        return [
            _event(
                "issue.unassigned",
                {
                    **base,
                    "assignee": (payload.get("assignee") or {}).get("login"),
                    "actor": (payload.get("sender") or {}).get("login"),
                },
                payload,
            )
        ]

    return []


def _h_issue_comment(payload: dict) -> list[dict]:
    action = payload.get("action")
    if action not in ("created", "edited"):
        return []
    comment = payload.get("comment", {})
    issue = payload.get("issue", {})
    parent_type = "pr" if "pull_request" in issue else "issue"
    body = comment.get("body") or ""

    base = {
        "parent_type": parent_type,
        "parent_number": issue.get("number"),
        "body": body,
        "author": (comment.get("user") or {}).get("login"),
        "comment_id": comment.get("id"),
    }

    events = []
    if action == "created":
        events.append(_event("comment.created", base, payload))
    else:  # edited
        events.append(
            _event(
                "comment.edited",
                {
                    **base,
                    "before_body": (payload.get("changes", {}).get("body") or {}).get("from"),
                },
                payload,
            )
        )

    # Detect slash command
    slash = _detect_slash_command(body)
    if slash:
        command, args = slash
        events.append(
            _event(
                "comment.slash_command",
                {
                    **base,
                    "command": command,
                    "args": args,
                },
                payload,
            )
        )

    return events


def _h_push(payload: dict) -> list[dict]:
    ref = payload.get("ref", "")
    branch = ref.replace("refs/heads/", "") if ref.startswith("refs/heads/") else ref
    base = {
        "branch": branch,
        "before_sha": payload.get("before"),
        "after_sha": payload.get("after"),
        "actor": (payload.get("pusher") or {}).get("name")
        or (payload.get("sender") or {}).get("login"),
        "commits": [
            {
                "sha": c.get("id"),
                "message": c.get("message"),
                "author": (c.get("author") or {}).get("name"),
            }
            for c in payload.get("commits") or []
        ],
        "files": _files_from_push(payload),
    }
    repo = payload.get("repository", {})
    if branch and branch == repo.get("default_branch"):
        return [
            _event("push.protected_branch", {**base, "branch_is_default": True}, payload),
            _event("push", base, payload),
        ]
    return [_event("push", base, payload)]


def _h_create(payload: dict) -> list[dict]:
    ref_type = payload.get("ref_type")
    if ref_type == "branch":
        return [
            _event(
                "branch.created",
                {
                    "branch": payload.get("ref"),
                    "sha": payload.get("master_branch"),
                    "actor": (payload.get("sender") or {}).get("login"),
                },
                payload,
            )
        ]
    if ref_type == "tag":
        return [
            _event(
                "tag.created",
                {
                    "tag": payload.get("ref"),
                    "sha": payload.get("master_branch"),
                    "actor": (payload.get("sender") or {}).get("login"),
                },
                payload,
            )
        ]
    return []


def _h_delete(payload: dict) -> list[dict]:
    if payload.get("ref_type") == "branch":
        return [
            _event(
                "branch.deleted",
                {
                    "branch": payload.get("ref"),
                    "actor": (payload.get("sender") or {}).get("login"),
                },
                payload,
            )
        ]
    return []


def _h_release(payload: dict) -> list[dict]:
    action = payload.get("action")
    release = payload.get("release", {})
    base = {
        "tag": release.get("tag_name"),
        "name": release.get("name"),
        "body": release.get("body"),
        "author": (release.get("author") or {}).get("login"),
    }
    if action == "created":
        return [_event("release.created", base, payload)]
    if action == "published":
        return [_event("release.published", base, payload)]
    return []


def _h_schedule(payload: dict) -> list[dict]:
    cron = payload.get("schedule", "")
    if "* * 0" in cron or _is_weekly(cron):
        return [_event("schedule.weekly", {"scheduled_at": payload.get("scheduled_at")}, payload)]
    return [_event("schedule.daily", {"scheduled_at": payload.get("scheduled_at")}, payload)]


def _h_workflow_dispatch(payload: dict) -> list[dict]:
    inputs = payload.get("inputs") or {}
    return [
        _event(
            "schedule.on_demand",
            {
                "actor": (payload.get("sender") or {}).get("login"),
                "intent": inputs.get("operation", "reconcile"),
            },
            payload,
        )
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _event(name: str, payload: dict, original: dict) -> dict:
    return {
        "name": name,
        "payload": payload,
        "provider_meta": {
            "delivery_id": original.get("X-GitHub-Delivery"),
            "repo": (original.get("repository") or {}).get("full_name"),
        },
    }


def _detect_slash_command(body: str) -> tuple[str, str] | None:
    """
    Parse `/command args` from the start of a comment body.
    Only considers the first line that starts with `/`.
    """
    if not body:
        return None
    for line in body.splitlines():
        m = SLASH_COMMAND_RE.match(line)
        if m:
            return m.group(1), m.group(2).strip()
    return None


def _files_from_push(payload: dict) -> list[str]:
    """Extract changed files from a push payload (best-effort)."""
    files: set[str] = set()
    for commit in payload.get("commits") or []:
        for k in ("added", "modified", "removed"):
            for f in commit.get(k) or []:
                files.add(f)
    return sorted(files)


def _is_weekly(cron: str) -> bool:
    """Crude heuristic — true if cron has a day-of-week set."""
    parts = cron.split()
    if len(parts) >= 5:
        dow = parts[4]
        return dow not in ("*", "?")
    return False


_GITHUB_HANDLERS = {
    "pull_request": _h_pull_request,
    "pull_request_review": _h_pull_request_review,
    "pull_request_review_comment": _h_pull_request_review_comment,
    "issues": _h_issues,
    "issue_comment": _h_issue_comment,
    "push": _h_push,
    "create": _h_create,
    "delete": _h_delete,
    "release": _h_release,
    "schedule": _h_schedule,
    "workflow_dispatch": _h_workflow_dispatch,
}
