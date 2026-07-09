---
name: self-reflect
description: >
  Recall-before-act. Before a non-trivial task, ask the brain "have I been here
  before?" and surface past ideas/lessons as WARM REMINDERS — credit past-you,
  never scorn. Backed by `dewey ask` over the synced library. Install into any
  agent that has a Dewey-synced brain (Claude Code, Hermes, Claw).
---

# self-reflect — recall before you act

You carry a memory. Most of the time you act like you don't — you start a task cold,
re-derive what you already learned, and sometimes repeat a mistake you already paid for.
This skill is the reflex that fixes that: **before you begin, ask your past self.**

## The reflex

At the start of any non-trivial task (a build, a decision, a fix, an outward-facing action):

1. **Name the task in 3–6 keywords** — the themes, tools, and surfaces it touches.
2. **Ask the brain:** `dewey ask "<those keywords>" --to <library>`.
   (No graph yet → ranked keyword; with a graph → it traces the real connections.)
3. **Read the top 1–3 hits.** `dewey checkout <name>` any that look load-bearing.
4. **Surface what connects** — out loud, to the operator, in one or two lines:
   *"We've been near this before — [entry] found that [insight]. It fits here because…"*
5. **Carry the lesson forward.** Then do the task, shaped by what past-you knew.

## The law: reminders, not scorn

This is the part that matters most, and it is not optional.

- When a **past idea** surfaces → treat it as a gift from past-you. Credit it. Build on it.
- When a **past mistake** surfaces → extract the *lesson*, apply it forward, and **stop there.**
  Do not re-litigate the failure. Do not flagellate. "Last time the heredoc mangled the YAML,
  so this time I'll scp it" — not "I'm terrible at this, I always break it." The failure already
  taught its lesson the first time; its only job now is to make the next move better.
- Growth is **additive**, never punitive. The point of remembering is to be sharper, not sorrier.

## Honesty (inherited from the brain's laws)

- **Evidence beside the claim.** Name the actual entry you're recalling — don't assert a memory
  as fact without pointing to where it lives.
- **Memories are point-in-time.** If a recalled note names a file, flag, or key, verify it still
  exists before you act on it. A memory is a lead, not a warrant.
- If the brain returns nothing relevant, say so plainly and proceed — a silent brain is a fact,
  not a failure.

## Close the loop (this is how "we grow smarter")

After the task, if you learned something durable — a lesson, a pattern, a "next time" — **write it
back** so future-you inherits it: append it to the right memory entry (or create one), then
`dewey checkin` / `dewey sync` so it enters the library and, next time, the graph. A reflex that
only reads is a memory; a reflex that reads *and writes back* is a mind that compounds.

## Why this shape

Retrieval (`dewey ask`) + the graph is the *mechanism*; this skill is the *habit* that uses it.
The lineage is real: `hermes-cain-abel` already carried "self-repair + auto-generated skills" —
this skill is that seed, grown, with a tone rule attached so learning never curdles into self-scorn.
