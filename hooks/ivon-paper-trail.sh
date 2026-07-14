#!/usr/bin/env bash
# Stop hook — the assisted paper trail. Appends a timestamped marker and checks that
# a dated session entry was written today; if not, it logs a clear reminder.
#
# ASSISTED, not enforced-hard: this never blocks the session (always exits 0). To turn
# it into a hard block, set DEWEY_PAPERTRAIL_BLOCK=1 and it will ask the assistant to
# write the check-in before stopping.
LOG="/c/Users/ivonh/.claude/ivon-paper-trail.log"
LIB="${DEWEY_LIBRARY:-D:/AI/obsidian-vault/brain/Memory}"
TODAY="$(date +%Y-%m-%d)"

printf '%s STOP cwd=%s\n' "$(date +%Y-%m-%dT%H:%M:%S)" "$(pwd)" >> "$LOG" 2>/dev/null

# Did a session note land today? (any *.md under the library modified today)
wrote_today=""
if [ -d "$LIB" ]; then
  wrote_today="$(find "$LIB" -name '*.md' -newermt "$TODAY 00:00:00" 2>/dev/null | head -1)"
fi

if [ -z "$wrote_today" ]; then
  printf '%s REMINDER no dated session entry written today — checkin + Notion still owed\n' \
    "$(date +%Y-%m-%dT%H:%M:%S)" >> "$LOG" 2>/dev/null
  if [ "${DEWEY_PAPERTRAIL_BLOCK:-0}" = "1" ]; then
    printf '{"decision":"block","reason":"Paper trail: write a dated session check-in (dewey checkin) and push it to Notion before stopping."}\n'
    exit 0
  fi
fi
exit 0
