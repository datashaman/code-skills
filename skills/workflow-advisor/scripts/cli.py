#!/usr/bin/env python3
"""
workflow-advisor CLI

Single entry point used by both reactive (CI) and interactive (local)
contexts. Subcommands map to the operations described in the skill:
reconcile, status, simulate, report, lifecycle, profiles, interview,
migrate, doctor.

In reactive mode (CI), the CLI is invoked by the GitHub Actions workflow
with the event payload path. It runs to completion, exits with a status
code, and prints structured output for the workflow's commit step.

In interactive mode (local), the CLI is typically not invoked directly
by users — it's invoked by the skill running in a Claude session. The
skill's role is to converse, infer, propose; the CLI's role is to
execute deterministic operations the skill has decided on.

The CLI is intentionally thin. Almost all logic lives in
scripts/helpers/. The CLI parses args, loads config, dispatches to a
handler, prints results.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

# Project-internal imports. These follow the layout described in
# SKILL.md "Helpers (Python)" section.
from helpers import config_io, provider_actions
from helpers import lifecycle as lifecycle_mod
from helpers import metrics as reports_mod
from helpers.reconcile import (
    apply as apply_phase,
)
from helpers.reconcile import (
    cascade as cascade_phase,
)
from helpers.reconcile import (
    checkpoint,
)
from helpers.reconcile import (
    classify as classify_phase,
)
from helpers.reconcile import (
    log as log_phase,
)
from helpers.reconcile import (
    observe as observe_phase,
)
from helpers.transport import normalize as transport_normalize

# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def cmd_reconcile(args: argparse.Namespace) -> int:
    """
    The core operation. Run the reconcile loop against an event payload
    or against current state (no event = full reconcile).

    Used by:
    - GitHub Actions workflow on every event trigger.
    - Local interactive use when the user wants to manually reconcile.
    - Other CLI subcommands as a building block.
    """
    config = config_io.load_from_path(_config_path())

    # Translate provider event to canonical event.
    event = transport_normalize.translate(
        provider=args.transport,
        event_name=args.event_name,
        event_action=args.event_action,
        payload_path=args.event_payload,
    )

    # Idempotency check.
    if event and _already_processed(event, config):
        print(json.dumps({"event": "reconcile.noop", "reason": "already_processed"}))
        return 0

    # Run the loop. Each phase is a pure function over its inputs.
    observed = observe_phase.run(config=config, event=event)
    classification = classify_phase.run(config=config, observed=observed)

    if args.dry_run:
        # Dry-run: produce proposed changes without writing.
        proposed = apply_phase.dry_run(
            config=config, observed=observed, classification=classification
        )
        cascade = cascade_phase.dry_run(
            config=config, observed=observed, classification=classification, proposed=proposed
        )
        _print_dry_run_summary(proposed, cascade)
        return 0

    # Real run: apply with checkpointing.
    with checkpoint.session(config=config, event=event) as session:
        applied = apply_phase.run(
            config=config, observed=observed, classification=classification, session=session
        )
        cascaded = cascade_phase.run(
            config=config,
            observed=observed,
            classification=classification,
            applied=applied,
            session=session,
        )
        log_phase.run(
            config=config,
            event=event,
            observed=observed,
            classification=classification,
            applied=applied,
            cascaded=cascaded,
            session=session,
        )
        # checkpoint.session commits on context exit if any writes occurred.

    provider_result = _handle_provider_actions_after_reconcile(config)
    print(
        json.dumps(
            {
                "event": "reconcile.completed",
                "commit": session.commit_sha,
                "provider_actions": provider_result,
            }
        )
    )
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """
    Render the current status of a PR, issue, or the repo as a whole.
    Read-only; never invokes reconcile.
    """
    config = config_io.load_from_path(_config_path())

    if args.target:
        item = _parse_target(args.target)  # e.g., "pr-127", "issue-89", "spec-0042"
        from helpers import status_render

        report = status_render.render_item(config=config, item=item, format=args.format)
    else:
        from helpers import status_render

        report = status_render.render_repo(config=config, format=args.format)

    print(report)
    return 0


def cmd_simulate(args: argparse.Namespace) -> int:
    """
    Dry-run the skill against a simulated event, replay a past event,
    or compare what config changes would have done historically.
    """
    from helpers import simulate as simulate_mod

    config = config_io.load_from_path(_config_path())

    if args.mode == "event":
        result = simulate_mod.simulate_event(
            config=config,
            event_name=args.event_name,
            **args.event_args,
        )
    elif args.mode == "replay":
        result = simulate_mod.replay_event(
            config=config,
            run_id=args.run_id,
            at_stage=args.at_stage,
        )
    elif args.mode == "config-diff":
        result = simulate_mod.config_diff(
            config=config,
            from_ref=args.from_ref,
            to_ref=args.to_ref,
            event_range=args.against,
        )
    else:
        raise ValueError(f"Unknown simulate mode: {args.mode}")

    print(simulate_mod.format_result(result, format=args.format))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """
    Generate process metrics reports. Pure functions over the lifecycle
    archive and metrics events log. Read-only.
    """
    config = config_io.load_from_path(_config_path())

    report = reports_mod.compute(
        config=config,
        report_type=args.report_type,
        since=args.since,
        until=args.until,
        compare_to=args.compare_to,
        render_as=args.render_as or config["observability_reports"]["reports"]["actor_attribution"],
    )

    print(reports_mod.format_report(report, format=args.format))
    return 0


def cmd_lifecycle(args: argparse.Namespace) -> int:
    """
    Show the composed lifecycle (stages, gates) for the active config.
    """
    config = config_io.load_from_path(_config_path())
    composed = lifecycle_mod.compose(config)

    if args.subcommand == "show":
        print(lifecycle_mod.render(composed, format=args.format))
    elif args.subcommand == "validate":
        issues = lifecycle_mod.validate(composed)
        if issues:
            for issue in issues:
                print(f"WARN: {issue}")
            return 1
        print("Lifecycle composition is valid.")
    return 0


def cmd_profiles(args: argparse.Namespace) -> int:
    """List enabled profiles and their contributions."""
    config = config_io.load_from_path(_config_path())

    if args.subcommand == "list":
        from helpers import profiles_mod

        for name, prof in profiles_mod.iter_profiles(config):
            status = "enabled" if prof.enabled else "disabled"
            print(f"{name}: {status}")
            if args.verbose and prof.enabled:
                print(f"  artifacts: {', '.join(prof.artifacts)}")
                print(f"  gates: {', '.join(prof.gates)}")
                print(f"  labels: {', '.join(prof.labels)}")
    elif args.subcommand == "enable" or args.subcommand == "disable":
        # These delegate to reconfigure flow; they don't write directly.
        from helpers import reconfigure

        diff = reconfigure.profile_change(
            config=config, profile=args.profile, enabled=(args.subcommand == "enable")
        )
        print(reconfigure.format_diff(diff))
        print()
        print("Run with --apply to commit, or modify .workflow/config.yml manually.")
        if args.apply:
            reconfigure.apply(diff)
    return 0


def cmd_interview(args: argparse.Namespace) -> int:
    """
    Run the progressive interview. Typically not invoked directly — the
    skill's interactive layer drives the interview via Claude. This
    command is exposed for testing the question bank deterministically.
    """
    from helpers import interview as interview_mod

    if args.profile:
        questions = interview_mod.questions_for_profile(args.profile)
    elif args.config_key:
        questions = interview_mod.questions_for_key(args.config_key)
    else:
        config = config_io.load_or_default(_config_path())
        questions = interview_mod.next_questions(config)

    print(json.dumps(questions, indent=2))
    return 0


def cmd_migrate(args: argparse.Namespace) -> int:
    """
    Run schema migrations. Comparing .workflow/schema_version against
    the skill's current schema, run pending migrations.
    """
    from helpers.migrations import runner

    workflow_dir = Path(".workflow")
    current = runner.get_schema_version(workflow_dir)
    target = runner.skill_current_schema_version()

    if current >= target:
        print(f"Schema up to date (version {current}).")
        return 0

    if args.dry_run:
        plan = runner.plan(current, target)
        print(f"Would migrate from version {current} to {target}:")
        for migration in plan:
            print(f"  {migration.id}: {migration.description}")
        return 0

    runner.run_migrations(workflow_dir, from_version=current, to_version=target, args=args)
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """
    Diagnose folder/repo state. Useful when something has gone wrong
    and the user wants the skill to self-check.
    """
    from helpers import doctor as doctor_mod

    findings = doctor_mod.check(_config_path())

    if not findings:
        print("All checks passed.")
        return 0

    for finding in findings:
        severity = finding.get("severity", "warning")
        symbol = "x" if severity == "error" else "!"
        print(f"{symbol} {finding.get('message', '')}")
        if finding.get("fix_command"):
            print(f"  Suggested fix: {finding['fix_command']}")
    return 1 if any(f.get("severity") == "error" for f in findings) else 0


def cmd_provider_actions(args: argparse.Namespace) -> int:
    """List or flush queued provider actions."""
    if args.subcommand == "list":
        records = provider_actions.list_pending()
        if args.format == "json":
            print(json.dumps(records, indent=2))
        else:
            if not records:
                print("No pending provider actions.")
            for idx, record in enumerate(records, 1):
                print(
                    f"{idx}. {record.get('action')} "
                    f"status={record.get('status', 'pending')} "
                    f"reason={record.get('reason', '')}"
                )
        return 0

    if args.subcommand == "flush":
        result = provider_actions.flush_queue(dry_run=not args.apply)
        if args.format == "json":
            print(json.dumps(result, indent=2))
        else:
            mode = "dry-run" if result["dry_run"] else "apply"
            print(
                f"Provider actions {mode}: "
                f"pending={result['pending']} "
                f"applied={result['applied']} "
                f"failed={result['failed']} "
                f"remaining={result['remaining']}"
            )
            for item in result["results"]:
                status = "ok" if item.get("ok") else "failed"
                print(f"- {item.get('action')}: {status}")
                for command in item.get("commands", []):
                    print(f"  $ {' '.join(command)}")
                if item.get("error"):
                    print(f"  error: {item['error']}")
        return 1 if result["failed"] else 0

    raise ValueError(f"Unknown provider-actions subcommand: {args.subcommand}")


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="workflow-advisor",
        description="Team workflow orchestrator for SDD-versant repos.",
    )
    p.add_argument("--config", help="Path to .workflow/config.yml (default: auto-detect)")
    sub = p.add_subparsers(dest="command", required=True)

    # reconcile
    rec = sub.add_parser("reconcile", help="Run the reconcile loop")
    rec.add_argument("--event-name", default=None)
    rec.add_argument("--event-action", default=None)
    rec.add_argument("--event-payload", default=None, help="Path to event payload JSON file")
    rec.add_argument(
        "--transport",
        default="github_actions",
        choices=[
            "github_actions",
            "gh_forward",
            "self_hosted_webhook",
            "polling",
            "on_demand_only",
        ],
    )
    rec.add_argument("--dry-run", action="store_true")
    rec.set_defaults(func=cmd_reconcile)

    # status
    status = sub.add_parser("status", help="Show status of a PR/issue/spec or repo")
    status.add_argument(
        "target",
        nargs="?",
        default=None,
        help="e.g., pr-127, issue-89, spec-0042; omit for repo-wide",
    )
    status.add_argument("--format", choices=["text", "markdown", "json"], default="text")
    status.set_defaults(func=cmd_status)

    # simulate
    sim = sub.add_parser("simulate", help="Dry-run events and config changes")
    sim_sub = sim.add_subparsers(dest="mode", required=True)
    sim_event = sim_sub.add_parser("event")
    sim_event.add_argument("event_name")
    sim_event.add_argument("--event-args", type=json.loads, default={})
    sim_replay = sim_sub.add_parser("replay")
    sim_replay.add_argument("run_id")
    sim_replay.add_argument("--at-stage")
    sim_diff = sim_sub.add_parser("config-diff")
    sim_diff.add_argument("--from-ref", default="HEAD")
    sim_diff.add_argument("--to-ref", default=None)
    sim_diff.add_argument("--against", default="last-30-days-events")
    sim.add_argument("--format", choices=["text", "json"], default="text")
    sim.set_defaults(func=cmd_simulate)

    # report
    rep = sub.add_parser("report", help="Generate process metrics report")
    rep.add_argument(
        "report_type",
        choices=[
            "process",
            "cycle-times",
            "gate-friction",
            "role-load",
            "documentation",
            "observability",
            "before-after",
        ],
    )
    rep.add_argument("--since", default=None)
    rep.add_argument("--until", default=None)
    rep.add_argument("--compare-to", default=None)
    rep.add_argument("--render-as", choices=["roles", "names", "hybrid"], default=None)
    rep.add_argument("--format", choices=["text", "markdown", "json"], default="text")
    rep.set_defaults(func=cmd_report)

    # lifecycle
    lc = sub.add_parser("lifecycle", help="Inspect lifecycle composition")
    lc_sub = lc.add_subparsers(dest="subcommand", required=True)
    lc_show = lc_sub.add_parser("show")
    lc_show.add_argument("--format", choices=["text", "mermaid"], default="text")
    lc_sub.add_parser("validate")
    lc.set_defaults(func=cmd_lifecycle)

    # profiles
    pr = sub.add_parser("profiles", help="Manage profiles")
    pr_sub = pr.add_subparsers(dest="subcommand", required=True)
    pr_list = pr_sub.add_parser("list")
    pr_list.add_argument("-v", "--verbose", action="store_true")
    pr_enable = pr_sub.add_parser("enable")
    pr_enable.add_argument("profile")
    pr_enable.add_argument("--apply", action="store_true")
    pr_disable = pr_sub.add_parser("disable")
    pr_disable.add_argument("profile")
    pr_disable.add_argument("--apply", action="store_true")
    pr.set_defaults(func=cmd_profiles)

    # interview
    iv = sub.add_parser("interview", help="Inspect or run the question bank")
    iv.add_argument("--profile", default=None)
    iv.add_argument("--config-key", default=None)
    iv.set_defaults(func=cmd_interview)

    # migrate
    mig = sub.add_parser("migrate", help="Apply schema migrations")
    mig.add_argument("--dry-run", action="store_true")
    mig.set_defaults(func=cmd_migrate)

    # doctor
    doc = sub.add_parser("doctor", help="Diagnose .workflow/ folder state")
    doc.set_defaults(func=cmd_doctor)

    # provider-actions
    pa = sub.add_parser("provider-actions", help="Inspect or flush queued provider actions")
    pa_sub = pa.add_subparsers(dest="subcommand", required=True)
    pa_list = pa_sub.add_parser("list")
    pa_list.add_argument("--format", choices=["text", "json"], default="text")
    pa_flush = pa_sub.add_parser("flush")
    pa_flush.add_argument("--apply", action="store_true", help="Execute actions instead of dry-run")
    pa_flush.add_argument("--format", choices=["text", "json"], default="text")
    pa.set_defaults(func=cmd_provider_actions)

    return p


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _config_path() -> Path:
    """Resolve the config path, walking up from CWD if needed."""
    parser_config = getattr(build_parser, "_config_override", None)
    if parser_config:
        return Path(parser_config)
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        p = parent / ".workflow" / "config.yml"
        if p.exists():
            return p
    raise FileNotFoundError(
        ".workflow/config.yml not found. Run bootstrap first or check your working directory."
    )


def _already_processed(event: Any, config: dict) -> bool:
    """Check the idempotency ledger for this event ID."""
    state_path = _config_path().parent / "state" / "processed_events.yml"
    if not state_path.exists():
        return False
    from helpers import state_io

    processed = state_io.load_processed_events(state_path)
    event_id = event.get("id") or event.get("provider_meta", {}).get("delivery_id")
    return bool(event_id and event_id in processed)


def _parse_target(target: str) -> dict:
    """Parse 'pr-127', 'issue-89', 'spec-0042' style targets."""
    if "-" not in target:
        raise ValueError(f"Invalid target: {target}")
    kind, _, ident = target.partition("-")
    return {"kind": kind, "id": ident}


def _print_dry_run_summary(proposed: dict, cascade: dict) -> None:
    """Pretty-print a dry-run summary for the interactive case."""
    print("=== Proposed changes (dry-run) ===")
    if not proposed and not cascade:
        print("(no changes)")
        return
    if proposed:
        print("\nApply phase:")
        for change in proposed.get("changes", []):
            print(f"  {change['op']} {change['path']}: {change.get('summary', '')}")
    if cascade:
        print("\nCascade phase:")
        for effect in cascade.get("effects", []):
            print(f"  {effect['target']}: {effect['action']} ({effect.get('reason', '')})")


def _handle_provider_actions_after_reconcile(config: dict) -> dict:
    """
    Apply provider-action policy after folder state has been reconciled.

    Modes:
      queue   - leave actions pending; report count.
      dry_run - preview flush commands; leave actions pending.
      apply   - execute via gh and archive successes/failures.
    """
    mode = config.get("provider_actions", {}).get("mode", "queue")
    pending = provider_actions.list_pending()
    if mode == "queue":
        return {"mode": mode, "pending": len(pending)}
    if mode == "dry_run":
        result = provider_actions.flush_queue(dry_run=True)
        return {
            "mode": mode,
            "pending": result["pending"],
            "remaining": result["remaining"],
            "failed": result["failed"],
        }
    if mode == "apply":
        result = provider_actions.flush_queue(dry_run=False)
        return {
            "mode": mode,
            "pending": result["pending"],
            "applied": result["applied"],
            "failed": result["failed"],
            "remaining": result["remaining"],
        }
    return {"mode": mode, "pending": len(pending), "warning": "unknown provider_actions.mode"}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    build_parser._config_override = args.config
    try:
        return args.func(args)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        # Top-level exceptions are bugs; print stack in CI for diagnosis.
        import traceback

        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
