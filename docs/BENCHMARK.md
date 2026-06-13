<p align="center">
  <img src="../assets/dewey-mascot.webp" width="120" alt="Dewey">
</p>

# Benchmark: a 2.9 MB memory, and the ~800 tokens that answered the question

*Roadmap item from the README — "a measured token benchmark, the same task on raw vs. Dewey-pointered memory" — measured on a real personal estate, 2026-06-13.*

A coding assistant's working memory is capped by its context window (here, 200,000 tokens). Personal notes are not. Left alone for a few months, mine grew past the point where the whole thing could ever be loaded at once. This is the measurement of what that costs — and what asking a *librarian* instead of loading *everything* costs instead.

## The estate (raw)

Counted directly off disk: every `.md` across the Claude Code silos plus the canonical Obsidian library.

| Store | Files | Size |
|---|---:|---:|
| Claude Code silos (`.claude/projects/*/memory`) | 425 | 1,409 KB |
| Canonical library (`brain/Memory`, Dewey-classed) | 460 | 1,599 KB |
| **Total memory corpus** | **885** | **2.94 MB** |

At ~4 characters per token that's **≈770,000 tokens** — **3.9× larger than the 200,000-token window**. You physically cannot hold this brain in one session. The only question is how you choose what to leave out.

## The question

A real one, asked of the library through the `dewey-mcp` reference desk (read-only `search`):

> **"What do I have for a car app that does visual recognition?"**

## The result

- **Surfacing the right shelf.** One `search` returned the relevant entries — as call numbers plus one-line summaries — in **≈800 tokens** of index. That is **~960× lighter** than holding the 770K-token estate, before reading a single full note.
- **Reading the chosen entries.** Pulling the three most relevant notes in full adds a few KB more, on demand. Still a rounding error against 770K, and **lossless** — `checkout` restores any entry to full content.
- **Accuracy.** Nothing was hand-picked. The search returned the drive-vision detector, face and pet recognition, the live-vision phone link, *and* the night-vision branch (`CAT S62 FLIR thermal camera`). The whole thread, surfaced from one question.

## A finding the librarian surfaced for free

The same project was filed under **three different names**, and the library made the duplication visible at a glance:

- `project_ruby-driver` records it was *"renamed from **kitt-hapai-remix** → ruby-driver"*
- the ElevenLabs entry is labelled *"**KITT voice** (William Daniels-grade)"* — the actor who voiced KITT in *Knight Rider*
- `kitt.html` / `kitt-api.php` were *ported into* the WAKA app

**KITT → Ruby → WAKA — one idea, three labels.** A flat folder of 885 files hides that. A classified, queryable library shows it, which is exactly what you need before you consolidate three half-built versions into one.

## The shrink

Once classified, the silos collapse to pointers:

| | Before | After | Saved |
|---|---:|---:|---:|
| Silo footprint (`micronise`) | ~1.4 MB | ~123 KB | **~91%** |

The full content stays in the library; pointers carry a call number, a summary, and a link. The shrink is reversible (`checkout --all`), and `MEMORY.md` — the index loaded every launch — is never shrunk.

## Numbers at a glance

| Metric | Value |
|---|---:|
| Files in corpus | 885 |
| Corpus size | 2.94 MB |
| Corpus tokens (est.) | ~770,000 |
| Context window | 200,000 |
| Overflow | 3.9× |
| Index to answer one question | ~800 tokens |
| Context reduction (surfacing) | ~960× |
| Silo shrink (`micronise`) | ~91% |
| Loss | none (reversible) |

## Method & reproduce

- Measured 2026-06-13 on Windows. Sizes via direct file enumeration; tokens estimated at 4 chars/token (a standard rough conversion — treat as an estimate, not an exact tokeniser count).
- Retrieval run read-only through `dewey-mcp` (`search`), no files modified.

```bash
# point the reference desk at your library
DEWEY_LIBRARY=/path/to/brain/Memory dewey-mcp
# then, from the assistant:
#   search "vision"   ->  the shelf of relevant entries
#   read_entry NAME   ->  the one note you actually need
```

The point isn't the exact multiplier — it's the shape. Memory grows without bound; context does not. Ask the librarian; don't carry the library.
