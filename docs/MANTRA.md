# The Dewey mantra

> **Recall before you act. Make memory smaller, not heavier. Never lose anything.**

Dewey is a librarian, not a hoarder. Its whole reason to exist is that a growing pile
of `.md` memory drowns an assistant in tokens and drift. So every Dewey reflex bends
toward the same shape:

## 1. Recall before you act
Before a non-trivial task, ask your past self — `dewey ask "<keywords>"` — and surface
what connects. Past ideas are gifts; past mistakes are lessons, applied forward, never
re-litigated. See the [`self-reflect`](../skills/self-reflect/SKILL.md) skill: this is
the *read* half of the loop.

## 2. Make memory smaller, not heavier
The point of remembering is to be **sharper, not fatter**. Full content lives once, in
the library; everywhere else carries a small Dewey-decimal **pointer** to it. A pointer
is a promise: "the real thing is on this shelf, fetch it when you actually need it."

- `dewey brief` injects STATE + the few relevant *pointers* at session start — never bodies.
- `dewey micronise` / `dewey autostub` collapse shelved files back to pointers.
- `dewey checkout` rehydrates a pointer to full content on demand; `checkin` re-shrinks it.

**Autostub is this mantra made automatic.** When a silo file grows during a session and
its content is already safely shelved (byte-identical) in the library, it collapses back
to a pointer on its own — typically from a Stop hook at session end. Nothing is ever
lost: only byte-identical content is stubbed, `MEMORY.md` is never touched, and every
run writes a recovery log (`~/.dewey-micronise-recovery.md`).

## 3. Never lose anything
Smaller is not the same as gone. Content moves to the shelf, it is never deleted.
Overdue "Sci-Fi" ideas go to a *Forgotten Dreams* archive, not the bin. Dry-run is the
default for anything destructive; every collapse is reversible from its recovery log.

---

*The Leeloo loop:* **inject → act → capture → auto-stub.** `brief` injects the brain at
launch; you act; new knowledge is captured (research / OCR / image intake); `autostub`
returns grown memory to pointers so the next session starts light again.
