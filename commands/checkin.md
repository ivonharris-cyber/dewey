---
description: End-of-session Dewey wrap-up — sync checked-out entries and commit durable learnings to the VRAIN
argument-hint: [optional: specific entry name or learning to commit]
---

Run the Dewey wrap-up ritual. Focus: **$ARGUMENTS** (if empty, sweep the whole session).

1. Review this session for durable learnings — decisions made, state changes shipped, gotchas discovered. Skip anything the repo/git history already records.
2. For every library entry that was edited or checked out this session, call `mcp__dewey__checkin` with its name to sync edits back and re-shrink it to a pointer.
3. For NEW learnings with no existing entry: create the entry in the canonical library at `D:\AI\obsidian-vault\brain\Memory\` following its Dewey-decimal class conventions (300-agents / 400-projects / 500-reference), then route it through `D:\AI\obsidian-vault\00-INDEX.md`. NEVER create a parallel index.
4. Mask any secrets — raw keys/tokens never go into memory; point to `Master.env` instead.
5. Report back: which entries were checked in, which were created, and anything deliberately NOT saved (and why). Mantra: make memory smaller, not heavier.
