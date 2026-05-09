"""
helpers/labels.py

Label taxonomy synchronization and mutual-exclusion enforcement.

The skill maintains a canonical label taxonomy (see
references/vocabulary/labels.md). This helper:

- Syncs taxonomy with provider (idempotent label creation/update).
- Enforces mutual-exclusion groups (e.g., one `stage:*` per item).
- Resolves aliases (e.g., team's `bug` → canonical `type:bugfix`).
"""

from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger(__name__)

# Mutual-exclusion groups. The key is a label namespace (or a tuple of
# namespaces); only one label from the group can be applied at once.
MUTUAL_EXCLUSION_GROUPS = {
    "stage": "stage:",
    "type": "type:",
    "spec_state": "spec:",
    "adr_state": "adr:",
    "impl_plan_state": "impl-plan:",
    "test_plan_state": "test-plan:",
    "obs_plan_state": "obs-plan:",
    "threat_model_state": "threat-model:",
}

# Per-audience doc-state groups are dynamic; computed at runtime.
DOC_AUDIENCE_PREFIXES = (
    "doc:developer:",
    "doc:operator:",
    "doc:sre:",
    "doc:support:",
    "doc:product:",
    "doc:end_user:",
    "doc:security:",
    "doc:legal:",
    "doc:architect:",
)


def resolve_alias(label: str, aliases: dict) -> str:
    """Map an aliased label to its canonical form."""
    return aliases.get(label, label)


def find_mutex_group(label: str) -> str | None:
    """Return the mutex group key for a label, or None if multi-applicable."""
    for group_name, prefix in MUTUAL_EXCLUSION_GROUPS.items():
        if label.startswith(prefix):
            return group_name
    for prefix in DOC_AUDIENCE_PREFIXES:
        if label.startswith(prefix):
            return f"doc_state_{prefix.split(':')[1]}"
    return None


def compute_label_diff(
    current: list[str],
    target: list[str],
    aliases: dict | None = None,
) -> dict[str, list[str]]:
    """
    Compute the set of labels to add and remove to move from current
    to target, respecting mutual exclusion and aliases.
    """
    aliases = aliases or {}
    canonical_current = {resolve_alias(label, aliases) for label in current}
    canonical_target = {resolve_alias(label, aliases) for label in target}

    to_add = canonical_target - canonical_current
    to_remove = set()

    # For each label being added, remove conflicting mutex-group members.
    for new_label in to_add:
        group = find_mutex_group(new_label)
        if not group:
            continue
        for existing in canonical_current:
            if existing == new_label:
                continue
            if find_mutex_group(existing) == group:
                to_remove.add(existing)

    # Plus any explicit removals (current minus target, minus what's added)
    for old_label in canonical_current - canonical_target:
        to_remove.add(old_label)

    # Drop labels from to_remove that are aliased forms of labels still in
    # target — we don't unaliased existing labels.
    return {
        "add": sorted(to_add - canonical_current),
        "remove": sorted(to_remove),
    }


def apply_diff_via_gh(
    repo: str, item_number: int, diff: dict[str, list[str]], item_kind: str = "issues"
) -> None:
    """
    Apply a label diff to an issue or PR via `gh api`.
    `item_kind` is "issues" for both issues and PRs (GitHub uses the same
    endpoint).
    """
    if diff["add"]:
        for label in diff["add"]:
            subprocess.run(
                [
                    "gh",
                    "api",
                    f"repos/{repo}/issues/{item_number}/labels",
                    "--method",
                    "POST",
                    "-f",
                    f"labels[]={label}",
                ],
                check=False,
            )
    if diff["remove"]:
        for label in diff["remove"]:
            subprocess.run(
                [
                    "gh",
                    "api",
                    f"repos/{repo}/issues/{item_number}/labels/{label}",
                    "--method",
                    "DELETE",
                ],
                check=False,
            )


def sync_taxonomy(repo: str, taxonomy: list[dict]) -> dict:
    """
    Idempotent label creation/update against provider.

    Args:
        repo: "owner/name"
        taxonomy: list of { name, color, description }

    Returns:
        summary: { "created": [...], "updated": [...], "unchanged": [...] }
    """
    existing = _list_existing_labels(repo)
    summary = {"created": [], "updated": [], "unchanged": []}

    for spec in taxonomy:
        name = spec["name"]
        match = next((label for label in existing if label["name"] == name), None)
        if match is None:
            _create_label(repo, spec)
            summary["created"].append(name)
        elif match.get("color") != spec.get("color") or match.get("description") != spec.get(
            "description"
        ):
            _update_label(repo, spec)
            summary["updated"].append(name)
        else:
            summary["unchanged"].append(name)

    return summary


def _list_existing_labels(repo: str) -> list[dict]:
    import json

    result = subprocess.run(
        ["gh", "api", "--paginate", f"repos/{repo}/labels"],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def _create_label(repo: str, spec: dict) -> None:
    args = [
        "gh",
        "api",
        f"repos/{repo}/labels",
        "--method",
        "POST",
        "-f",
        f"name={spec['name']}",
        "-f",
        f"color={spec.get('color', 'cccccc')}",
    ]
    if spec.get("description"):
        args.extend(["-f", f"description={spec['description']}"])
    subprocess.run(args, check=False)


def _update_label(repo: str, spec: dict) -> None:
    args = [
        "gh",
        "api",
        f"repos/{repo}/labels/{spec['name']}",
        "--method",
        "PATCH",
        "-f",
        f"new_name={spec['name']}",
        "-f",
        f"color={spec.get('color', 'cccccc')}",
    ]
    if spec.get("description"):
        args.extend(["-f", f"description={spec['description']}"])
    subprocess.run(args, check=False)
