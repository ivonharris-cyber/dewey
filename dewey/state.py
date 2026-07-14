"""The canonical STATE entry — one truth, read first every session.

`dewey state` reads/writes a single always-current entry at
`<library>/000-meta/STATE.md`: the current project, the date, the last action,
open loops, a Notion pointer, and the active project's tag id. A SessionStart
hook loads it so the assistant opens each session knowing where things stand,
instead of a blank slate; each check-in updates it.

Dependency-free (stdlib only), like the rest of core.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import core

STATE_REL = "000-meta/STATE.md"
_FIELDS = ("project", "date", "last", "notion", "tag")


@dataclass
class State:
    project: str = ""
    date: str = ""
    last: str = ""
    notion: str = ""
    tag: str = ""
    loops: list[str] = field(default_factory=list)


def state_path(library: Path) -> Path:
    return Path(library) / STATE_REL


def _parse_flat_frontmatter(text: str) -> dict:
    """Read flat `key: value` pairs from a leading `--- … ---` frontmatter block."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    out: dict[str, str] = {}
    for line in lines[1:]:
        s = line.strip()
        if s == "---":
            break
        if ":" in s and not s.startswith("#"):
            k, v = s.split(":", 1)
            out[k.strip().lower()] = v.strip().strip('"').strip("'")
    return out


def read_state(library: Path) -> Optional[State]:
    """Load the STATE entry, or None if it doesn't exist yet."""
    path = state_path(library)
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="ignore")
    fm = _parse_flat_frontmatter(text)
    # Open loops are only the bullets UNDER the "## Open loops" header.
    loops: list[str] = []
    in_loops = False
    for ln in text.splitlines():
        s = ln.strip()
        if s.lower().startswith("## open loops"):
            in_loops = True
            continue
        if in_loops:
            if s.startswith("## "):
                break
            if s.startswith("- ") and s != "- (none)":
                loops.append(s[2:].strip())
    return State(
        project=fm.get("project", ""),
        date=fm.get("date", ""),
        last=fm.get("last", ""),
        notion=fm.get("notion", ""),
        tag=fm.get("tag", ""),
        loops=[x for x in loops if x],
    )


def render_state(state: State) -> str:
    """Render STATE.md: a parseable frontmatter head + a human body."""
    head = ["---",
            "description: Canonical session truth — read first every session (dewey state).",
            f"project: {state.project}",
            f"date: {state.date}",
            f"last: {state.last}",
            f"notion: {state.notion}",
            f"tag: {state.tag}",
            "---", ""]
    body = ["# STATE — the one truth", "",
            f"- **Project:** {state.project or '—'}",
            f"- **As of:** {state.date or '—'}",
            f"- **Last action:** {state.last or '—'}",
            f"- **Notion:** {state.notion or '—'}",
            f"- **Active tag id:** {state.tag or '—'}", "",
            "## Open loops", ""]
    body += [f"- {loop}" for loop in state.loops] or ["- (none)"]
    return "\n".join(head + body) + "\n"


def write_state(library: Path, state: State) -> Path:
    """Write STATE.md atomically under library/000-meta; returns its path."""
    path = state_path(library)
    path.parent.mkdir(parents=True, exist_ok=True)
    core._atomic_write(path, render_state(state))
    return path


def update_state(library: Path, *, project: Optional[str] = None, last: Optional[str] = None,
                 loops: Optional[list[str]] = None, notion: Optional[str] = None,
                 tag: Optional[str] = None, today: Optional[str] = None) -> tuple[State, Path]:
    """Merge the given fields into the existing STATE (or a fresh one) and write it.

    Only fields you pass are changed; the date is always refreshed to today. If you
    name a project but no tag, the active project's tag id is looked up from the library.
    """
    state = read_state(library) or State()
    if project is not None:
        state.project = project
    if last is not None:
        state.last = last
    if loops is not None:
        state.loops = loops
    if notion is not None:
        state.notion = notion
    if tag is not None:
        state.tag = tag
    elif project is not None:
        found = _tag_for_project(library, state.project)
        if found:
            state.tag = found
    state.date = today or datetime.now().strftime("%Y-%m-%d")
    path = write_state(library, state)
    return state, path


def _tag_for_project(library: Path, project: str) -> str:
    """The call number of the freshest entry whose tags.project matches (best-effort)."""
    if not project:
        return ""
    best = ""
    for e in core.library_entries(library):
        if e.tags.get("project", "").lower() == project.lower():
            best = e.tags.get("call") or e.tags.get("id") or best
    return best
