#!/usr/bin/env bash
# SessionStart hook — injects Ivon's enforced protocol + the CURRENT TIME + the
# live Dewey brief (STATE + top memory pointers) so every session opens
# ready-to-go, not cold.
#
# Fail-open by design: if `dewey brief` is slow, missing, or errors, we still
# emit the protocol + time (no regression, ever). Every fire is logged to
# dewey-brief.log so we can VERIFY it worked, not guess.
#
# Leeloo upgrade — Cycle 1 (feat/leeloo-1-inject). Hardened 2026-07-23:
#   * Windows `timeout.exe` was hijacking `timeout` and killing the brief on
#     redirected stdin -> only the protocol got injected. Now we only use
#     `timeout` when it is GNU coreutils; otherwise run Python directly.
#   * Inject current local date/time.
#   * Log each fire (brief length + outcome) for evidence.

PROTO='IVON PROTOCOL (enforced, per ~/.claude/CLAUDE.md). 1) MEMORY FIRST: load context from the VRAIN via mcp__dewey__search BEFORE planning. Canonical memory = D:/AI/obsidian-vault/brain/Memory, routed through 00-INDEX; per-launch memory = thin pointers only; NEVER create a parallel index. 2) PAPER TRAIL: before finishing, commit durable learnings via Dewey checkin AND push the artifact to Notion. 3) NO QUICK WINS: generate Plan.MD in the project root for complex tasks; do research via Perplexity/deep-research and SAVE findings to disk. 4) Be agentic — act, do not ask the user to point you to things that live in the brain or infra table. Verify before claiming done.'

LIB="D:/AI/obsidian-vault"
LOG="/c/Users/ivonh/.claude/hooks/dewey-brief.log"

# --- resolve a working python (hardcoded path first, then PATH) ---
PY="C:/Python314/python.exe"
if [ ! -x "$PY" ] && ! command -v "$PY" >/dev/null 2>&1; then
  if command -v python >/dev/null 2>&1; then PY="python"
  elif command -v python3 >/dev/null 2>&1; then PY="python3"
  fi
fi

# --- current local time (e.g. "Thu 2026-07-23 17:30 NZST") ---
NOW="$(date '+%a %Y-%m-%d %H:%M %Z' 2>/dev/null)"

# --- pull the live brief; only trust `timeout` if it is GNU coreutils ---
# (Windows timeout.exe has no --version and breaks on redirected stdin.)
if timeout --version >/dev/null 2>&1; then
  BRIEF="$(timeout 25 "$PY" -m dewey brief --to "$LIB" 2>>"$LOG" || true)"
else
  BRIEF="$("$PY" -m dewey brief --to "$LIB" 2>>"$LOG" || true)"
fi
BRIEF="$(printf '%s' "$BRIEF" | sed -e 's/[[:space:]]*$//')"

# --- log the outcome so the next session can confirm this fired ---
{
  if [ -n "$BRIEF" ]; then
    echo "[$NOW] brief OK — ${#BRIEF} chars injected"
  else
    echo "[$NOW] brief EMPTY — protocol+time only (check python/lib/dewey)"
  fi
} >>"$LOG" 2>/dev/null

# --- merge protocol + time + brief into one json-escaped additionalContext ---
if ! PROTO="$PROTO" NOW="$NOW" BRIEF="$BRIEF" "$PY" - <<'PY'
import json, os
proto = os.environ.get("PROTO", "")
now   = os.environ.get("NOW", "").strip()
brief = os.environ.get("BRIEF", "").strip()
parts = [proto]
if now:
    parts.append("CURRENT TIME: " + now)
if brief:
    parts.append(brief)
ctx = "\n\n".join(parts)
print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ctx}}))
PY
then
  # Hard fallback: protocol only, never break startup.
  cat <<'JSON'
{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"IVON PROTOCOL (enforced, per ~/.claude/CLAUDE.md). 1) MEMORY FIRST: load context from the VRAIN via mcp__dewey__search BEFORE planning. Canonical memory = D:/AI/obsidian-vault/brain/Memory, routed through 00-INDEX; per-launch memory = thin pointers only; NEVER create a parallel index. 2) PAPER TRAIL: before finishing, commit durable learnings via Dewey checkin AND push the artifact to Notion. 3) NO QUICK WINS: generate Plan.MD in the project root for complex tasks; do research via Perplexity/deep-research and SAVE findings to disk. 4) Be agentic — act, do not ask the user to point you to things that live in the brain or infra table. Verify before claiming done."}}
JSON
fi
