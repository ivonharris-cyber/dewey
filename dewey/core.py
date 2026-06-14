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
# Names Claude Code auto-loads on every launch — never replace these with a pointer stub.
# Compared case-insensitively (Windows/macOS filesystems are case-insensitive). CLAUDE.md is
# also auto-loaded but lives outside silos; MEMORY.md is the in-silo session index.
_NEVER_STUB = {"memory.md"}
# Per-silo / per-agent identity files: the same filename across silos is BY DESIGN
# (each agent's soul, each silo's index), never a cross-silo duplicate to merge.
_NEVER_MERGE = {"memory.md", "soul.md"}

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


def _atomic_write(path: Path, text: str) -> None:
    """Write via a temp file + atomic os.replace, so a crash never leaves a truncated/empty file."""
    tmp = path.with_name(path.name + ".dewey-tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


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
        freshest = max(paths, key=lambda p: (p.stat().st_mtime, p.as_posix()))  # deterministic, OS-independent
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
    bound = str(CLAUDE.resolve()) + os.sep
    fresh_digest = _digest(group.freshest)
    stub = (
        "# moved by `dewey balance`\n\n"
        "This was an exact duplicate. The canonical copy is at:\n\n"
        f"`{portable(group.freshest)}`\n"
    )
    healed = 0
    for stale in group.identical_stale:
        if stale.name.lower() in _NEVER_STUB:
            continue  # never stub a file the assistant auto-loads
        if stale.is_symlink() or not str(stale.resolve()).startswith(bound):
            continue  # only ever write a real file inside ~/.claude
        if not stale.exists() or _digest(stale) != fresh_digest:
            continue  # drifted since the scan — leave it alone
        _atomic_write(stale, stub)
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
    home = _homeify(canonical)
    return (
        "# moved by `dewey micronise`\n"
        f"# dewey-canonical: {home}\n\n"
        "The full copy lives in the library:\n\n"
        f"`{home}`\n"
    )


def _canonical_from_stub(text: str) -> Optional[Path]:
    """Read the library path back out of a pointer stub.

    Prefers the machine-readable `# dewey-canonical:` header; falls back to the
    backtick-quoted path line that older stubs (written before the header) used.
    """
    fallback: Optional[Path] = None
    for line in text.splitlines():
        if line.startswith("# dewey-canonical:"):
            return Path(line.split(":", 1)[1].strip()).expanduser()
        stripped = line.strip()
        if fallback is None and len(stripped) > 2 and stripped.startswith("`") and stripped.endswith("`"):
            fallback = Path(stripped[1:-1].strip()).expanduser()
    return fallback


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
            if f.name.lower() in _NEVER_STUB:
                continue  # never pointer-ize the live session index (MEMORY.md)
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
        if silo_file.name.lower() in _NEVER_STUB:
            continue  # defense-in-depth: never stub the live index even if it was planned
        if silo_file.is_symlink() or not str(silo_file.resolve()).startswith(bound):
            continue  # safety: only ever write a real file inside ~/.claude
        if not silo_file.exists() or not lib_copy.exists():
            continue
        if _digest(silo_file) != _digest(lib_copy):
            continue  # drifted since the scan — skip
        _atomic_write(silo_file, _pointer_stub(lib_copy))
        done += 1
    return done


# --- checkout / checkin: borrow a shrunk entry back, then return it -----------


def checkout_entry(silo_file: Path) -> bool:
    """Restore a pointer stub to its full library content so the assistant can read it again."""
    bound = str(CLAUDE.resolve()) + os.sep
    if silo_file.is_symlink() or not str(silo_file.resolve()).startswith(bound):
        return False
    if not silo_file.is_file():
        return False
    text = silo_file.read_text(encoding="utf-8", errors="ignore")
    if not text.startswith(_STUB_MARKER):
        return False  # not a pointer — nothing to check out
    canonical = _canonical_from_stub(text)
    if canonical is None or not canonical.is_file():
        return False
    _atomic_write(silo_file, canonical.read_text(encoding="utf-8"))
    return True


def checkin_entry(silo_file: Path, library: Path) -> bool:
    """Sync a checked-out entry's edits back to the library, then re-shrink it to a pointer."""
    bound = str(CLAUDE.resolve()) + os.sep
    if silo_file.is_symlink() or not str(silo_file.resolve()).startswith(bound):
        return False
    if not silo_file.is_file() or silo_file.name.lower() in _NEVER_STUB:
        return False
    text = silo_file.read_text(encoding="utf-8", errors="ignore")
    if text.startswith(_STUB_MARKER):
        return False  # still a pointer — nothing checked out to check in
    matches = sorted(
        p for p in Path(library).rglob(silo_file.name)
        if p.is_file() and not p.name.startswith("_")
    )
    if not matches:
        return False  # no library home — refuse rather than guess
    canonical = matches[0]
    if _digest(silo_file) != _digest(canonical):
        _atomic_write(canonical, text)  # carry the edits back to the shelf first
    _atomic_write(silo_file, _pointer_stub(canonical))
    return True


# --- reference desk: search the library + read entries (powers the MCP) -------


@dataclass
class Entry:
    name: str
    summary: str
    path: Path
    klass: str


def _summary(text: str) -> str:
    """One-line gist: the frontmatter `description:`, else the first real body line."""
    in_fm = False
    body_first = ""
    for i, line in enumerate(text.splitlines()):
        s = line.strip()
        if i == 0 and s == "---":
            in_fm = True
            continue
        if in_fm:
            if s == "---":
                in_fm = False
            elif s.lower().startswith("description:"):
                return s.split(":", 1)[1].strip().strip('"').strip()
            continue
        if s and not s.startswith("#") and not body_first:
            body_first = s
    return body_first


def library_entries(library: Path) -> list[Entry]:
    """Every shelved entry in the library (skips hub/index files), with a one-line summary."""
    library = Path(library)
    out: list[Entry] = []
    for p in sorted(library.rglob("*.md")):
        if p.name.startswith("_") or p.name in _WEAVE_SKIP:
            continue
        rel = p.relative_to(library)
        klass = rel.parts[0] if len(rel.parts) > 1 else "000-meta"
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        out.append(Entry(p.name, _summary(text), p, klass))
    return out


def search_library(library: Path, query: str) -> list[Entry]:
    """Case-insensitive AND-of-terms match over each entry's name, summary, and class."""
    q = query.lower().split()
    entries = library_entries(library)
    if not q:
        return entries
    return [e for e in entries if all(t in f"{e.name}\n{e.summary}\n{e.klass}".lower() for t in q)]


def read_library_entry(library: Path, name: str) -> Optional[str]:
    """Full text of a library entry by filename (first match); None if absent."""
    for e in library_entries(library):
        if e.name == name or e.name == f"{name}.md":
            return e.path.read_text(encoding="utf-8", errors="ignore")
    return None


# --- merge: consolidate duplicate-named entries across silos to one canonical -


@dataclass
class MergeGroup:
    name: str
    canonical: Path            # the copy we keep — largest, then newest
    redundant: list[Path]      # byte-identical extra copies (safe to retire)
    conflicts: list[Path]      # same name, different content (retired too, but flagged)


def find_name_duplicates(silos: list[Silo]) -> list[MergeGroup]:
    """Group entries that share a filename across silos; canonical = largest, then newest, then path."""
    by_name: dict[str, list[Path]] = {}
    for silo in silos:
        for f in silo.files:
            if f.name.lower() in _NEVER_MERGE or is_sensitive(f.name):
                continue  # never merge per-silo/agent identity files (MEMORY.md, soul.md) or credentials
            by_name.setdefault(f.name, []).append(f)
    groups: list[MergeGroup] = []
    for name, paths in sorted(by_name.items()):
        if len(paths) < 2:
            continue
        canonical = max(paths, key=lambda p: (p.stat().st_size, p.stat().st_mtime, p.as_posix()))
        cdig = _digest(canonical)
        redundant: list[Path] = []
        conflicts: list[Path] = []
        for p in paths:
            if p == canonical:
                continue
            (redundant if _digest(p) == cdig else conflicts).append(p)
        groups.append(MergeGroup(name, canonical, redundant, conflicts))
    return groups


def merge_archive_dir() -> Path:
    """Timestamped retirement folder under ~/.claude (outside every silo, so it is never re-scanned)."""
    return CLAUDE / "_dewey-retired" / datetime.now().strftime("%Y%m%d-%H%M%S")


def write_merge_log(groups: list[MergeGroup], archive: Path) -> Path:
    """Record what --apply will retire, before any file moves (recovery)."""
    log = Path.home() / ".dewey-merge-recovery.md"
    lines = [f"# dewey merge - recovery log ({datetime.now():%Y-%m-%d %H:%M})", "",
             f"archive: {_homeify(archive)}", ""]
    for g in groups:
        lines.append(f"- **{g.name}** keep canonical `{portable(g.canonical)}`")
        for r in g.redundant:
            lines.append(f"    - retired (identical): `{portable(r)}`")
        for c in g.conflicts:
            lines.append(f"    - flagged (CONFLICT - different content, NOT moved): `{portable(c)}`")
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return log


def apply_merge(groups: list[MergeGroup], archive: Path) -> int:
    """Move every non-canonical copy into the archive (never delete); re-checked, stays inside ~/.claude."""
    bound = str(CLAUDE.resolve()) + os.sep
    archive = Path(archive)
    moved = 0
    for g in groups:
        for p in g.redundant:  # only byte-identical extras are retired; conflicts are flagged, never moved
            if p.is_symlink() or not str(p.resolve()).startswith(bound):
                continue  # only ever move a real file from inside ~/.claude
            if not p.is_file():
                continue
            try:
                rel = p.resolve().relative_to(CLAUDE.resolve())
            except ValueError:
                rel = Path(p.name)
            dest = archive / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                dest = dest.with_name(f"{dest.stem}-{_digest(p)[:8]}{dest.suffix}")
            shutil.move(str(p), str(dest))
            moved += 1
    return moved


# --- scrub: redact secret VALUES from notes (the .env stays the single source) -

_SECRET_RES = [
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----", re.DOTALL),
    re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    re.compile(r"\bAQ\.[A-Za-z0-9_\-]{18,}\b"),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{20,}\b"),
    re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b"),
    re.compile(r"\b[0-9]{8,10}:[A-Za-z0-9_\-]{30,}\b"),       # telegram bot token
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
    re.compile(r"\b(?:gsk|glpat)[-_][A-Za-z0-9_\-]{20,}\b"),
]
_SECRET_KV_RE = re.compile(
    r"(?im)^(?P<key>\s*[-*>\s]*\"?[\w.\- ]*?(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?key|client[_-]?secret|token|auth[_-]?token|bearer|credential)s?[\w.\-]*\"?\s*[:=]\s*)(?P<val>\S[^\r\n]*)$"
)
_REDACTION = "[redacted -> .env]"


def scrub_text(text: str, extra: Optional[list[str]] = None) -> tuple[str, int]:
    """Replace high-confidence secret values with a marker; returns (new_text, redaction_count)."""
    n = 0
    for rx in _SECRET_RES:
        text, c = rx.subn(_REDACTION, text)
        n += c
    n += sum(1 for m in _SECRET_KV_RE.finditer(text) if _REDACTION not in m.group("val"))
    text = _SECRET_KV_RE.sub(lambda m: m.group(0) if _REDACTION in m.group("val") else m.group("key") + _REDACTION, text)
    for lit in (extra or []):
        if lit and lit in text and lit != _REDACTION:
            n += text.count(lit)
            text = text.replace(lit, _REDACTION)
    return text, n


def scan_secret_notes(silos: list[Silo], extra: Optional[list[str]] = None) -> list[tuple[Path, int]]:
    """Find notes that contain secret-like values, with a redaction count each."""
    out: list[tuple[Path, int]] = []
    for silo in silos:
        for f in silo.files:
            try:
                _, n = scrub_text(f.read_text(encoding="utf-8", errors="ignore"), extra)
            except OSError:
                continue
            if n:
                out.append((f, n))
    return out


def apply_scrub(silos: list[Silo], extra: Optional[list[str]] = None) -> int:
    """Redact secret values in place (atomic, inside ~/.claude only); returns notes changed."""
    bound = str(CLAUDE.resolve()) + os.sep
    changed = 0
    for silo in silos:
        for f in silo.files:
            if f.is_symlink() or not str(f.resolve()).startswith(bound):
                continue
            try:
                old = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            new, n = scrub_text(old, extra)
            if n and new != old:
                _atomic_write(f, new)
                changed += 1
    return changed


# --- consolidate: stitch notes into one scrubbed Markdown per major artery ----


def artery_key(stem: str) -> str:
    """Derive a coarse artery (major topic) from a filename stem: drop the category prefix,
    take the first non-numeric token. e.g. 'project_manametamaori-blog' -> 'manametamaori'."""
    rest = _PREFIX_RE.sub("", stem).strip(" -_")
    toks = [t for t in re.split(r"[-_]+", rest.lower()) if t and not t.isdigit()]
    return toks[0] if toks else "misc"


def plan_consolidate(silos: list[Silo], min_notes: int = 2) -> dict:
    """Group notes into arteries by topic; groups smaller than min_notes fold into '_misc'."""
    raw: dict = {}
    for silo in silos:
        for f in silo.files:
            if f.name.lower() in _NEVER_MERGE or is_sensitive(f.name):
                continue
            raw.setdefault(artery_key(f.stem), []).append(f)
    arteries: dict = {}
    for key, files in raw.items():
        arteries.setdefault(key if len(files) >= min_notes else "_misc", []).extend(files)
    for files in arteries.values():
        files.sort(key=lambda p: p.as_posix())
    return arteries


def write_arteries(arteries: dict, target: Path, extra=None) -> list:
    """Write one secret-scrubbed Markdown per artery: each member note under its own header."""
    target = Path(target).resolve()
    bound = str(target) + os.sep
    written = []
    for key, files in sorted(arteries.items()):
        dest = (target / f"{key}.md").resolve()
        if dest != target and not str(dest).startswith(bound):
            continue  # path-traversal guard
        lines = [f"# {key}", "",
                 f"> Consolidated artery — {len(files)} notes. Auto-built by `dewey consolidate`; secrets scrubbed.", ""]
        for f in files:
            try:
                body, _ = scrub_text(f.read_text(encoding="utf-8", errors="ignore"), extra)
            except OSError:
                continue
            _, title = categorize(f.stem)
            lines += [f"## {title or f.stem}", "", f"<sub>source: `{portable(f)}`</sub>", "",
                      body.strip(), "", "---", ""]
        dest.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(dest, "\n".join(lines) + "\n")
        written.append(dest)
    return written
