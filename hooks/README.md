# Dewey session hooks — the assisted one-truth loop

Two hooks make every session start from one truth and leave a paper trail. They are
**reference copies** — installing them is opt-in (they change how *every* Claude Code
session boots).

| Hook | Event | What it does |
|---|---|---|
| `ivon-session-start.sh` | SessionStart | Injects the IVON PROTOCOL **plus the canonical `dewey state`** (current project, last action, open loops) so the assistant opens knowing where things stand. |
| `ivon-paper-trail.sh` | Stop | Appends a timestamped marker and checks a dated session note was written today; logs a reminder if not. **Assisted — never blocks** (set `DEWEY_PAPERTRAIL_BLOCK=1` to make it a hard block). |

## Config (env vars, with defaults)

- `DEWEY_LIBRARY` — the synced library STATE is read from (default `D:/AI/obsidian-vault/brain/Memory`)
- `DEWEY_REPO` — the dewey checkout, so `python -m dewey` runs the latest (default `D:/Projects/dewey`)
- `PYTHON` — interpreter (default `python`)

## Install

Copy both scripts into `~/.claude/hooks/` and wire them in `~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [{ "hooks": [{ "type": "command", "shell": "bash",
      "command": "bash /c/Users/<you>/.claude/hooks/ivon-session-start.sh" }] }],
    "Stop":         [{ "hooks": [{ "type": "command", "shell": "bash",
      "command": "bash /c/Users/<you>/.claude/hooks/ivon-paper-trail.sh" }] }]
  }
}
```

Both are safe: SessionStart always emits exactly one valid JSON object (protocol alone if
STATE is unavailable); Stop always exits 0 unless you opt into `DEWEY_PAPERTRAIL_BLOCK=1`.

> Note: the live MCP server must be restarted after upgrading Dewey for the new
> `mcp__dewey__ask` / `build_graph` tools to appear.
