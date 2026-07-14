#!/usr/bin/env bash
# SessionStart hook — inject the IVON PROTOCOL + the canonical STATE (dewey) into
# context every session, so the assistant opens knowing where things stand.
#
# Upgrade of the reminder-only hook: it now also loads `dewey state` (one truth).
# Safe by design: if dewey/STATE are unavailable it still emits the protocol alone,
# and it always prints exactly one valid JSON object.
#
# Config via env (with sane defaults):
#   DEWEY_LIBRARY  the synced library to read STATE from
#   DEWEY_REPO     the dewey source checkout (so `python -m dewey` runs the latest)
#   PYTHON         the python interpreter to use
LIB="${DEWEY_LIBRARY:-D:/AI/obsidian-vault/brain/Memory}"
REPO="${DEWEY_REPO:-D:/Projects/dewey}"
PY="${PYTHON:-python}"

PROTOCOL="IVON PROTOCOL (enforced, per ~/.claude/CLAUDE.md). 1) MEMORY FIRST: load context from the VRAIN via mcp__dewey__search/ask BEFORE planning. Canonical memory = D:/AI/obsidian-vault/brain/Memory, routed through 00-INDEX; per-launch memory = thin pointers only; NEVER create a parallel index. 2) PAPER TRAIL: before finishing, commit durable learnings via Dewey checkin AND push the artifact to Notion. 3) NO QUICK WINS: generate Plan.MD in the project root for complex tasks; do research via Perplexity/deep-research and SAVE findings to disk. 4) Be agentic — act, do not ask the user to point you to things that live in the brain or infra table. Verify before claiming done."

STATE="$(cd "$REPO" 2>/dev/null && PYTHONPATH="$REPO" "$PY" -m dewey state --to "$LIB" 2>/dev/null)"

"$PY" - "$PROTOCOL" "$STATE" <<'PY'
import json, sys
protocol, state = sys.argv[1], sys.argv[2]
ctx = protocol
if state.strip():
    ctx += "\n\nSTATE (dewey — the one truth, read first):\n" + state.strip()
print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ctx}}))
PY
