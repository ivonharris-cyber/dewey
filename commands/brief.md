---
description: Re-pull the Dewey session brief (STATE + top memory pointers) to reorient mid-session
---

Reorient from the Dewey brain:

1. Call `mcp__dewey__session_state` to pull the current brief — canonical STATE plus top memory pointers (this mirrors what the SessionStart hook injects at launch).
2. Present it tight: current project + last shipped, open loops as a short list, and only the pointers relevant to what we're working on right now.
3. If the STATE looks stale versus what has happened THIS session, flag the drift and offer to update it via the wrap-up (`/checkin`).
