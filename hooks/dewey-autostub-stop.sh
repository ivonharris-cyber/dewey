#!/usr/bin/env bash
# Example Stop hook — the auto-stubbing mantra at session end (OPT-IN).
#
# Copy this into your Claude Code hooks dir (e.g. ~/.claude/hooks/) and register it
# as a Stop hook in settings.json. On each session end it:
#   1) shelves the session's memory into the library (`dewey sync --apply`), then
#   2) collapses grown, already-synced silo files back to pointers (`dewey autostub --apply`).
#
# Safe + reversible: only byte-identical content is ever stubbed, MEMORY.md is never
# touched, and every collapse writes ~/.dewey-micronise-recovery.md. Time-boxed and
# silent (logs to $LOG); never blocks Stop.
#
# Edit PY / LIB / LOG for your machine. settings.json wiring:
#   "Stop": [ { "hooks": [ { "type": "command",
#     "command": "bash /path/to/dewey-autostub-stop.sh", "shell": "bash" } ] } ]

PY="${DEWEY_PYTHON:-python}"
LIB="${DEWEY_LIBRARY:?set DEWEY_LIBRARY to your synced library dir}"
LOG="${DEWEY_AUTOSTUB_LOG:-$HOME/.claude/dewey-autostub.log}"

RUN() { if command -v timeout >/dev/null 2>&1; then timeout 60 "$@"; else "$@"; fi; }

{
  printf '\n%s autostub-stop\n' "$(date +%Y-%m-%dT%H:%M:%S)"
  RUN "$PY" -m dewey sync --to "$LIB" --apply 2>&1 | tail -2
  RUN "$PY" -m dewey autostub --library "$LIB" --apply 2>&1 | tail -3
} >> "$LOG" 2>&1

exit 0
