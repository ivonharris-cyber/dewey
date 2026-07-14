"""Dewey Reference Desk — a local MCP server over a synced library.

Optional component: `pip install dewey[mcp]`. Point it at a library (the folder
`dewey sync --to ... --apply` created) with the DEWEY_LIBRARY environment variable:

    DEWEY_LIBRARY=~/dewey-library dewey-mcp

Exposes search / ask / read / catalogue over the library, plus checkout / checkin
so an assistant can borrow a shrunk entry back to full content and return it, and
build_graph to (re)build the Graphify graph that makes `ask` graph-guided. `ask`
is the ranked, tag- and body-aware recall verb — prefer it over the strict `search`.
The core logic lives in `core.py` (dependency-free); only this thin wrapper needs `mcp`.
"""
from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from . import core, graph

mcp = FastMCP("dewey")


def _library() -> Path:
    raw = os.environ.get("DEWEY_LIBRARY", "")
    lib = Path(raw).expanduser() if raw else None
    if lib is None or not lib.is_dir():
        raise RuntimeError(
            "DEWEY_LIBRARY is not set to a real library directory. "
            "Create one with `dewey sync --to <dir> --apply`, then set DEWEY_LIBRARY=<dir>."
        )
    return lib


def _fmt(entries) -> str:
    return "\n".join(f"- {e.name}  [{e.klass}]  {e.summary}" for e in entries)


@mcp.tool()
def search(query: str) -> str:
    """Search the memory library (name, class, summary, tags, and body); AND-of-terms."""
    hits = core.search_library(_library(), query)
    if not hits:
        return f"No entries match '{query}'."
    head = f"{len(hits)} entr{'y' if len(hits) == 1 else 'ies'} for '{query}':"
    return head + "\n" + _fmt(hits[:50])


@mcp.tool()
def ask(question: str, limit: int = 8) -> str:
    """Ask a plain-language question; get the few entries that answer it.

    Graph-guided when a Graphify graph exists (`dewey graph`), otherwise a ranked
    keyword search over name/class/summary/tags/body. This is sharper than `search`
    for natural-language questions — prefer it for recall.
    """
    res = graph.ask(_library(), question)
    if not res.entries:
        return f"[{res.mode}] {res.note}\nNo entries answered '{question}'."
    return f"[{res.mode}] {res.note}\n" + _fmt(res.entries[:limit])


@mcp.tool()
def build_graph() -> str:
    """(Re)build the Graphify knowledge graph over the library so `ask` becomes graph-guided."""
    build = graph.build_graph(_library())
    return build.message


@mcp.tool()
def read_entry(name: str) -> str:
    """Return the full Markdown content of one library entry, by filename."""
    text = core.read_library_entry(_library(), name)
    return text if text is not None else f"No entry named '{name}'."


@mcp.tool()
def catalogue() -> str:
    """List every entry in the library (name, class, one-line summary)."""
    return _fmt(core.library_entries(_library())) or "Library is empty."


@mcp.tool()
def checkout(name: str) -> str:
    """Restore a shrunk silo entry to its full content so it loads in future sessions."""
    done = sum(
        core.checkout_entry(f)
        for s in core.discover_silos() for f in s.files if f.name == name
    )
    return f"checked out {done} cop{'y' if done == 1 else 'ies'} of '{name}'."


@mcp.tool()
def checkin(name: str) -> str:
    """Sync a checked-out entry's edits back to the library and re-shrink it to a pointer."""
    lib = _library()
    done = sum(
        core.checkin_entry(f, lib)
        for s in core.discover_silos() for f in s.files if f.name == name
    )
    return f"checked in {done} cop{'y' if done == 1 else 'ies'} of '{name}'."


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
