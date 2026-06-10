"""Core library logic: discover silos, build the dated log, scan repos for leaks.

No secret values are ever read or printed — `doctor` checks git-tracking and
.gitignore coverage only, by filename.
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

CLAUDE = Path.home() / ".claude"

_PREFIX_RE = re.compile(r"^(feedback|project|reference|user|session|decision|soul)[_-]", re.IGNORECASE)
_PRUNE_DIRS = {"node_modules", ".git", ".venv", "venv", "__pycache__", "dist", "build", ".next", "target", ".cache"}
_ENV_EXEMPT = {".env.example", ".env.sample", ".env.template", ".env.dist"}


def is_env_file(name: str) -> bool:
    """True for real dotenv files (.env, .env.local, prod.env) — not .envrc/.environment/templates."""
    low = name.lower()
    if low in _ENV_EXEMPT:
        return False
    return low == ".env" or low.startswith(".env.") or low.endswith(".env")


@dataclass
class Silo:
    """One Claude memory store, keyed by the working dir it was created from."""

    name: str
    path: Path
    kind: str  # "project" | "agent"
    files: list[Path] = field(default_factory=list)


def discover_silos() -> list[Silo]:
    """Find every project and per-agent memory silo under ~/.claude."""
    silos: list[Silo] = []
    projects = CLAUDE / "projects"
    if projects.is_dir():
        for d in sorted(projects.iterdir()):
            mem = d / "memory"
            if mem.is_dir():
                silos.append(Silo(d.name, mem, "project", sorted(mem.glob("*.md"))))
    agents = CLAUDE / "agent-memory"
    if agents.is_dir():
        for d in sorted(agents.iterdir()):
            if d.is_dir():
                silos.append(Silo(d.name, d, "agent", sorted(d.glob("*.md"))))
    return silos


def categorize(stem: str) -> tuple[str, str]:
    """Split a filename stem into (category, human title)."""
    match = _PREFIX_RE.match(stem)
    category = match.group(1).lower() if match else "note"
    title = _PREFIX_RE.sub("", stem).replace("_", " ").replace("-", " ").strip()
    return category, title


@dataclass
class LogRow:
    date: datetime
    silo: str
    category: str
    title: str


def build_log(silos: list[Silo]) -> list[LogRow]:
    """Captain's Log: every memory file as a dated row, oldest first (UTC)."""
    rows = [
        LogRow(
            datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc),
            s.name, *categorize(f.stem),
        )
        for s in silos
        for f in s.files
    ]
    rows.sort(key=lambda r: r.date)
    return rows


def _git(repo: Path, *args: str) -> Optional[list[str]]:
    """Run git; return stdout lines, or None if git is missing or the call failed.

    Returning None (not []) lets callers distinguish "no matches" from "git errored",
    so a failed call can never be mistaken for a clean result.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, check=False,
        )
    except (FileNotFoundError, OSError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.splitlines()


def _gitignore_covers_env(path: Path) -> bool:
    """True only if .gitignore has an active (non-comment, non-negated) rule mentioning .env."""
    if not path.is_file():
        return False
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        if ".env" in line:
            return True
    return False


def _find_env_files(repo: Path) -> list[Path]:
    """Locate real .env files (skips templates and vendored dirs)."""
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [d for d in dirnames if d not in _PRUNE_DIRS]
        for name in filenames:
            if is_env_file(name):
                found.append(Path(dirpath) / name)
    return found


def find_git_repos(root: Path) -> list[Path]:
    """Find every git repo at or under root, including nested repos."""
    repos: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _PRUNE_DIRS]
        if ".git" in dirnames or ".git" in filenames:  # .git is a dir, or a file for worktrees/submodules
            repos.append(Path(dirpath))
    return repos


@dataclass
class RepoHealth:
    name: str
    verdict: str
    env_files: list[str]
    gitignore_covers_env: bool
    tracked_env: list[str]
    ever_committed: bool


def doctor_env(root: Path) -> list[RepoHealth]:
    """Scan each git repo at/under `root` (recursively) for the real leak: a tracked .env."""
    out: list[RepoHealth] = []
    for repo in sorted(find_git_repos(root)):
        present = [str(p.relative_to(repo)) for p in _find_env_files(repo)]
        covered = _gitignore_covers_env(repo / ".gitignore")
        listed = _git(repo, "ls-files")
        if listed is None:
            out.append(RepoHealth(repo.name, "git error (could not read)", present, covered, [], False))
            continue
        tracked = [t for t in listed if is_env_file(os.path.basename(t))]
        history = _git(repo, "log", "--all", "--oneline", "--", "*.env", ".env")
        ever = bool(history)
        if tracked:
            verdict = "LEAK: .env tracked"
        elif ever:
            verdict = "WAS committed (history)"
        elif present and not covered:
            verdict = "AT RISK: env present, not ignored"
        else:
            verdict = "ok"
        out.append(RepoHealth(repo.name, verdict, present, covered, tracked, ever))
    return out
