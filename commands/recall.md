---
description: Search the Dewey VRAIN and load the entries that answer a question
argument-hint: <topic or question>
---

Recall from the Dewey VRAIN library: **$ARGUMENTS**

1. Call `mcp__dewey__ask` with the question above (it is graph-guided and sharper than raw search). If the question is just 1-2 bare keywords, use `mcp__dewey__search` instead (AND-of-terms).
2. From the returned pointers, call `mcp__dewey__read_entry` on the entries that actually answer the question (usually 1-3 — don't bulk-load).
3. If an entry is one we will clearly need again in FUTURE sessions (active project, ongoing loop), also call `mcp__dewey__checkout` on it so it loads full-fat next launch. Otherwise leave it shrunk — make memory smaller, not heavier.
4. Answer the question from what was recalled, citing entry names (e.g. `project_007-bond`). If nothing relevant comes back, say so plainly — never invent memory.
