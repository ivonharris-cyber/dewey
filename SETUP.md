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
