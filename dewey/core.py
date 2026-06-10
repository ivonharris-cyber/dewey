"""Core library logic: discover silos, build the dated log, scan repos for leaks,
shelve / de-duplicate memory, and weave + micronise it into a vault.

No secret values are ever read or printed — `doctor` checks git-tracking and
.gitignore coverage only, and `sync` skips credential-named files entirely.
"""
from __future__ import annotations

import hashlib
import json
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
_WEAVE_SKIP = {"LIBRARY-INDEX.md"}
_STUB_MARKER = "# moved by `dewey"

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

_CLASS_COLORS = {
    "000-meta": "9AA0A6", "100-people": "E8833A", "200-infra": "4C8BF5",
    "300-agents": "A45CF0", "400-projects": "3FB950", "500-reference": "2BB7B3",
    "600-secrets": "E5534B", "700-voice": "EC6CB9", "800-brains": "E3B341",
    "900-sessions": "6E7BF2",
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
        return _homeify(path)


def _homeify(path: Path) -> str:
    """Replace the home-directory prefix with ~ so paths carry no username."""
    home = str(Path.home())
    s = str(path)
    return "~" + s[len(home):] if s.startswith(home) else s


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
    """Replace each byte-identical stale copy with a pointer stub (re-verified; conflicts untouched)."""
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


# --- weave: connect + colour the synced library in the Obsidian graph --------


def find_vault(start: Path) -> Optional[Path]:
    """Walk up from `start` to the Obsidian vault root (the dir containing .obsidian)."""
    for d in [start, *start.parents]:
        if (d / ".obsidian").is_dir():
            return d
    return None


def weave_library(library: Path) -> tuple[Path, int, list[str]]:
    """Per-class hub notes (topic clusters) + a master Map of Content, all wikilinked."""
    library = Path(library).resolve()
    vault = find_vault(library)
    prefix = (library.relative_to(vault).as_posix() + "/") if vault else ""
    by_class: dict[str, list[Path]] = {}
    for p in sorted(library.rglob("*.md")):
        if p.name.startswith("_") or p.name in _WEAVE_SKIP:
            continue
        rel = p.relative_to(library)
        klass = rel.parts[0] if len(rel.parts) > 1 else "000-meta"
        by_class.setdefault(klass, []).append(rel)
    total = 0
    hub_links: list[str] = []
    bound = str(library) + os.sep
    for klass in sorted(by_class):
        hub_lines = [f"# {klass}", "", f"> Topic cluster — {len(by_class[klass])} entries.", ""]
        for rel in by_class[klass]:
            hub_lines.append(f"- [[{prefix}{rel.with_suffix('').as_posix()}|{rel.stem}]]")
            total += 1
        hub_dest = (library / klass / f"_{klass}.md").resolve()
        if not str(hub_dest).startswith(bound):
            continue  # path-traversal guard
        hub_dest.parent.mkdir(parents=True, exist_ok=True)
        hub_dest.write_text("\n".join(hub_lines) + "\n", encoding="utf-8")
        hub_links.append(f"- [[{prefix}{klass}/_{klass}|{klass}]] ({len(by_class[klass])})")
    moc_lines = ["# Dewey Library — Map of Content", "",
                 "> Auto-generated by `dewey weave`. Each class is a colour-coded topic cluster.", ""]
    moc_lines += hub_links
    moc = library / "_LIBRARY-MAP.md"
    moc.write_text("\n".join(moc_lines) + "\n", encoding="utf-8")
    return moc, total, sorted(by_class.keys())


def weave_colors(vault: Path, library: Path, classes: list[str]) -> Path:
    """Write Obsidian graph colour-groups so each Dewey class (000–900) shows in its own colour."""
    rel = library.relative_to(vault).as_posix()
    gpath = vault / ".obsidian" / "graph.json"
    raw = gpath.read_text(encoding="utf-8") if gpath.is_file() else None
    try:
        data = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, ValueError):
        data = {}
    bak = vault / ".obsidian" / "graph.json.bak"
    if raw is not None and not bak.exists():  # preserve the ORIGINAL — never clobber a prior backup
        bak.write_text(raw, encoding="utf-8")
    query_prefix = f'path:"{rel}/'
    groups = [g for g in data.get("colorGroups", []) if not g.get("query", "").startswith(query_prefix)]
    for klass in classes:
        color = _CLASS_COLORS.get(klass)
        if color:
            groups.append({"query": f'{query_prefix}{klass}"', "color": {"a": 1, "rgb": int(color, 16)}})
    data["colorGroups"] = groups
    gpath.parent.mkdir(parents=True, exist_ok=True)
    gpath.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return gpath


# --- micronise: shrink shelved silo files to pointers (the de-bloat) ---------


@dataclass
class MicroPlan:
    targets: list[tuple[Path, Path]]  # (silo_file, byte-identical library copy)
    before_bytes: int
    after_bytes: int


def _pointer_stub(canonical: Path) -> str:
    return (
        "# moved by `dewey micronise`\n\n"
        "The full copy lives in the library:\n\n"
        f"`{_homeify(canonical)}`\n"
    )


def plan_micronise(silos: list[Silo], library: Path) -> MicroPlan:
    """Plan replacing each silo file that has a byte-identical library copy with a small pointer."""
    library = Path(library)
    lib: dict[str, list[Path]] = {}
    for p in library.rglob("*.md"):
        if p.name.startswith("_") or p.name in _WEAVE_SKIP:
            continue
        lib.setdefault(p.name, []).append(p)
    targets: list[tuple[Path, Path]] = []
    before = after = 0
    for silo in silos:
        for f in silo.files:
            cands = lib.get(f.name, [])
            if not cands:
                continue
            try:
                if f.read_text(encoding="utf-8", errors="ignore").startswith(_STUB_MARKER):
                    continue  # already a pointer — skip
                fdig = _digest(f)
            except OSError:
                continue
            match = next((c for c in cands if _digest(c) == fdig), None)
            if match:
                targets.append((f, match))
                before += f.stat().st_size
                after += len(_pointer_stub(match).encode("utf-8"))
    return MicroPlan(targets, before, after)


def write_micronise_log(plan: MicroPlan) -> Path:
    log = Path.home() / ".dewey-micronise-recovery.md"
    lines = [f"# dewey micronise — recovery log ({datetime.now():%Y-%m-%d %H:%M})", ""]
    for silo_file, lib_copy in plan.targets:
        lines.append(f"- shrank `{_homeify(silo_file)}` -> pointer to `{_homeify(lib_copy)}`")
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return log


def apply_micronise(plan: MicroPlan) -> int:
    """Replace each planned silo file with a pointer, re-verifying content first (no data loss)."""
    bound = str(CLAUDE.resolve()) + os.sep
    done = 0
    for silo_file, lib_copy in plan.targets:
        if not str(silo_file.resolve()).startswith(bound):
            continue  # safety: only ever write inside ~/.claude
        if not silo_file.exists() or not lib_copy.exists():
            continue
        if _digest(silo_file) != _digest(lib_copy):
            continue  # drifted since the scan — skip
        silo_file.write_text(_pointer_stub(lib_copy), encoding="utf-8")
        done += 1
    return done
