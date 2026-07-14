"""Cross-drive brain-health sweep — read-only.

Discovers every Markdown note across the given roots (by default the machine's
drives), hashes each one, guesses its Dewey class, and flags the four things a
brain needs to know about itself:

  * duplicate  — the same bytes in more than one place. A copy that spans two
                 roots (e.g. D: and the F: SATA backup) is a HEALTHY backup, not
                 waste; only extra copies WITHIN one drive are dedupe candidates.
  * orphan     — a memory-like note that links to nothing and is linked by
                 nothing (the "loose node" that is invisible to recall).
  * superseded — a note living under a wiped/archived/retired path (history).
  * secret     — a note whose body carries secret-like values (via the same
                 detector `dewey scrub` uses), so it can be rotated to .env.

It writes a human `BRAIN-HEALTH.md` report and a machine `brain-health-tasks.json`
task board the Hermes agents action — WITH APPROVAL, never auto-delete.

STRICTLY READ-ONLY over the scanned drives: the sweep never modifies, moves, or
deletes a scanned file. Its only writes are the two report artifacts, into the
output directory you choose.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from . import core

# Dirs we never descend into: build/vendor noise + OS/system trees that hold no
# memory. Compared lower-cased (Windows paths are case-insensitive).
PRUNE_DIRS = {d.lower() for d in core._PRUNE_DIRS} | {
    "vendor", ".pytest_cache", "_graph", ".obsidian", "site-packages",
    "$recycle.bin", "system volume information", "windows", "$windows.~bt",
    "programdata", "program files", "program files (x86)", "recovery",
    ".dewey-tmp", "_dewey-retired",
}
# A path under any of these marks a note as history, not live memory.
_SUPERSEDED_RE = re.compile(r"_vault-wiped|superseded|_retired|_archive|[/\\]backup", re.IGNORECASE)
# Where memory actually lives — used to keep "orphan" signal meaningful (a stray
# code README is not the brain's problem; an unlinked vault note is).
_MEMORY_HINT_RE = re.compile(r"brain|memory|obsidian|vault|\.claude", re.IGNORECASE)
_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)")

DEFAULT_DRIVES = ("C:\\", "D:\\", "F:\\")
_REPORT_MD = "BRAIN-HEALTH.md"
_TASKS_JSON = "brain-health-tasks.json"


@dataclass
class Note:
    """One Markdown file on disk, read exactly once."""

    path: Path
    root: Path            # the scan root it was found under (which drive)
    size: int
    sha: str
    klass: str
    category: str
    outbound: int         # count of [[wikilinks]] it contains
    stem: str             # lower-cased filename stem, for link matching
    superseded: bool
    secret_hits: int
    memory_like: bool
    orphan: bool = False              # filled by _mark_orphans
    redundant: bool = False           # an extra copy WITHIN one drive (dedupe target)
    canonical: Optional[Path] = None  # the copy we'd keep, when redundant


@dataclass
class Health:
    roots: list[Path]
    notes: list[Note]
    scanned: int
    capped: bool
    unreadable_dirs: int
    when: str


def _iter_md(root: Path) -> Iterator[tuple[Path, int]]:
    """Yield (markdown path, errors) under root, pruning noise/system dirs.

    os.walk swallows permission errors via `onerror`; we count them so the
    report can be honest about coverage instead of silently under-reporting.
    """
    errors = 0

    def _on_error(_exc: OSError) -> None:
        nonlocal errors
        errors += 1

    for dirpath, dirnames, filenames in os.walk(root, onerror=_on_error):
        dirnames[:] = [d for d in dirnames if d.lower() not in PRUNE_DIRS]
        for name in filenames:
            if name.lower().endswith(".md"):
                yield Path(dirpath) / name, errors


def _read_note(path: Path, root: Path) -> Optional[Note]:
    """Read one file exactly once; return a Note, or None if unreadable."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    text = data.decode("utf-8", "ignore")
    category, _ = core.categorize(path.stem)
    klass = core._CLASS_BY_CATEGORY.get(category, "000-meta")
    _, secret_hits = core.scrub_text(text)
    path_str = str(path)
    # Dewey's own hub/index files (LIBRARY-INDEX.md, _<class>.md, _LIBRARY-MAP.md) are
    # structure, not memory — never treat them as orphan memory notes (mirrors the
    # `_`-prefix / _WEAVE_SKIP convention used by library_entries and weave).
    is_structural = path.name.startswith("_") or path.name in core._WEAVE_SKIP
    memory_like = (not is_structural) and (
        category != "note" or bool(_MEMORY_HINT_RE.search(path_str)))
    return Note(
        path=path,
        root=root,
        size=len(data),
        sha=hashlib.sha256(data).hexdigest(),
        klass=klass,
        category=category,
        outbound=len(_WIKILINK_RE.findall(text)),
        stem=path.stem.lower(),
        superseded=bool(_SUPERSEDED_RE.search(path_str)),
        secret_hits=secret_hits,
        memory_like=memory_like,
    )


def _mark_duplicates(notes: list[Note]) -> None:
    """Flag extra copies that sit WITHIN a single drive as redundant (dedupe targets).

    Copies of the same bytes that span different roots are healthy backups and are
    left un-flagged — the report counts them separately as backup coverage.
    """
    by_sha: dict[str, list[Note]] = defaultdict(list)
    for n in notes:
        by_sha[n.sha].append(n)
    for group in by_sha.values():
        if len(group) < 2:
            continue
        per_root: dict[Path, list[Note]] = defaultdict(list)
        for n in group:
            per_root[n.root].append(n)
        for copies in per_root.values():
            if len(copies) < 2:
                continue  # single copy on this drive — nothing redundant here
            # Keep the shortest path (closest to a root) as canonical; flag the rest.
            keep = min(copies, key=lambda n: (len(str(n.path)), str(n.path)))
            for n in copies:
                if n is not keep:
                    n.redundant = True
                    n.canonical = keep.path


def _mark_orphans(notes: list[Note]) -> None:
    """A memory-like note is an orphan if it links to nothing and nothing links to it.

    The inbound set is every wikilink target's stem across all notes. Only notes
    that HAVE outbound links are re-read, so most files are touched just once.
    """
    targets: set[str] = set()
    for n in notes:
        if n.outbound:
            try:
                text = n.path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for raw in _WIKILINK_RE.findall(text):
                targets.add(Path(raw.strip()).stem.lower())
    for n in notes:
        if n.memory_like and n.outbound == 0 and n.stem not in targets:
            n.orphan = True


def sweep(roots: list[Path], *, max_files: int = 60000) -> Health:
    """Walk every root read-only, returning a Health snapshot. Honours a file cap loudly."""
    notes: list[Note] = []
    scanned = 0
    capped = False
    unreadable = 0
    for root in roots:
        if not root.exists():
            continue
        for path, errors in _iter_md(root):
            unreadable = errors
            scanned += 1
            if len(notes) >= max_files:
                capped = True
                break
            note = _read_note(path, root)
            if note is not None:
                notes.append(note)
        if capped:
            break
    _mark_duplicates(notes)
    _mark_orphans(notes)
    return Health(
        roots=roots,
        notes=notes,
        scanned=scanned,
        capped=capped,
        unreadable_dirs=unreadable,
        when=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


def _tasks(health: Health) -> list[dict]:
    """The machine task board: one entry per actionable finding (Hermes actions, with approval)."""
    tasks: list[dict] = []
    for n in health.notes:
        if n.redundant:
            tasks.append({"action": "dedupe", "path": str(n.path),
                          "reason": f"byte-identical to {n.canonical} on the same drive"})
        if n.secret_hits:
            tasks.append({"action": "scrub-secret", "path": str(n.path),
                          "reason": f"{n.secret_hits} secret-like value(s) in body — rotate to .env"})
        if n.superseded:
            tasks.append({"action": "retire-superseded", "path": str(n.path),
                          "reason": "lives under a wiped/archived/retired path — confirm it is history"})
        if n.orphan:
            tasks.append({"action": "review-orphan", "path": str(n.path),
                          "reason": "memory-like note with no links in or out — link it or retire it"})
    return tasks


def _backup_coverage(notes: list[Note]) -> int:
    """Count sha-groups whose copies span more than one root (healthy backup coverage)."""
    roots_by_sha: dict[str, set[Path]] = defaultdict(set)
    for n in notes:
        roots_by_sha[n.sha].add(n.root)
    return sum(1 for rs in roots_by_sha.values() if len(rs) > 1)


def render_report(health: Health) -> str:
    """The human BRAIN-HEALTH.md: counts first, then the actionable lists."""
    notes = health.notes
    redundant = [n for n in notes if n.redundant]
    secrets = [n for n in notes if n.secret_hits]
    superseded = [n for n in notes if n.superseded]
    orphans = [n for n in notes if n.orphan]
    by_class = Counter(n.klass for n in notes)
    backups = _backup_coverage(notes)

    lines = [
        f"# Brain Health — {health.when}", "",
        "> Read-only cross-drive sweep by `dewey health`. Nothing scanned was modified.", "",
        "## Vitals", "",
        f"- Roots swept: {', '.join(str(r) for r in health.roots)}",
        f"- Markdown notes read: **{len(notes)}** ({health.scanned} seen)"
        + ("  ⚠️ **CAP HIT — results truncated**" if health.capped else ""),
        f"- Healthy cross-drive backup groups: **{backups}**",
        f"- Redundant copies within a drive (dedupe): **{len(redundant)}**",
        f"- Notes with secret-like values (scrub): **{len(secrets)}**",
        f"- Superseded/archived notes: **{len(superseded)}**",
        f"- Orphan memory notes (no links in/out): **{len(orphans)}**",
    ]
    if health.unreadable_dirs:
        lines.append(f"- Unreadable dirs skipped (permissions): {health.unreadable_dirs}")
    lines += ["", "## Class distribution", ""]
    for klass in sorted(by_class):
        lines.append(f"- {klass}: {by_class[klass]}")

    def _section(title: str, items: list[Note], render) -> None:
        lines.extend(["", f"## {title} ({len(items)})", ""])
        if not items:
            lines.append("_none_")
            return
        for n in items[:200]:
            lines.append(render(n))
        if len(items) > 200:
            lines.append(f"- … and {len(items) - 200} more (see {_TASKS_JSON})")

    _section("Secrets to rotate", secrets,
             lambda n: f"- `{n.path}` — {n.secret_hits} value(s)")
    _section("Redundant within a drive", redundant,
             lambda n: f"- `{n.path}` → keep `{n.canonical}`")
    _section("Superseded / archived", superseded,
             lambda n: f"- `{n.path}`")
    _section("Orphan memory notes", orphans,
             lambda n: f"- `{n.path}` [{n.klass}]")
    lines += ["", "---",
              f"Machine task board for the Hermes agents: `{_TASKS_JSON}` "
              "(each task actioned with approval — nothing auto-deleted).", ""]
    return "\n".join(lines)


def write_reports(health: Health, out_dir: Path) -> tuple[Path, Path]:
    """Write BRAIN-HEALTH.md + brain-health-tasks.json into out_dir; return both paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report = out_dir / _REPORT_MD
    tasks = out_dir / _TASKS_JSON
    report.write_text(render_report(health), encoding="utf-8")
    tasks.write_text(json.dumps({"generated": health.when, "tasks": _tasks(health)}, indent=2),
                     encoding="utf-8")
    return report, tasks


def default_roots(bcp: Optional[str] = None) -> list[Path]:
    """The drives to sweep when the caller names none: existing C:/D:/F: plus an optional BCP path."""
    roots = [Path(d) for d in DEFAULT_DRIVES if Path(d).exists()]
    if bcp:
        roots.append(Path(bcp))
    return roots
