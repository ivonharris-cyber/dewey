"""Dewey x Graphify meld — the interlink + retrieval wave.

Dewey is the librarian (governance, secret-hygiene, one index, micronise/checkout).
Graphify (github.com/Graphify-Labs/graphify, PyPI `graphifyy`) is the cartographer —
it maps a folder into a queryable knowledge graph. This module melds them:

  dewey graph  — build the graph OVER THE SANITISED LIBRARY (never raw silos/.env),
                 so the map covers only what `sync` already cleared of secrets.
  dewey ask    — a question -> the few entries that answer it. With a graph present it
                 asks Graphify and pulls the named entries; with no graph (or no
                 Graphify installed) it degrades to Dewey's own keyword search, so the
                 verb always works — it just gets sharper once the graph exists.

Design rule: we WRAP Graphify's CLI and extract only stable filename references from
its output. We never hand-parse Graphify's internal JSON schema — the meld stays honest
and survives upstream graph-format changes. The graph is a DERIVED CACHE: rebuilt from
the library, never a second source of truth. Files win every disagreement.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import core

# Where the derived graph lives — beside the library, clearly disposable.
GRAPH_DIRNAME = "_graph"
_MD_TOKEN = re.compile(r"[A-Za-z0-9][\w./-]*\.md")


def graphify_cli() -> Optional[str]:
    """Path to the `graphify` command, or None if it isn't installed."""
    return shutil.which("graphify")


@dataclass
class GraphBuild:
    ok: bool
    out_dir: Path
    message: str
    artifacts: list[Path]


def build_graph(library: Path, *, timeout: int = 900) -> GraphBuild:
    """Run Graphify over the sanitised library; drop artifacts in library/_graph.

    We point Graphify ONLY at the synced library — the 16 secret-named files were
    already excluded by `sync`, so the graph can never ingest a credential.
    """
    library = Path(library).resolve()
    out_dir = library / GRAPH_DIRNAME
    if not library.is_dir():
        return GraphBuild(False, out_dir, f"not a library directory: {library}", [])

    cli = graphify_cli()
    if not cli:
        return GraphBuild(
            False, out_dir,
            "graphify is not installed. Install it yourself (you approve the package):\n"
            "    pip install graphifyy      # PyPI package for github.com/Graphify-Labs/graphify\n"
            "then re-run `dewey graph`.",
            [],
        )

    out_dir.mkdir(exist_ok=True)
    # `graphify <path> --out <dir>`; we keep it to the documented positional + output.
    try:
        proc = subprocess.run(
            [cli, str(library), "--out", str(out_dir)],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return GraphBuild(False, out_dir, f"graphify timed out after {timeout}s", [])
    except OSError as e:
        return GraphBuild(False, out_dir, f"could not run graphify: {e}", [])

    artifacts = [p for p in out_dir.rglob("*") if p.is_file()]
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
        return GraphBuild(False, out_dir, "graphify failed:\n  " + "\n  ".join(tail), artifacts)
    return GraphBuild(True, out_dir, f"graph built ({len(artifacts)} artifact(s))", artifacts)


@dataclass
class AskResult:
    mode: str                 # "graph" or "keyword"
    question: str
    entries: list[core.Entry]
    note: str


def _entries_by_name(library: Path) -> dict[str, core.Entry]:
    return {e.name: e for e in core.library_entries(library)}


_STOP = {"the", "a", "an", "of", "for", "to", "and", "or", "in", "on", "is", "what",
         "how", "why", "who", "when", "where", "with", "my", "our", "me", "do", "does"}


def _ranked_keyword(library: Path, question: str) -> list[core.Entry]:
    """Ranked OR-match: score each entry by how many question terms it hits.

    Dewey's own `search_library` is strict AND (every term must appear) — which
    returns nothing for a natural-language question. This ranked OR fallback is
    both useful today and the honest baseline the graph must beat.
    """
    terms = [t for t in re.split(r"\W+", question.lower()) if t and t not in _STOP and len(t) > 2]
    if not terms:
        return core.library_entries(library)
    scored: list[tuple[int, core.Entry]] = []
    for e in core.library_entries(library):
        hay = f"{e.name}\n{e.summary}\n{e.klass}".lower()
        score = sum(1 for t in terms if t in hay)
        if score:
            scored.append((score, e))
    scored.sort(key=lambda se: (-se[0], se[1].name))
    return [e for _, e in scored]


def ask(library: Path, question: str, *, timeout: int = 120) -> AskResult:
    """Return the few library entries that answer the question.

    Graph mode: ask Graphify, extract the .md filenames it cites, resolve them to
    library entries (ranked in the order Graphify surfaced them). Keyword mode
    (no graph / no graphify): fall back to Dewey's proven `search_library`.
    """
    library = Path(library).resolve()
    by_name = _entries_by_name(library)
    graph_dir = library / GRAPH_DIRNAME
    cli = graphify_cli()

    if cli and graph_dir.is_dir():
        try:
            proc = subprocess.run(
                [cli, "query", question, "--out", str(graph_dir)],
                capture_output=True, text=True, timeout=timeout,
            )
            text = (proc.stdout or "") + "\n" + (proc.stderr or "")
        except (subprocess.TimeoutExpired, OSError) as e:
            text = ""
            proc = None  # type: ignore
        if proc is not None and proc.returncode == 0:
            seen: list[core.Entry] = []
            for tok in _MD_TOKEN.findall(text):
                name = Path(tok).name
                e = by_name.get(name)
                if e and e not in seen:
                    seen.append(e)
            if seen:
                return AskResult("graph", question, seen,
                                 "graph-guided: Graphify traced these from the knowledge graph")

    # Fallback — always works, honest about being keyword-only.
    hits = _ranked_keyword(library, question)
    note = ("keyword fallback (ranked): no graph yet — run `dewey graph --to <library>` to enable "
            "graph-guided retrieval" if not (cli and graph_dir.is_dir())
            else "keyword fallback (ranked): the graph returned nothing citable for this question")
    return AskResult("keyword", question, hits, note)
