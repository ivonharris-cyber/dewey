<p align="center">
  <img src="assets/dewey-mascot.webp" width="160" alt="Dewey">
</p>

# Dewey — a memory librarian for Claude Code

Claude Code stores its memory in a folder keyed to the directory it was launched from. Over time,
working from different locations produces several isolated memory silos that never synchronise —
leaving hundreds of scattered `.md` files with no shared index. Dewey maps them, dates them,
removes duplicates, and keeps a single canonical copy.

## Why it exists

A coding assistant's memory is siloed, and it is never read automatically from external stores such
as Notion or an Obsidian vault. Those stores and the assistant's own memory therefore drift apart.
Dewey is the bridge that keeps an agent's memory tidy, consistent, and free of bloat.

## Philosophy: less, not more

Most agent-memory tools add weight — vector databases, knowledge graphs, extra indexes. Dewey does
the opposite. It collapses each oversized memory file into a small pointer: a call number, a one-line
summary, and a link. The full content lives once — in your vault or Notion — while the file the
assistant loads each session shrinks from kilobytes to bytes.

Shorter context is better engineering. Bloat is removed at the source, not indexed around it.
Contributions that make memory smaller, not heavier, are welcome.

## The model: a library

- The vault or Notion holds the canonical copy of every entry — the shelves.
- Each memory silo is a working desk that holds only what it currently needs.
- `memory.md` is the library card: it lists what the agent has on loan.

Entries are classified first by type — an established fact versus a proposal or idea — and then by
subject, in a Dewey-style 000–900 range. When a proposal becomes real, it is re-filed from "idea"
to "fact".

## Commands

| Command | Status | Description |
|---|---|---|
| `dewey sweep` | available | List every memory silo and its file count |
| `dewey log` | available | List every memory entry in date order |
| `dewey doctor [root]` | available | Scan repositories for committed `.env` files and missing ignore rules (no secret values are read) |
| `dewey sync --to DIR` | available | Copy memory into a browsable Markdown library; skips credential files; dry-run by default |
| `dewey balance` | available | Find duplicate entries across silos and replace exact duplicates with a pointer; conflicts are reported, never modified; dry-run by default |
| `dewey weave --to DIR` | available | Link a synced library into per-class topic clusters and colour each class (000–900) in the Obsidian graph |
| `dewey micronise --library DIR` | available | Replace shelved silo files with small pointers (content stays in the library); reports the size saved; dry-run by default |
| `dewey checkout` / `checkin` | planned | Borrow and return entries for context — ships with the MCP layer below |

## Reference Desk (planned — MCP)

An MCP server will let the assistant query the catalogue in natural language and load only the
relevant entries, rather than the whole library:

> **Query:** "What do we have on authentication?"
> **Reply:** "Three entries — the login service, the token store, and the OAuth migration. Load them?"

## Roadmap

- **Obsidian** — already works at the file level: point `sync` at your vault and the entries appear
  natively, because Dewey writes plain Markdown. A one-click community plugin is a future convenience.
- **Notion** — a `sync --to notion` integration that publishes the categorised library to a Notion
  database, using your own Notion token.
- **MCP server** — the Reference Desk above, so an assistant can query and check out entries directly.
- A scheduled job (cron or an automation tool such as n8n) that runs `dewey balance` on a regular cadence.
- An archive for entries that fall out of use, so nothing is permanently lost.

## Security

- The repository contains code only — never your data. Memory and `.env` files are excluded by `.gitignore`.
- `dewey doctor` detects leaks (tracked `.env` files, missing ignore rules) without printing any secret value.
- `dewey sync` skips any file whose name indicates credentials.

## Install

See [SETUP.md](SETUP.md). Quickest path:

```
pipx install git+https://github.com/ivonharris-cyber/dewey
dewey --version
dewey sweep
```

## License

MIT — see [LICENSE](LICENSE).
