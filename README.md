<p align="center">
  <img src="assets/dewey-mascot.webp" width="160" alt="Dewey">
</p>

# Dewey — a memory librarian for Claude Code

> **A coding assistant's memory, kept honest — in under 1,000 lines of dependency-free Python.**

Claude Code writes its memory into a folder keyed to the directory it was launched from. Work from
different locations for a few months and you end up with several isolated memory silos that never
synchronise — hundreds of scattered `.md` files, duplicates, and bloat, with no shared index. Dewey
maps them, dates them, de-duplicates them, and collapses the lot into one browsable, classified library.

**Measured on a real estate:** 16 silos, 454 files. A library of 442 entries — ≈**1.4 MB** of memory —
micronises to ≈**75 KB** of pointers (**~95% smaller**), with the full content preserved in the library.

## Philosophy: less, not more

Most agent-memory tools add weight — vector databases, knowledge graphs, extra indexes. Dewey does the
opposite. It collapses each oversized memory file into a small pointer: a call number, a one-line
summary, and a link. The full content lives once — in your vault or Notion — while the file the
assistant loads each session shrinks from kilobytes to bytes.

Shorter context is better engineering. Bloat is removed at the source, not indexed around it. The whole
tool is **deliberately under 1,000 lines, with zero runtime dependencies** — auditable in one sitting.
Contributions that make memory *smaller*, not heavier, are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## The model: a library

- The vault or Notion holds the canonical copy of every entry — the shelves.
- Each memory silo is a working desk that holds only what it currently needs.
- `memory.md` is the library card: it lists what the agent has on loan.

Entries are classified first by type — an established fact vs. a proposal or idea — and then by subject,
in a Dewey-style `000`–`900` range. When a proposal ships, it is re-filed from "idea" to "fact".

## Commands

| Command | Status | Description |
|---|---|---|
| `dewey sweep` | available | List every memory silo and its file count |
| `dewey log` | available | List every memory entry in date order |
| `dewey doctor [root]` | available | Scan repositories for committed `.env` files and missing ignore rules (no secret values are read) |
| `dewey sync --to DIR` | available | Copy memory into a browsable Markdown library; skips credential files; dry-run by default |
| `dewey balance` | available | Replace exact-duplicate entries with a pointer; conflicts are reported, never modified; dry-run by default |
| `dewey weave --to DIR` | available | Link a library into per-class topic clusters and colour each class in the Obsidian graph |
| `dewey micronise --library DIR` | available | Replace shelved silo files with pointers (content stays in the library); reports the size saved; dry-run by default |
| `dewey checkout NAME` / `--all` | available | Restore a shrunk entry to full content so the assistant can read it |
| `dewey checkin NAME --library DIR` / `--all` | available | Sync a checked-out entry's edits back to the library and re-shrink it to a pointer |

> **`micronise` never shrinks `MEMORY.md`** — it's the index your assistant loads on every launch, so it always stays whole. For every other entry the full copy lives in the library, and `--apply` writes a recovery log you can restore from.

## Reference Desk (MCP)

A local MCP server — `dewey-mcp` — lets the assistant query the catalogue and load only the relevant
entries, rather than the whole library:

> **Query:** "What do we have on authentication?"
> **Reply:** "Three entries — the login service, the token store, and the OAuth migration. Load them?"

Install the extra and point it at your library:

```bash
pip install dewey[mcp]
DEWEY_LIBRARY=~/dewey-library dewey-mcp
```

Tools: `search`, `read_entry`, `catalogue`, `checkout`, `checkin`. The core stays
dependency-free — only this server needs `mcp`.

## Roadmap

- **Obsidian** — works today: point `sync` at your vault and entries appear natively (plain Markdown), then `weave` clusters and colours them.
- **Notion** — a `sync --to notion` integration, using your own token.
- **MCP server** — ✅ shipped in 0.3.0 (`dewey-mcp`, the Reference Desk above).
- **A measured token benchmark** — ✅ first run in [docs/BENCHMARK.md](docs/BENCHMARK.md): a 2.94 MB / ~770K-token estate (3.9× over a 200K window) answered one real question from ~800 tokens of index — ~960× lighter, lossless.
- Scheduled `balance` (cron / n8n) and an archive for entries that fall out of use.

## Security

- The repository contains code only — never your data. Memory and `.env` files are excluded by `.gitignore`.
- `dewey doctor` detects leaks (tracked `.env`, missing ignore rules) without printing any secret value.
- `dewey sync` and `dewey micronise` skip any file whose name indicates credentials.

## Install

See [SETUP.md](SETUP.md). Quickest path:

```
pipx install git+https://github.com/ivonharris-cyber/dewey
dewey --version
dewey sweep
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md). Latest: **0.2.0** — `checkout`/`checkin` make shrinking reversible, plus atomic writes and `MEMORY.md` protection.

## License

MIT — see [LICENSE](LICENSE).
