"""
helpers/metrics package.

Compute reports from .workflow/metrics/events.jsonl and decision logs.

Three report types:

- cycle-time: time-in-stage per stage, per item type. Median / p90.
- gate-friction: override rate per gate; gate failure rate per stage.
- summary: high-level rollup (counts of items by stage, recent activity).

Reports respect the config's actor_attribution policy (roles / names /
hybrid). The redaction step is centralized so reports are uniform
regardless of source.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
import re

logger = logging.getLogger(__name__)

EVENTS_FILE = Path(".workflow/metrics/events.jsonl")
LIFECYCLE_ACTIVE = Path(".workflow/lifecycle/active")
LIFECYCLE_ARCHIVE = Path(".workflow/lifecycle/archive")


def compute_report(report_type: str, time_range: str = "30d", render_as: str = "markdown") -> str:
    """
    Compute a report. Top-level entry point used by `workflow-advisor report`.
    """
    cutoff = _parse_range(time_range)
    events = _load_events(since=cutoff)

    if report_type == "cycle-time":
        return _render_cycle_time(events, render_as)
    if report_type == "gate-friction":
        return _render_gate_friction(events, render_as)
    if report_type == "summary":
        return _render_summary(events, render_as)
    if report_type == "role-load":
        return _render_role_load(events, render_as)
    if report_type == "documentation":
        return _render_documentation(events, render_as)
    if report_type == "observability":
        return _render_observability(events, render_as)
    return f"Unknown report type: {report_type}"


def compute(
    config: dict,
    report_type: str,
    since: str | None = None,
    until: str | None = None,
    compare_to: str | None = None,
    render_as: str = "markdown",
) -> str:
    """CLI compatibility wrapper for report generation."""
    if compare_to:
        return compare_periods(report_type, compare_to, since or "30d", render_as)
    normalized = {
        "process": "summary",
        "cycle-times": "cycle-time",
        "before-after": "cycle-time",
    }.get(report_type, report_type)
    return compute_report(normalized, time_range=since or "30d", render_as=render_as)


def format_report(report: str, format: str = "text") -> str:
    """Reports are already rendered strings in the current implementation."""
    return report


def compare_periods(
    report_type: str, period_a: str, period_b: str, render_as: str = "markdown"
) -> str:
    """
    Before/after comparison for a metrics dimension. Useful after a
    config change to see if cycle time or gate friction shifted.
    """
    a_events = _load_events(since=_parse_range(period_a), until=_parse_range_end(period_a))
    b_events = _load_events(since=_parse_range(period_b), until=_parse_range_end(period_b))

    if report_type == "cycle-time":
        a_metrics = _cycle_time_metrics(a_events)
        b_metrics = _cycle_time_metrics(b_events)
    elif report_type == "gate-friction":
        a_metrics = _gate_friction_metrics(a_events)
        b_metrics = _gate_friction_metrics(b_events)
    else:
        return f"Compare not supported for report_type: {report_type}"

    return _render_comparison(a_metrics, b_metrics, period_a, period_b, render_as)


def _load_events(since: datetime | None = None, until: datetime | None = None) -> list[dict]:
    if not EVENTS_FILE.exists():
        return []
    out = []
    with EVENTS_FILE.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = _parse_iso(event.get("ts"))
            if since and ts and ts < since:
                continue
            if until and ts and ts > until:
                continue
            out.append(event)
    return out


def _cycle_time_metrics(events: list[dict]) -> dict:
    """Aggregate stage durations from events."""
    # In this minimal version, derive from lifecycle archives' stage_history
    durations: dict[str, list[float]] = defaultdict(list)
    for sidecar_file in LIFECYCLE_ARCHIVE.rglob("*.yml"):
        import yaml

        with sidecar_file.open() as f:
            sidecar = yaml.safe_load(f) or {}
        history = sidecar.get("stage_history") or []
        for i in range(len(history) - 1):
            stage = history[i].get("to")
            t0 = _parse_iso(history[i].get("at"))
            t1 = _parse_iso(history[i + 1].get("at"))
            if stage and t0 and t1:
                durations[stage].append((t1 - t0).total_seconds() / 86400.0)

    return {
        stage: {
            "count": len(d),
            "median_days": _median(d),
            "p90_days": _percentile(d, 90),
        }
        for stage, d in durations.items()
    }


def _gate_friction_metrics(events: list[dict]) -> dict:
    """Override rate per gate, gate failure rate per stage."""
    # Simplified: count event types
    summary = {
        "overrides_used": 0,
        "stage_skips": 0,
        "in_flight_conflicts": 0,
        "cascades_applied": 0,
    }
    for event in events:
        for k in summary:
            if k in event:
                v = event[k]
                if isinstance(v, (int, float)):
                    summary[k] += v
                elif v:
                    summary[k] += 1
    return summary


def _render_cycle_time(events: list[dict], render_as: str) -> str:
    metrics = _cycle_time_metrics(events)
    if render_as == "json":
        return json.dumps(metrics, indent=2)
    lines = ["## Cycle time", ""]
    for stage, m in sorted(metrics.items()):
        lines.append(
            f"- **{stage}**: median {m['median_days']:.1f}d, p90 {m['p90_days']:.1f}d (n={m['count']})"
        )
    return "\n".join(lines)


def _render_gate_friction(events: list[dict], render_as: str) -> str:
    metrics = _gate_friction_metrics(events)
    if render_as == "json":
        return json.dumps(metrics, indent=2)
    lines = ["## Gate friction", ""]
    for k, v in metrics.items():
        lines.append(f"- {k.replace('_', ' ')}: {v}")
    return "\n".join(lines)


def _render_summary(events: list[dict], render_as: str) -> str:
    by_stage = defaultdict(int)

    for sidecar in _load_sidecars(active_only=True):
        by_stage[sidecar.get("stage", "unknown")] += 1

    if render_as == "json":
        return json.dumps(
            {"active_by_stage": dict(by_stage), "events_in_window": len(events)}, indent=2
        )
    lines = ["## Workflow summary", "", "### Active items by stage", ""]
    for stage, count in sorted(by_stage.items()):
        lines.append(f"- {stage}: {count}")
    lines.extend(["", f"Events in window: {len(events)}"])
    return "\n".join(lines)


def _render_role_load(events: list[dict], render_as: str) -> str:
    sidecars = _load_sidecars(active_only=True)
    by_actor: dict[str, int] = defaultdict(int)
    by_stage: dict[str, int] = defaultdict(int)

    for sidecar in sidecars:
        by_stage[sidecar.get("stage", "unknown")] += 1
        for actor in _sidecar_actors(sidecar):
            by_actor[actor] += 1

    payload = {
        "active_items": len(sidecars),
        "events_in_window": len(events),
        "items_by_stage": dict(sorted(by_stage.items())),
        "items_by_actor": dict(sorted(by_actor.items())),
    }
    if render_as == "json":
        return json.dumps(payload, indent=2)
    lines = ["## Role load", "", f"Active items: {payload['active_items']}", ""]
    lines.append("### Items by actor")
    if by_actor:
        for actor, count in sorted(by_actor.items()):
            lines.append(f"- {actor}: {count}")
    else:
        lines.append("- No actors recorded on active sidecars.")
    lines.extend(["", "### Items by stage"])
    for stage, count in sorted(by_stage.items()):
        lines.append(f"- {stage}: {count}")
    lines.append(f"\nEvents in window: {len(events)}")
    return "\n".join(lines)


def _render_documentation(events: list[dict], render_as: str) -> str:
    sidecars = _load_sidecars(active_only=True)
    linked: dict[str, int] = defaultdict(int)
    items_with_links = 0

    for sidecar in sidecars:
        artifacts = sidecar.get("linked_artifacts") or {}
        if artifacts:
            items_with_links += 1
        for kind, values in artifacts.items():
            linked[kind] += len(values if isinstance(values, list) else [values])

    payload = {
        "active_items": len(sidecars),
        "items_with_linked_artifacts": items_with_links,
        "linked_artifacts": dict(sorted(linked.items())),
        "artifacts_observed": sum(int(e.get("artifacts_observed") or 0) for e in events),
        "artifacts_changed": sum(int(e.get("artifacts_changed") or 0) for e in events),
        "events_in_window": len(events),
    }
    if render_as == "json":
        return json.dumps(payload, indent=2)
    lines = [
        "## Documentation",
        "",
        f"Active items with linked artifacts: {items_with_links}/{len(sidecars)}",
        f"Artifacts observed in window: {payload['artifacts_observed']}",
        f"Artifacts changed in window: {payload['artifacts_changed']}",
        "",
        "### Linked artifacts",
    ]
    if linked:
        for kind, count in sorted(linked.items()):
            lines.append(f"- {kind}: {count}")
    else:
        lines.append("- No linked artifacts recorded on active sidecars.")
    lines.append(f"\nEvents in window: {len(events)}")
    return "\n".join(lines)


def _render_observability(events: list[dict], render_as: str) -> str:
    sidecars = _load_sidecars(active_only=True)
    metrics_enabled = 0
    baseline_captured = 0
    post_release_reviewed = 0

    for sidecar in sidecars:
        instrumentation = sidecar.get("instrumentation") or {}
        metrics = sidecar.get("metrics") or {}
        if instrumentation.get("metrics") or metrics:
            metrics_enabled += 1
        if metrics.get("baseline_captured"):
            baseline_captured += 1
        if metrics.get("post_release_reviewed"):
            post_release_reviewed += 1

    payload = {
        "active_items": len(sidecars),
        "events_in_window": len(events),
        "lifecycle_items_observed": sum(
            int(e.get("lifecycle_items_observed") or 0) for e in events
        ),
        "sidecars_written": sum(int(e.get("sidecars_written") or 0) for e in events),
        "lifecycle_updated": sum(int(e.get("lifecycle_updated") or 0) for e in events),
        "cascades_failed": sum(int(e.get("cascades_failed") or 0) for e in events),
        "metrics_enabled_items": metrics_enabled,
        "baseline_metrics_captured": baseline_captured,
        "post_release_metrics_reviewed": post_release_reviewed,
    }
    if render_as == "json":
        return json.dumps(payload, indent=2)
    return "\n".join(
        [
            "## Observability",
            "",
            f"Events in window: {payload['events_in_window']}",
            f"Lifecycle items observed: {payload['lifecycle_items_observed']}",
            f"Sidecars written: {payload['sidecars_written']}",
            f"Lifecycle updates: {payload['lifecycle_updated']}",
            f"Cascades failed: {payload['cascades_failed']}",
            "",
            "### Metrics gates",
            f"- Metrics enabled items: {metrics_enabled}",
            f"- Baseline metrics captured: {baseline_captured}",
            f"- Post-release metrics reviewed: {post_release_reviewed}",
        ]
    )


def _load_sidecars(active_only: bool = False) -> list[dict]:
    import yaml

    roots = [LIFECYCLE_ACTIVE] if active_only else [LIFECYCLE_ACTIVE, LIFECYCLE_ARCHIVE]
    sidecars = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.yml"):
            with path.open() as f:
                sidecars.append(yaml.safe_load(f) or {})
    return sidecars


def _sidecar_actors(sidecar: dict) -> set[str]:
    actors: set[str] = set()
    for key in ("owner", "assignee"):
        value = sidecar.get(key)
        if isinstance(value, str) and value:
            actors.add(value)

    for key in ("owners", "assignees", "reviewers"):
        value = sidecar.get(key)
        if isinstance(value, list):
            actors.update(str(v) for v in value if v)
        elif isinstance(value, dict):
            for nested in value.values():
                if isinstance(nested, list):
                    actors.update(str(v) for v in nested if v)
                elif nested:
                    actors.add(str(nested))
        elif value:
            actors.add(str(value))

    approvals = sidecar.get("approvals") or {}
    received = approvals.get("received")
    if isinstance(received, list):
        actors.update(str(v) for v in received if v)
    elif received:
        actors.add(str(received))

    return actors


def _render_comparison(a: dict, b: dict, period_a: str, period_b: str, render_as: str) -> str:
    if render_as == "json":
        return json.dumps({"a": a, "b": b}, indent=2)
    lines = [f"## Comparison: {period_a} vs {period_b}", ""]
    keys = sorted(set(a.keys()) | set(b.keys()))
    for k in keys:
        av = a.get(k)
        bv = b.get(k)
        lines.append(f"- {k}: {av} → {bv}")
    return "\n".join(lines)


def redact_actors(text: str, attribution: str = "roles") -> str:
    """Apply the actor_attribution policy to a rendered report."""
    if attribution == "names":
        return text
    if attribution == "hybrid":
        return text  # keep handles inline
    # roles: replace @handles with role placeholders (best effort)
    return re.sub(r"@\w[\w-]*", "{actor}", text)


def _parse_range(s: str) -> datetime | None:
    """Parse '30d', '1w', '6mo', etc. into a datetime cutoff."""
    if not s:
        return None
    m = re.match(r"^(\d+)(d|w|mo|y)$", s.strip())
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    days = {"d": 1, "w": 7, "mo": 30, "y": 365}[unit] * n
    return datetime.now(timezone.utc) - timedelta(days=days)


def _parse_range_end(s: str) -> datetime | None:
    """Period end is 'now' for current ranges."""
    return datetime.now(timezone.utc)


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def _percentile(values: list[float], p: int) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(len(s) * p / 100)))
    return s[k]
