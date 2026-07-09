# Changelog

All notable changes to Dewey are documented here. This project follows [Semantic Versioning](https://semver.org).

## [0.5.0] — 2026-07-10

The **living 3D brain** — memory you can watch think.

### Added
- **`dewey brain --to <library>`** — generates `_brain-3d.html`, a WebGL force-graph
  (vasturiano/3d-force-graph, Three.js) of the whole library. Nodes coloured by Dewey
  class; **directional particles run along every edge** — the synapse-runners. Fully
  local except the graph library from a CDN. Derived artifact, rebuilt from the files.
- **Thought traces** — `dewey ask` now writes `_brain-thought.json` (the entries it
  touched, rank-ordered). The viewer polls it and lights that route: the **origin**
  (where the thought started, rank[0]) glows biggest and whitest, the **reach** (how
  deep it went) glows gold. Retrieval becomes a visible burst of synaptic traffic.
- `dewey/brain3d.py` + 4 tests (28 total). Verified live: rendered 1490 nodes / 673
  links in a headless browser and screenshotted the result.

## [0.4.0] — 2026-07-10

The **Graphify meld** — Dewey the librarian gains a cartographer. First wave of the
"multi-waved brain" (see `docs/DEWEY-GRAPHIFY-MELD.md`): keyword retrieval becomes
graph-guided retrieval, without losing the one-index / secret-hygiene / files-win laws.

### Added
- **`dewey graph --to <library>`** — builds a queryable knowledge graph over the
  **sanitised** library via [Graphify](https://github.com/Graphify-Labs/graphify)
  (PyPI `graphifyy`). Points Graphify only at the synced library, so the graph can
  never ingest one of the 16 secret-named files `sync` already excluded. The graph is a
  **derived cache** — rebuilt from the files, never a second source of truth.
- **`dewey ask "<question>" --to <library>`** — returns the *few* entries that answer a
  question, ready to `checkout`. With a graph present it asks Graphify and resolves the
  cited entries; with no graph (or Graphify not installed) it degrades to a **ranked
  keyword** fallback, so the verb always works and gets sharper once the graph exists.
- `dewey/graph.py` + 4 tests (24 total). We wrap Graphify's CLI and extract only stable
  `.md` filename references — never hand-parse its internal JSON schema, so the meld
  survives upstream format changes.

### Notes
- Graphify is **not** a Dewey dependency: the core stays zero-dependency and both new
  verbs run without it (keyword mode). Install `graphifyy` yourself to enable graph mode.

## [0.3.0] — 2026-06-11

The Reference Desk goes live as a **local MCP server**.

### Added
- **`dewey-mcp`** — a local [MCP](https://modelcontextprotocol.io) server over a synced library, so an assistant can query memory natively instead of loading the whole thing. Tools: `search`, `read_entry`, `catalogue`, `checkout`, `checkin`.
- Reference-desk logic in the dependency-free core (`library_entries`, `search_library`, `read_library_entry`) — 3 more tests (11 total).
- Optional install extra `pip install dewey[mcp]`. The core stays **zero-dependency**; only the server needs `mcp`.

### Usage
```bash
DEWEY_LIBRARY=~/dewey-library dewey-mcp
```

## [0.2.0] — 2026-06-11

The release that makes shrinking **reversible** — and hardens the destructive paths.

### Added
- **`dewey checkout NAME | --all`** — restore a shrunk (pointered) entry to its full library content so the assistant can read it again.
- **`dewey checkin NAME --library DIR | --all`** — sync a checked-out entry's edits back to the library, then re-shrink it to a pointer.
- A machine-readable `# dewey-canonical:` header in pointer stubs, so `checkout` resolves reliably (with a fallback that still reads older stubs).
- The project's first unit-test suite — **8 tests** covering the micronise skip-rules and the checkout/checkin round-trip.

### Changed / Hardened
- **`micronise` never pointer-izes `MEMORY.md`** — the index Claude Code auto-loads on every launch. Matched case-insensitively and enforced in both the plan and apply layers.
- **All destructive writes are now atomic** (temp file + `os.replace`) — a crash can never leave a truncated or empty silo file.
- **`balance` gained the `~/.claude` boundary + symlink guards** that `micronise` already had.

### Still zero runtime dependencies, still under 1,000 lines.

## [0.1.0] — 2026-06-10

### Added
- Initial public release (MIT). `sweep`, `log`, `doctor`, `sync`, `balance`, `weave`, `micronise` — map, date, de-duplicate, shelve, cluster + colour (Obsidian), and shrink stray Claude Code memory silos into one classified library.
