"""Core library logic: discover silos, build the dated log, scan repos for leaks,
and shelve / de-duplicate memory.

No secret values are ever read or printed — `doctor` checks git-tracking and
.gitignore coverage only, and `sync` skips credential-named files entirely.
"""
from __future__ import annotations

import hashlib
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
    r"(api[-_]?key|credential|secret|token|password|(?:^|[-_])login|keystore|\.key$)",
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
    """True for files whose name suggests credentials — never copied by sync."""
    return is_env_file(name) or bool(_SENSITIVE_RE.search(name))


def portable(path: Path) -> str:
    """Render a path under ~/.claude as a portable, username-free pointer."""
    try:
        return "~/.claude/" + path.relative_to(CLAUDE).as_posix()
    except ValueError:
        return str(path)


@dataclass
class Silo:
    """One Claude memory store, keyed by the working dir it was created from."""

    name: str
    path: Path
    kind: str  # "project" | "agent"
    files: list[Path] = field(default_factory=list)


def _md_files(directory: Path) -> list[Path]:
    """All *.md in a directory, skipping symlinks (which could point outside the trusted area)."""
    return sorted(p for p in directory.glob("*.md") if not p.is_symlink())


def discover_silos() -> list[Silo]:
    """Find every project and per-agent memory silo under ~/.claude."""
    silos: list[Silo] = []
    projects = CLAUDE / "projects"
    if projects.is_dir():
        for d in sorted(projects.iterdir()):
            mem = d / "memory"
            if mem.is_dir():
                silos.append(Silo(d.name, mem, "project", _md_files(mem)))
    agents = CLAUDE / "agent-memory"
    if agents.is_dir():
        for d in sorted(agents.iterdir()):
            if d.is_dir():
                silos.append(Silo(d.name, d, "agent", _md_files(d)))
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
    """Every memory file as a dated row, oldest first (UTC)."""
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
    """Run git; return stdout lines, or None if git is missing or the call failed."""
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
        if ".git" in dirnames or ".git" in filenames:
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


# --- sync: copy memory into a browsable Markdown library ----------------------


@dataclass
class SyncPlan:
    copied: list[tuple[Path, Path]]
    skipped_sensitive: list[Path]


def plan_sync(silos: list[Silo], target: Path) -> SyncPlan:
    """Plan a library mirror: files -> target/<class>/<kind>-<silo>/<file>, skipping secrets."""
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
            copied.append((f, target / klass / f"{silo.kind}-{silo.name}" / f.name))
    return SyncPlan(copied, skipped)


def apply_sync(plan: SyncPlan, target: Path) -> list[Path]:
    """Write the planned library without clobbering equal/newer copies or escaping `target`."""
    target = Path(target).resolve()
    prefix = str(target) + os.sep
    written: list[Path] = []
    for src, dest in plan.copied:
        dest = dest.resolve()
        if dest != target and not str(dest).startswith(prefix):
            continue  # path-traversal guard: never write outside target
        if dest.exists() and dest.stat().st_mtime >= src.stat().st_mtime:
            continue  # don't overwrite an equal-or-newer library copy
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        written.append(dest)
    lines = ["# Dewey Library — index", ""]
    lines += [f"- `{d.relative_to(target).as_posix()}`" for d in sorted(written)]
    if plan.skipped_sensitive:
        lines += ["", "## Skipped (sensitive — never copied)", ""]
        lines += [f"- {p.name}" for p in plan.skipped_sensitive]
    (target / "LIBRARY-INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return written


# --- balance: find and heal duplicate entries across silos --------------------


@dataclass
class DupGroup:
    name: str
    freshest: Path
    identical_stale: list[Path]   # byte-identical older copies (safe to replace with a pointer)
    conflicts: list[Path]         # same name, different content (needs a human)


def _digest(path: Path) -> str:
    """Streaming sha256 so very large files never load fully into memory."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def find_duplicates(silos: list[Silo]) -> list[DupGroup]:
    """Group files by name across silos; classify older copies as identical or conflicting."""
    by_name: dict[str, list[Path]] = {}
    for silo in silos:
        for f in silo.files:
            by_name.setdefault(f.name, []).append(f)
    groups: list[DupGroup] = []
    for name, paths in sorted(by_name.items()):
        if len(paths) < 2:
            continue
        freshest = max(paths, key=lambda p: (p.stat().st_mtime, str(p)))  # deterministic
        fresh_digest = _digest(freshest)
        identical: list[Path] = []
        conflicts: list[Path] = []
        for p in paths:
            if p == freshest:
                continue
            (identical if _digest(p) == fresh_digest else conflicts).append(p)
        groups.append(DupGroup(name, freshest, identical, conflicts))
    return groups


def write_balance_log(dups: list[DupGroup]) -> Path:
    """Record what `--apply` is about to do, for recovery, before any file is touched."""
    log = Path.home() / ".dewey-balance-recovery.md"
    lines = [f"# dewey balance — recovery log ({datetime.now():%Y-%m-%d %H:%M})", ""]
    for g in dups:
        for stale in g.identical_stale:
            lines.append(f"- replaced `{portable(stale)}` -> canonical `{portable(g.freshest)}`")
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return log


def heal_duplicate(group: DupGroup) -> int:
    """Replace each byte-identical stale copy with a pointer stub.

    Re-verifies content at write time, so an edit made since the scan is never
    clobbered (closes the TOCTOU window). Conflicts are never touched.
    """
    if not group.freshest.exists():
        return 0
    fresh_digest = _digest(group.freshest)
    stub = (
        "# moved by `dewey balance`\n\n"
        "This was an exact duplicate. The canonical copy is at:\n\n"
        f"`{portable(group.freshest)}`\n"
    )
    healed = 0
    for stale in group.identical_stale:
        if not stale.exists() or _digest(stale) != fresh_digest:
            continue  # drifted since the scan — leave it alone
        stale.write_text(stub, encoding="utf-8")
        healed += 1
    return healed
