# 📚 Dewey — a memory librarian for Claude Code

> Claude Code writes memory into a folder keyed to *wherever you launched it*. Work from your
> home dir, from `system32`, from `D:\Projects` — each gets its **own** silo, and none of them
> sync. Do this for months and you wake up with **hundreds of stray `.md` files** and no map.
> Dewey is the librarian that maps them, dates them, and keeps **one** canonical copy.

Stardate 10-06-2026. Built because Ivon the Dyslexic Nerd found 430 stray memories across 18 silos.

**Why it exists:** you build the Notion, you build the vault — but your coding agent still *forgets*,
because its memory is siloed and never auto-read from those stores. Dewey is the bridge that keeps the
Coder **tidy and un-forgetting.**

---

## Philosophy — micronisation

Everyone else makes agent memory **bigger and smarter** — vector DBs, knowledge graphs, more indexes.
Dewey goes the other way: **smaller.**

> Shorter context is sharper model engineering. A pointer is a wink to a mate — a picture worth a
> thousand words. Humans think big and go big; but the truth an LLM needs is a short code, not a long note.

Dewey collapses each bloated memory file into a tiny **pointer stub** (call-number + one-line hook + link).
The full content lives **once** in your vault or Notion. The silo Claude auto-loads every session shrinks
from kilobytes to bytes. **Bloat is stopped at the root** — not indexed around it.

**Invitation to the world: micronisation.** PRs that make memory *smaller*, not heavier, are welcome.

## The rule of three (where things live)

| Store | Holds | |
|---|---|---|
| **Claude memory** | short **facts** = Dewey call-numbers + pointers | *what Claude auto-reads* |
| **Vault + Slack** | the **conversations** — sessions, diaries, chatter | |
| **Notion** | the **Book** — the explained, readable reference | |

Memory is the **index card**. The vault is the **shelf**. Never two copies drifting apart.

---

## The library model (check-in / check-out)

Dewey treats memory like a real library so it **balances itself**:

- 📚 **Vault = the shelves** — the one canonical copy of every book.
- 🪑 **Each silo = a borrower's desk** — small, holds only what's checked out.
- 🪪 **`memory.md` = the library card** — it lists which books this Claude has out.

### Two shelves: is it fact, or is it an idea?

Like a real library, every book is shelved by **fiction vs non-fiction** *first*, then by subject:

- **Non-Fiction** = it's **real / true / shipped** (e.g. "EFCV chat v1.1 shipped", "screenshots live in the Screenshots folder").
- **Sci-Fi** = it's an **idea, not real yet** (e.g. "Ruby 3D talking head", "Minecraft-AR app", "Jarvis-automated home").

…then the Dewey subject number (000–900) within the shelf. A *biology project* sits in Non-Fiction if it's
factual, Sci-Fi if it's a concept. **When a Sci-Fi idea ships, the librarian re-shelves it into Non-Fiction** —
that's how `project_X` graduates to `project_X-shipped`.

```
dewey checkout 200,300 --to <silo>   # load those call-numbers into the silo Claude reads
dewey checkin <silo>                 # push edits to the shelf, bump version, leave a pointer stub
dewey balance                        # find the freshest copy of each fact, make the vault canonical,
                                     #   re-stub stale duplicates → drift heals itself
```

Every book carries its catalogue card in front-matter:

```yaml
call: 400.12              # Dewey subject number
shelf: sci-fi             # non-fiction (real) | sci-fi (idea)
version: 3
checked_out_to: [hermes-cain-abel]   # which silos hold a copy
due: 2026-06-17           # when a borrowed copy goes stale
last_checkin: 2026-06-10
shipped:                  # set this date → idea graduates to Non-Fiction
```

**Overdue books:** a copy that sat in a silo past its `due` date is stale. `dewey balance` is the librarian's
round — it reclaims overdue copies (checks them back in), re-shelves shipped ideas, and makes the vault canonical.
A Claude reads its `memory.md` card, **checks out** the books it needs for context, and **returns them when overdue.**

---

## Commands

| Command | Status | What it does |
|---|---|---|
| `dewey sweep` | ✅ working | Find every memory silo across `~/.claude` and count it |
| `dewey log` | ✅ working | Captain's Log: every memory by stardate (oldest→newest) |
| `dewey doctor [root]` | ✅ working | Scan git repos for **`.env` leaks** + `.gitignore` gaps (no secrets printed) |
| `dewey checkout` | 🛠️ planned | Load Dewey call-numbers into a silo |
| `dewey checkin` | 🛠️ planned | Sync a silo back to the vault, leave pointer stubs |
| `dewey balance` | 🛠️ planned | Self-healing reconcile across all silos + vault |
| `dewey sync` | ✅ working | Shelve memory into a browsable Markdown library (secret-aware, dry-run) |

---

## The Reference Desk — the Librarian (planned AI / MCP layer)

The MCP layer gives Dewey a face: a Librarian at the desk you can just *ask*.

```
You:       "Hi, I'm looking for Ivon's work on eyewear — what can you show me?"
Librarian: "I have several books: Waka.Ai, Ruby.Ai, and Eyewear-OEM.
            Would you like to check those out?"
```

Behind the desk: your natural-language question runs a semantic lookup over the Dewey catalogue
(call-numbers + shelves + titles), and the Librarian offers to **check out** only the books you
need — loading those few pointers into the silo Claude reads, then checking them back in when
you're done. Ask for a topic, get the right few books — not the whole library dumped into context.

## Companions & roadmap

Dewey (the library) is meant to run with two helpers:

- 🤖 **n8n Librarian** — an automated nightly round on the Mother Ship (n8n cron) that runs
  `dewey balance`: reclaims overdue books, re-shelves shipped ideas, keeps the vault canonical.
- 🗄️ **The Archivist** — works with the Librarian so **forgotten dreams have a place**. A Sci-Fi
  book that goes overdue and is never checked out again isn't deleted — it's moved to a
  **"Forgotten Dreams" archive shelf**, preserved, ready to be rediscovered.

> Nothing is ever lost. Ideas that fade are archived, not binned — a dream can always be checked out again.

## Security stance (read before sharing)

- **Ships code only — never your data.** Your memory + `.env` files stay local; `.gitignore` excludes them.
- `dewey doctor` **finds** leaks (tracked `.env`, missing ignore rules) — it never prints secret values.
- Before open-sourcing, run it through a sanitizer pass. The tool helps *others* find their leaks too.

## Install

See **[SETUP.md](SETUP.md)** for the full guide. Quickest path (global command):

```
pipx install git+https://github.com/ivonharris-cyber/dewey
dewey --version
dewey sweep
```
