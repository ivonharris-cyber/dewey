"""Core library logic: discover silos, build the dated log, scan repos for leaks,
and shelve memory into a browsable Markdown library.

No secret values are ever read or printed — `doctor` checks git-tracking and
.gitignore coverage only, and `sync` skips credential-named files entirely.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

CLAUDE = Path.home() / ".claude"

_PREFIX_RE = re.compile(r"^(feedback|project|reference|user|session|decision|soul)[_-]", re.IGNORECASE)
_PRUNE_DIRS = {"node_modules", ".git", ".venv", "venv", "__pycache__", "dist", "build", ".next", "target", ".cache"}
_ENV_EXEMPT = {".env.example", ".env.sample", ".env.template", ".env.dist"}
_SENSITIVE_RE = re.compile(
    r"(api[-_]?key|credential|secret|token|password|[-_]login|keystore|\.key$|\.env)",
    re.IGNORECASE,
)

_CLASS_BY_CATEGORY = {
    "feedback": "100-people",
    "user": "100-people",
    "soul": "300-agents",
    "decision": "300-agents",
    "project": "400-projects",
    "reference": "500-reference",
    "session": "900-sessions",
    "note": "000-meta",
}


def is_env_file(name: str) -> bool:
    """True for real dotenv files (.env, .env.local, prod.env) — not .envrc/.environment/templates."""
    low = name.lower()
    if low in _ENV_EXEMPT:
        return False
    return low == ".env" or low.startswith(".env.") or low.endswith(".env")


def is_sensitive(name: str) -> bool:
    """True for files whose name suggests they hold credentials — never auto-copied by sync."""
    return bool(_SENSITIVE_RE.search(name))


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


# --- sync: shelve memory into a browsable Markdown library --------------------


@dataclass
class SyncPlan:
    copied: list[tuple[Path, Path]]
    skipped_sensitive: list[Path]


def plan_sync(silos: list[Silo], target: Path) -> SyncPlan:
    """Plan a library mirror: silo files -> target/<class>/<silo>/<file>, skipping secrets."""
    target = Path(target)
    copied: list[tuple[Path, Path]] = []
    skipped: list[Path] = []
    for silo in silos:
        for f in silo.files:
            if is_sensitive(f.name):
                skipped.append(f)
                continue
            category, _ = categorize(f.stem)
            klass = _CLASS_BY_CATEGORY.get(category, "000-meta")
            copied.append((f, target / klass / silo.name / f.name))
    return SyncPlan(copied, skipped)


def apply_sync(plan: SyncPlan, target: Path) -> None:
    """Write the planned library, then an index of what was shelved."""
    target = Path(target)
    for src, dest in plan.copied:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    lines = ["# Dewey Library — index", ""]
    lines += [f"- `{dest.relative_to(target)}`" for _, dest in sorted(plan.copied, key=lambda c: str(c[1]))]
    if plan.skipped_sensitive:
        lines += ["", "## Skipped (sensitive — never auto-copied)", ""]
        lines += [f"- {p.name}" for p in plan.skipped_sensitive]
    (target / "LIBRARY-INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
