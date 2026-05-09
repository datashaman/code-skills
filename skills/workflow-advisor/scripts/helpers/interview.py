"""
helpers/interview.py

Progressive interview runner. Demand-driven from the question bank in
references/interview.md.

Most of the interview is conversational — the skill (Claude) frames the
questions, listens for answers, infers from repo signals where possible.
This helper provides the deterministic scaffolding:

- Resume across sessions via `.workflow/.interview_in_progress.yml`.
- Track which fields have been answered.
- Persist partial answers without polluting `config.yml`.
- Provide the question bank as structured data for Claude to consult.

The actual question presentation and answer collection happens in the
chat session; this helper records the answers.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

IN_PROGRESS_FILE = Path(".workflow/.interview_in_progress.yml")


# Question bank — structured form of references/interview.md.
# Each question has:
#   key: the dotted config path
#   question: prompt text
#   options: list of choices (or None for free-form)
#   inference_hint: text to surface alongside (or None)
#   required_for: list of intents that need this answer
QUESTION_BANK: list[dict] = [
    {
        "key": "profiles",
        "question": "Which profiles do you want active?",
        "options": [
            "spec-driven (recommended)",
            "testability (recommended)",
            "observability (recommended)",
            "documentation",
            "security",
            "accessibility",
            "compliance",
        ],
        "multi_select": True,
        "required_for": ["bootstrap"],
    },
    {
        "key": "repo.branch_model",
        "question": "Which branch model do you use?",
        "options": ["trunk-based", "github-flow", "gitflow", "release-branches"],
        "required_for": ["bootstrap"],
    },
    {
        "key": "review_policy.min_approvals",
        "question": "How many reviewer approvals are required to merge?",
        "options": ["1", "2", "3 or more"],
        "required_for": ["bootstrap"],
    },
    {
        "key": "review_policy.codeowners_required",
        "question": "Should affected areas require CODEOWNERS approval?",
        "options": ["yes", "no"],
        "required_for": ["bootstrap"],
        "inference_hint": "We detect a CODEOWNERS file; defaulting to yes if so.",
    },
    {
        "key": "linkage.spec",
        "question": "How should PRs reference their spec?",
        "options": [
            "PR body line (recommended)",
            "commit trailer",
            "label",
        ],
        "required_for": ["spec-driven"],
    },
    {
        "key": "transport.mode",
        "question": "How should the skill receive events from GitHub?",
        "options": [
            "GitHub Actions (recommended)",
            "gh webhook forward (local dev)",
            "self-hosted webhook",
            "polling",
            "on-demand only",
        ],
        "required_for": ["bootstrap"],
    },
]


def get_questions_for_intent(intent: str, current_config: dict) -> list[dict]:
    """
    Return the questions that need answering for the given intent,
    filtering out fields that are already answered in current_config.
    """
    out: list[dict] = []
    for q in QUESTION_BANK:
        if intent not in q.get("required_for", []):
            continue
        if _has_answer(q["key"], current_config):
            continue
        out.append(q)
    return out


def questions_for_profile(profile: str) -> list[dict]:
    """Return questions relevant to a profile."""
    return [
        q
        for q in QUESTION_BANK
        if profile in q.get("required_for", []) or q.get("key", "").startswith(f"{profile}.")
    ]


def questions_for_key(config_key: str) -> list[dict]:
    """Return questions that write a specific config key."""
    return [q for q in QUESTION_BANK if q.get("key") == config_key]


def next_questions(current_config: dict, intent: str = "bootstrap") -> list[dict]:
    """Return the next unanswered questions for the default bootstrap intent."""
    return get_questions_for_intent(intent, current_config)


def save_progress(answers: dict) -> None:
    """Persist partial answers to the in-progress file."""
    IN_PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "answers": answers,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
    with IN_PROGRESS_FILE.open("w") as f:
        yaml.dump(record, f, sort_keys=False)


def load_progress() -> dict:
    """Load in-progress answers, or return empty dict if no resume."""
    if not IN_PROGRESS_FILE.exists():
        return {}
    with IN_PROGRESS_FILE.open() as f:
        record = yaml.safe_load(f) or {}
    return record.get("answers", {})


def commit_answers_to_config(answers: dict) -> None:
    """
    Merge interview answers into config.yml and remove the in-progress
    file. Called once the interview is complete.
    """
    from . import config_io

    try:
        current = config_io.load()
    except config_io.ConfigError:
        current = _default_config()

    for key, value in answers.items():
        _set_dotted_key(current, key, value)

    config_io.save(current)
    if IN_PROGRESS_FILE.exists():
        IN_PROGRESS_FILE.unlink()


def run_interview(
    scope: str = "bootstrap", target: str | None = None, resume: bool = False
) -> None:
    """
    CLI entry point. The actual conversational flow happens in the chat
    session; this is the deterministic harness.
    """
    answers = load_progress() if resume else {}
    questions = get_questions_for_intent(scope, _answers_as_config(answers))

    if not questions:
        print("No questions needed for this intent — config is complete.")
        return

    print(f"Interview: {scope}. {len(questions)} questions to ask.")
    for q in questions:
        print(f"\n  Q: {q['question']}")
        if q.get("inference_hint"):
            print(f"  Hint: {q['inference_hint']}")
        if q.get("options"):
            for i, opt in enumerate(q["options"], 1):
                print(f"    {i}. {opt}")
        # In a real interactive run, we'd wait for input. The chat
        # session handles that; this CLI path is mostly for inspection.
    print(
        "\n(In conversation, the skill collects answers and calls "
        "commit_answers_to_config when complete.)"
    )


def _has_answer(key: str, config: dict) -> bool:
    return _get_dotted_key(config, key) is not None


def _get_dotted_key(d: dict, key: str) -> Any:
    value: Any = d
    for part in key.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value


def _set_dotted_key(d: dict, key: str, value: Any) -> None:
    parts = key.split(".")
    target = d
    for part in parts[:-1]:
        target = target.setdefault(part, {})
    target[parts[-1]] = value


def _answers_as_config(answers: dict) -> dict:
    """Build a partial config dict from flat answer keys."""
    config: dict = {}
    for key, value in answers.items():
        _set_dotted_key(config, key, value)
    return config


def _default_config() -> dict:
    """Minimal scaffold used when no config exists yet."""
    return {
        "schema_version": 1,
        "repo": {"provider": "github"},
        "profiles": {},
        "lifecycle": {"composition": {}},
        "roles": {},
        "transport": {},
    }
