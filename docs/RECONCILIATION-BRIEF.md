# Brain Reconciliation — Seed Brief

> Seed for `/ultraplan`. Captures ground truth + locked decisions so the planner
> starts from fact, not a blank prompt. Authored 2026-06-14 (Pacific/Auckland).

## The problem in one line

Memory has **forked into multiple live, diverging stores** created at different
dates. Goal: re-write them into a **single point of truth that preserves history**
(newest→oldest traversal, keep the trail of how each thought evolved).

## Ground truth (scouted 2026-06-14)

Two full stores, both live, already diverging:

| Store | Files | Last write | Role |
|---|---|---|---|
| Claude silo `C:\Users\ivonh\.claude\projects\C--Users-ivonh\memory` | 358 MD | 2026-06-13 | Auto-written every CC session |
| VRAIN brain `D:\AI\obsidian-vault\brain\Memory` | 480 MD | 2026-06-14 | **Declared canonical** |

Plus the scatter:
- **12 separate `MEMORY.md` brains** — 5 Claude project silos (`C--Users-ivonh`,
  `C--Windows-system32`, `D--`, `D--Projects`, `hermes-cain-abel`) + 7 agent silos
  (bonita, cyber-hustler, infra-keymaster, ivon-ceo, kali-ops, seo-scraping,
  upgrade-manager).
- Each silo **mirrored again** into VRAIN `brain/Memory/000-meta` by Dewey on
  2026-06-10.
- **3 fossil copies** buried in project repos: `gokrazy`, `KiaOraFM`,
  `manametamaori` (old `.claude/agent-memory/...`).

## Diagnosis

Dewey's 2026-06-10 migration **copied, it did not stitch** — VRAIN brain was born
that day. The silos were never turned off, so Claude Code keeps writing them every
session. Result: two full stores diverging (358 vs 480, three days apart), not one
truth with history.

**Implication:** a one-time re-write closes today's gap but won't hold. The cure is
two-part — **(1) reconcile once, then (2) govern** so silos can't fork again. The
governance half is already declared in `~/.claude/CLAUDE.md` ("silos are thin
pointers, not the brain") but **nothing enforces it**.

## Locked decisions

1. **Canonical target = VRAIN brain** (`D:\AI\obsidian-vault\brain\Memory`).
   Silos collapse into it and become thin pointers.
2. **Conflict policy = flag every contradiction for Ivon.** The machine
   auto-merges *only* exact duplicates. Every genuine contradiction is queued for
   human arbitration — no silent newest-wins, no guessing. (Mirrors the prior
   `micronise --apply` block: never auto-apply unverified merges.)
3. **Engine = Dewey**, this repo. Cure tooling lives here.

## Existing tooling (work in progress, this repo)

Already started on `main` (uncommitted as of 2026-06-14):
- `tests/test_consolidate.py`, `tests/test_merge.py`, `tests/test_scrub.py`
- modified `dewey/cli.py`, `dewey/core.py`

`consolidate + merge + scrub` ≈ the reconciliation pipeline. The plan should build
on these, not replace them.

## What the plan needs to produce

1. **Inventory pass** — enumerate every store/entry with timestamp + provenance
   (source path, created/modified date).
2. **Semantic matching** — group entries that are about the same subject (Dewey
   search). This is the hard part and the make-or-break for "single truth" vs
   "pile of near-duplicates".
3. **Reconciliation pass (dry-run first)** — newest→oldest traversal; auto-merge
   exact dupes; **emit a conflict queue** for everything else. Apply nothing until
   Ivon reviews.
4. **Provenance/history** — every canonical entry keeps a dated trail of prior
   versions (not discarded).
5. **Governance** — enforce silos-as-thin-pointers going forward (hook or sync
   job) so the fork cannot reopen. Without this the whole exercise decays.

## Guardrails (from Ivon's standing rules)

- Plan before any irreversible/destructive step; surface options and WAIT for "go".
- Dry-run + human review before `--apply`. No silent truncation — log what's dropped.
- Never write secrets into vault/memory notes (metadata + pointers only).
- Verify against the live file before asserting a memory as fact (memories are
  point-in-time).
- Compare-before-create: update canonical entries, don't fork them.

## Open questions for the planner

- How to dedupe the **12 `MEMORY.md` indexes** vs the 480 entry files — are indexes
  reconciled separately from content?
- Fate of the 3 **fossil copies** in project repos — fold in, or archive + delete?
- Governance mechanism: a CC **hook** (PostToolUse on memory writes) vs a scheduled
  **sync job** that flattens silos into pointers?
- Agent silos (7) — do they reconcile into the same canonical brain or stay
  per-agent with pointers up to it?
