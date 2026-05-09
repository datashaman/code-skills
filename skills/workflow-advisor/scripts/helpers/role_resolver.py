"""
helpers/role_resolver.py

Resolve role names to concrete members. Heavily used by playbooks for
reviewer assignment, notifications, and authorization checks.

Resolution algorithm (matches references/vocabulary/roles.md):

1. Aliases first — if the role name is in config.roles.aliases, follow.
2. Members lookup — read config.roles.{role}.members.
3. Special values:
   - `any` → return repo collaborators (looked up via provider).
   - `[]` (empty) → empty-role fallback.
4. CODEOWNERS overlay (for `reviewer`) — intersect with paths.
5. Area-aware resolution — pick scoped members based on area labels.
6. De-duplication across roles.
"""

from __future__ import annotations

import logging
from pathlib import Path
import re
from typing import Any

logger = logging.getLogger(__name__)


CODEOWNERS_PATHS = (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS")


class RoleResolutionResult:
    """
    Result of resolving a role.

    Attributes:
        role: canonical role name (after alias resolution).
        members: list of resolved members (each dict with `type`, `handle`/`name`).
        empty_fallback: True if the role was empty and tech_lead was substituted.
        aliased_from: original role name if an alias was followed.
    """

    def __init__(
        self,
        role: str,
        members: list[dict],
        empty_fallback: bool = False,
        aliased_from: str | None = None,
    ):
        self.role = role
        self.members = members
        self.empty_fallback = empty_fallback
        self.aliased_from = aliased_from

    def github_handles(self) -> list[str]:
        """Return GitHub handles only — useful for `pr.assign_reviewers`."""
        return [m["handle"] for m in self.members if m.get("type") == "github"]

    def external_contacts(self) -> list[dict]:
        """Return external contacts only — for notification rendering."""
        return [m for m in self.members if m.get("type") == "external"]

    def __bool__(self) -> bool:
        return bool(self.members)


def resolve(
    role_name: str,
    config: dict,
    context: dict | None = None,
    provider_collaborators: list[str] | None = None,
) -> RoleResolutionResult:
    """
    Resolve a role to concrete members.

    Args:
        role_name: the role name being resolved.
        config: loaded `.workflow/config.yml`.
        context: optional `{ "paths": [...], "areas": [...] }` for
            area-aware resolution.
        provider_collaborators: optional list of GitHub handles for `any`
            resolution. If None and `any` is encountered, returns empty
            (caller can re-resolve once it has provider data).

    Returns:
        RoleResolutionResult.
    """
    context = context or {}
    roles_cfg = config.get("roles", {})

    # 1. Alias resolution
    aliases = roles_cfg.get("aliases", {})
    aliased_from = None
    if role_name in aliases:
        aliased_from = role_name
        role_name = aliases[role_name]
        logger.debug(f"Role alias: {aliased_from} → {role_name}")

    # 2. Members lookup
    role_cfg = roles_cfg.get(role_name)
    if not isinstance(role_cfg, dict):
        # Role not declared — return empty
        return RoleResolutionResult(
            role=role_name, members=[], empty_fallback=False, aliased_from=aliased_from
        )

    members_field = role_cfg.get("members", [])

    # 3. Special values
    if members_field == "any":
        if provider_collaborators is None:
            # Caller must supply; surface empty for now
            return RoleResolutionResult(role=role_name, members=[], aliased_from=aliased_from)
        return RoleResolutionResult(
            role=role_name,
            members=[{"type": "github", "handle": h} for h in provider_collaborators],
            aliased_from=aliased_from,
        )

    if not members_field:
        # 3b. Empty-role fallback — substitute tech_lead
        return _empty_role_fallback(role_name, config, context, aliased_from)

    members = _normalize_members(members_field, context)

    # 4. CODEOWNERS overlay (for `reviewer`)
    if role_name == "reviewer" and context.get("paths"):
        members = _overlay_codeowners(members, context["paths"])

    return RoleResolutionResult(role=role_name, members=members, aliased_from=aliased_from)


def resolve_multiple(
    role_names: list[str],
    config: dict,
    context: dict | None = None,
    provider_collaborators: list[str] | None = None,
) -> list[dict]:
    """
    Resolve multiple roles and return a deduplicated, flat list of members
    with the role(s) each member plays.

    Used when one gate requires multiple roles to approve.
    """
    seen: dict[tuple, dict] = {}
    for role_name in role_names:
        result = resolve(role_name, config, context, provider_collaborators)
        for member in result.members:
            key = _member_key(member)
            existing = seen.get(key)
            if existing:
                existing["roles"].add(result.role)
            else:
                seen[key] = {**member, "roles": {result.role}}
    # Convert sets to sorted lists for deterministic output
    return [{**m, "roles": sorted(m["roles"])} for m in seen.values()]


def check_authority(
    actor: str,
    command_or_action: str,
    config: dict,
) -> tuple[bool, list[str]]:
    """
    Check whether an actor is authorized to dispatch a command.

    Returns:
        (authorized, allowed_roles) — allowed_roles is the list of role
        names that would have authorized this; useful for the "this
        command requires X" reply.
    """
    auth_cfg = config.get("slash_commands", {}).get(command_or_action)
    if auth_cfg is None:
        # Command not configured — default deny
        return False, []

    if auth_cfg == "any":
        return True, ["any"]

    if isinstance(auth_cfg, str):
        # Single role name
        auth_cfg = [auth_cfg]

    if not isinstance(auth_cfg, list):
        # Special policies like `per_gate_override_policy` — caller resolves
        return False, []

    # Check actor against each authorized role's members
    for role_name in auth_cfg:
        result = resolve(role_name, config)
        if any(m.get("type") == "github" and m.get("handle") == actor for m in result.members):
            return True, auth_cfg

    return False, auth_cfg


def _normalize_members(members_field: Any, context: dict) -> list[dict]:
    """
    Normalize the various forms `members` can take.

    Supported shapes:
      - list of dicts: [{ type: github, handle: marlin }, ...]
      - dict by area: { auth: [...], payments: [...] } — pick by context.areas
    """
    if isinstance(members_field, list):
        return [m for m in members_field if isinstance(m, dict)]

    if isinstance(members_field, dict):
        # Area-aware resolution
        areas = context.get("areas") or []
        merged: list[dict] = []
        seen: set = set()
        for area in areas:
            for m in members_field.get(area, []):
                key = _member_key(m)
                if key not in seen:
                    seen.add(key)
                    merged.append(m)
        # Fallback: if no area matched, use the `default` key
        if not merged:
            merged = members_field.get("default", [])
        return merged

    return []


def _empty_role_fallback(
    role_name: str,
    config: dict,
    context: dict,
    aliased_from: str | None,
) -> RoleResolutionResult:
    """
    When a required role has no members, fall back to tech_lead.
    The caller is responsible for applying the
    `needs:role-assignment:{role}` label.
    """
    if role_name == "tech_lead":
        # tech_lead itself empty — nothing to fall back to
        return RoleResolutionResult(
            role=role_name, members=[], empty_fallback=False, aliased_from=aliased_from
        )

    tech_lead_cfg = config.get("roles", {}).get("tech_lead", {})
    members = _normalize_members(tech_lead_cfg.get("members", []), context)

    return RoleResolutionResult(
        role=role_name,
        members=members,
        empty_fallback=True,
        aliased_from=aliased_from,
    )


def _overlay_codeowners(members: list[dict], paths: list[str]) -> list[dict]:
    """
    Intersect resolved reviewers with CODEOWNERS pattern matches for the
    given paths. Members not matching any path are dropped; CODEOWNERS-
    only members whose patterns match are added.
    """
    codeowners = _load_codeowners()
    if not codeowners:
        return members

    matched_handles: set[str] = set()
    for pattern, owners in codeowners:
        for path in paths:
            if _codeowners_match(pattern, path):
                for owner in owners:
                    matched_handles.add(owner)

    if not matched_handles:
        return members

    # Existing reviewer members (preserving external contacts) + matched handles
    existing_handles = {m["handle"] for m in members if m.get("type") == "github"}
    final: list[dict] = [m for m in members if m.get("type") == "external"]
    for handle in matched_handles | existing_handles:
        final.append({"type": "github", "handle": handle})

    return final


def _load_codeowners() -> list[tuple[str, list[str]]]:
    """
    Read CODEOWNERS into a list of (pattern, owners) tuples.
    Handles only GitHub handles; team mentions like @org/team are kept
    as-is (caller can expand if needed).
    """
    for path in CODEOWNERS_PATHS:
        p = Path(path)
        if p.is_file():
            return _parse_codeowners(p.read_text())
    return []


def _parse_codeowners(content: str) -> list[tuple[str, list[str]]]:
    rules = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        pattern = parts[0]
        owners = [
            o.lstrip("@")
            for o in parts[1:]
            if o.startswith("@") and "/" not in o  # skip team mentions for now
        ]
        rules.append((pattern, owners))
    return rules


def _codeowners_match(pattern: str, path: str) -> bool:
    """
    CODEOWNERS pattern matching. Simplified — supports leading `/` for
    repo-rooted, trailing `/` for directories, `*` and `**` globs.
    """
    if pattern.startswith("/"):
        pattern = pattern[1:]
    elif "/" not in pattern:
        # No slash → match anywhere
        pattern = "**/" + pattern

    if pattern.endswith("/"):
        pattern = pattern + "**"

    regex = re.escape(pattern)
    regex = regex.replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
    return bool(re.match(regex + r"$", path))


def _member_key(member: dict) -> tuple:
    """Hashable key for a member."""
    if member.get("type") == "github":
        return ("github", member.get("handle"))
    if member.get("type") == "external":
        return ("external", member.get("name"), member.get("contact"))
    return ("unknown", str(member))
