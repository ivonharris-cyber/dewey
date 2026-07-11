# Setup

Dewey is a **Python** tool — *not* npm/Node. You need **Python 3.9+** and (for `doctor`) `git`.

## Install — global command (recommended)

`pipx` gives you a clean, isolated, global `dewey` command:

```bash
pipx install git+https://github.com/ivonharris-cyber/dewey
```

No pipx yet? Install it once:

```bash
python -m pip install --user pipx
python -m pipx ensurepath        # then restart your terminal
```

## Install — with pip

```bash
pip install git+https://github.com/ivonharris-cyber/dewey
```

## Install — from source (for hacking on it)

```bash
git clone https://github.com/ivonharris-cyber/dewey
cd dewey
pip install -e .
```

## Check it worked

```bash
dewey --version
dewey sweep
```

If `dewey` isn't found, your Python scripts directory isn't on `PATH`. Either run
`pipx ensurepath` (and reopen the terminal), or just use `python -m dewey ...` instead.

## What it's supposed to look like

```text
$ dewey sweep
16 memory silos, 452 files

  [project] C--Users-ivonh                      351
  [project] C--Windows-system32                  31
  ...

$ dewey doctor ~/projects
Scanning git repos under /home/you/projects for .env leaks (no secrets read)
0 repo(s) need attention.

$ dewey sync --to ~/dewey-library          # dry-run — shows what would shelve
Library target: /home/you/dewey-library
  430 books to shelve · 22 skipped (sensitive)

$ dewey sync --to ~/dewey-library --apply  # writes the library + an index
[ok] Shelved 430 books into /home/you/dewey-library
```

`sync` is **secret-aware** (skips anything named like a credential) and **dry-run by default** —
it never moves or deletes your originals; it copies into the library you point it at.
Point Obsidian at that folder, or import it into Notion, to read every book.

## Shrink, then borrow back (v0.2)

Once a library exists, cluster it, shrink the silos to pointers, and pull any entry
back on demand:

```bash
dewey weave --to ~/dewey-library                  # cluster + colour the library (Obsidian)
dewey micronise --library ~/dewey-library         # dry-run — shows the size saved
dewey micronise --library ~/dewey-library --apply # replace silo files with pointers

dewey checkout project_foo.md                          # restore one entry to full content
dewey checkin  project_foo.md --library ~/dewey-library # sync edits back, then re-shrink
```

`MEMORY.md` (the index your assistant loads each session) is **never** shrunk. Every
`--apply` writes a recovery log, and `checkout` is the clean reverse of `micronise`.

## Reference Desk MCP (optional, v0.3)

Let an assistant query the library natively instead of loading everything:

```bash
pip install "dewey[mcp]"
```

Register it with Claude Code (user scope), pointing it at your library:

```bash
claude mcp add -s user dewey --env DEWEY_LIBRARY="<your library dir>" -- dewey-mcp
```

Then reload Claude. Tools: `search`, `read_entry`, `catalogue`, `checkout`, `checkin`.

## Connectors & Keys hub (optional, v0.8)

The engine behind the 007 Dash bottom‑left tool — subscriptions, the Google‑Drive BCP backup, the MCP
catalogue, and the honest key vault. It reads your `.env` files only to report **set/missing** (never a
value).

```bash
dewey connectors state --json      # the panel's data (booleans only, no secret values)
dewey connectors keys              # ✓/✗ per service
dewey connectors spend             # $/mo total from ~/.dewey/expenses.csv
dewey connectors setcost anthropic --cost 20
dewey connectors mcp list          # catalogue, sorted by popularity
dewey connectors bcp status        # your rclone Google‑Drive backup connector
```

The optional **encrypted key vault** (fernet) adds a passphrase‑unlocked store with per‑use approval:

```bash
pip install "dewey[vault]"
dewey connectors vault import       # encrypt your env keys into ~/.dewey/vault.enc (0600)
dewey connectors key ANTHROPIC_API_KEY --for "Bonita chat"   # unlock + approve → releases once
```

`vault.enc` and `expenses.csv` live in `~/.dewey/` and are git‑ignored — no secret ever enters the repo.
