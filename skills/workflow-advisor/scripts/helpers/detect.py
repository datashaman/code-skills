"""
helpers/detect.py

Repo inference for bootstrap. Reads git history, file structure, and
provider state to make educated guesses about:

- Provider (from .git/config remote URL).
- Branch model (trunk-based, github-flow, gitflow, release-branches).
- Default branch.
- Languages and frameworks (from manifests).
- Existing CI (.github/workflows/, .gitlab-ci.yml, etc.).
- Existing artifacts (docs/specs/, docs/adr/, etc.).
- Existing labels (provider API).
- CODEOWNERS.
- Recent contributors and their roles (from git shortlog).

Inference is lossy. The bootstrap interview confirms or corrects
inferences before writing the config.
"""

from __future__ import annotations

from collections import Counter
import logging
from pathlib import Path
import re
import subprocess

logger = logging.getLogger(__name__)


def detect_all() -> dict:
    """Run all detection steps and return a combined report."""
    return {
        "provider": detect_provider(),
        "default_branch": detect_default_branch(),
        "branch_model": detect_branch_model(),
        "languages": detect_languages(),
        "ci_configs": detect_ci_configs(),
        "artifacts": detect_existing_artifacts(),
        "codeowners": detect_codeowners(),
        "contributors": detect_contributors(),
    }


def detect_provider() -> dict:
    """Detect the Git provider from the remote URL."""
    try:
        url = subprocess.check_output(
            ["git", "config", "--get", "remote.origin.url"], text=True
        ).strip()
    except subprocess.CalledProcessError:
        return {"provider": "unknown", "url": None}

    if "github.com" in url:
        # Parse owner/repo from either ssh or https URL.
        match = re.search(r"github\.com[:/]([^/]+)/([^/.]+)", url)
        if match:
            return {
                "provider": "github",
                "url": url,
                "identifier": f"{match.group(1)}/{match.group(2)}",
            }
    elif "gitlab.com" in url:
        return {"provider": "gitlab", "url": url}
    elif "bitbucket.org" in url:
        return {"provider": "bitbucket", "url": url}
    return {"provider": "unknown", "url": url}


def detect_default_branch() -> str:
    """Detect the default branch via git symbolic-ref or fallback."""
    try:
        ref = subprocess.check_output(
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD"], text=True
        ).strip()
        return ref.split("/")[-1]
    except subprocess.CalledProcessError:
        # Fallback: check common defaults
        for candidate in ("main", "master", "trunk"):
            if branch_exists(candidate):
                return candidate
        return "main"


def branch_exists(name: str) -> bool:
    return (
        subprocess.call(
            ["git", "show-ref", "--verify", f"refs/remotes/origin/{name}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        == 0
    )


def detect_branch_model() -> str:
    """
    Detect branch model by analyzing branch names and merge patterns.
    Heuristics:
    - Long-lived develop or release branches → gitflow or release-branches.
    - Only main + short-lived feature branches → trunk-based or github-flow.
    """
    branches = subprocess.check_output(["git", "branch", "-r"], text=True).split("\n")
    branches = [b.strip() for b in branches if b.strip() and "->" not in b]

    has_develop = any("origin/develop" in b for b in branches)
    has_release = any("origin/release-" in b or "origin/release/" in b for b in branches)

    if has_develop and has_release:
        return "gitflow"
    if has_release:
        return "release-branches"
    if has_develop:
        return "gitflow"
    return "trunk-based"


def detect_languages() -> dict:
    """Detect languages by file extensions and manifests."""
    extensions: Counter = Counter()
    manifests: list[str] = []

    for path in Path(".").rglob("*"):
        if any(p.startswith(".") for p in path.parts):
            continue
        if "node_modules" in path.parts or "vendor" in path.parts:
            continue
        if path.is_file():
            extensions[path.suffix] += 1
            if path.name in (
                "package.json",
                "Cargo.toml",
                "pyproject.toml",
                "setup.py",
                "go.mod",
                "Gemfile",
                "pom.xml",
                "build.gradle",
                "composer.json",
            ):
                manifests.append(str(path))

    return {
        "top_extensions": dict(extensions.most_common(10)),
        "manifests": manifests,
    }


def detect_ci_configs() -> list[str]:
    """Find existing CI configs."""
    found = []
    workflows = Path(".github/workflows")
    if workflows.is_dir():
        found.extend(str(p) for p in workflows.glob("*.yml"))
        found.extend(str(p) for p in workflows.glob("*.yaml"))
    for name in (
        ".gitlab-ci.yml",
        ".circleci/config.yml",
        "Jenkinsfile",
        ".travis.yml",
        "azure-pipelines.yml",
    ):
        if Path(name).exists():
            found.append(name)
    return found


def detect_existing_artifacts() -> dict:
    """Look for spec-like or ADR-like documents."""
    result: dict[str, list[str]] = {
        "specs": [],
        "adrs": [],
        "runbooks": [],
        "rfcs": [],
    }

    docs = Path("docs")
    if not docs.is_dir():
        return result

    spec_pattern = re.compile(r"\d{3,4}.*\.(md|markdown)$")
    adr_pattern = re.compile(r"(adr|decision)[-_]?\d", re.IGNORECASE)
    runbook_pattern = re.compile(r"runbook", re.IGNORECASE)
    rfc_pattern = re.compile(r"rfc", re.IGNORECASE)

    for path in docs.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        if adr_pattern.search(name):
            result["adrs"].append(str(path))
        elif runbook_pattern.search(name):
            result["runbooks"].append(str(path))
        elif rfc_pattern.search(name):
            result["rfcs"].append(str(path))
        elif spec_pattern.match(name):
            result["specs"].append(str(path))

    return result


def detect_codeowners() -> dict:
    """Read CODEOWNERS if present."""
    for path in (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS"):
        p = Path(path)
        if p.is_file():
            return {"path": str(p), "content": p.read_text()}
    return {"path": None}


def detect_contributors(window_months: int = 6) -> list[dict]:
    """Detect recent contributors with rough role inference."""
    try:
        output = subprocess.check_output(
            ["git", "shortlog", "-sne", f"--since={window_months}.months"],
            text=True,
        )
    except subprocess.CalledProcessError:
        return []

    contributors = []
    for line in output.strip().split("\n"):
        if not line:
            continue
        match = re.match(r"\s*(\d+)\s+(.+?)\s+<(.+?)>", line)
        if match:
            commits, name, email = match.groups()
            contributors.append(
                {
                    "name": name,
                    "email": email,
                    "commits": int(commits),
                }
            )

    # Top contributor is a candidate for architect/tech_lead.
    # Active reviewers (high reviews/commits ratio) need provider API
    # to detect — left to the bootstrap caller.
    return contributors


def infer_role_candidates(contributors: list[dict]) -> dict:
    """
    Suggest role candidates based on git history alone. The bootstrap
    interview confirms or corrects.
    """
    if not contributors:
        return {}

    top = contributors[0]
    return {
        "architect": [{"type": "github", "candidate_name": top["name"]}],
        "tech_lead": [{"type": "github", "candidate_name": top["name"]}],
        "maintainer": [{"type": "github", "candidate_name": top["name"]}],
        # reviewer / sre / security / accessibility_lead / audience roles
        # have no signal in git alone.
    }
