# Changelog

All notable changes to Dewey are documented here. This project follows [Semantic Versioning](https://semver.org).

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
