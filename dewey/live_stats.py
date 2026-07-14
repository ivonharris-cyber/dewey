"""Live session stats — measured from the transcripts, never a frozen cache.

The Claude Desktop app counts sessions / messages / tokens by reading the real
session transcripts (`~/.claude/projects/**/*.jsonl`). Dewey's dashboard was
reading `stats-cache.json`, which freezes (it last computed 2026-06-10) — so the
cockpit showed a month-old photograph as "today". This module measures the same
live source the app does, and its output mirrors the stats-cache shape exactly
so `dashboard.py` and `connectors.token_burn` consume it unchanged:

    lastComputedDate · dailyActivity[{date,messageCount,toolCallCount}]
    dailyModelTokens[{date,tokensByModel}] · modelUsage{model:{outputTokens}}
    totalSessions · totalMessages · firstSessionDate · hourCounts · source

Incremental: per-transcript summaries are cached by (mtime, size) in
`~/.claude/dewey-live-stats.json`, so only new/changed transcripts are
re-parsed. First full scan pays once; every later call is fast.

Honesty rules: everything here is COUNTED from the transcripts on disk —
nothing estimated, nothing carried over. `source` says exactly what was read.
Dependency-free (stdlib only).
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import core

CACHE_NAME = "dewey-live-stats.json"
# Sidechain transcripts (subagents) are files named agent-*.jsonl — they are work
# Claude spawned, not sessions Ivon opened. Counted separately, never as sessions.
_AGENT_PREFIX = "agent-"


def _summarise_file(path: Path) -> dict:
    """Parse ONE transcript into a small summary (the only expensive step; cached)."""
    days_msgs: dict[str, int] = defaultdict(int)
    days_tools: dict[str, int] = defaultdict(int)
    model_tokens: dict[str, int] = defaultdict(int)
    day_model_tokens: dict[str, dict] = defaultdict(lambda: defaultdict(int))
    day_hours: dict[str, dict] = defaultdict(lambda: defaultdict(int))  # per-day hour histogram
    messages = 0
    first_ts = last_ts = ""
    try:
        with path.open(encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                # cheap pre-filter: only user/assistant lines carry what we count
                if '"type":"user"' not in line and '"type":"assistant"' not in line \
                        and '"type": "user"' not in line and '"type": "assistant"' not in line:
                    continue
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(d, dict):
                    continue  # a bare array/string line is not a message record
                typ = d.get("type")
                if typ not in ("user", "assistant"):
                    continue
                ts = d.get("timestamp") or ""
                day, hour = ts[:10], ts[11:13]
                if ts:
                    first_ts = first_ts or ts
                    last_ts = ts
                messages += 1
                if day:
                    days_msgs[day] += 1
                    if hour:
                        day_hours[day][hour] += 1
                if typ == "assistant":
                    m = d.get("message")
                    if not isinstance(m, dict):
                        m = {}                       # `message` can be a raw string in some formats
                    usage = m.get("usage")
                    if not isinstance(usage, dict):
                        usage = {}
                    out_tok = usage.get("output_tokens", 0) or 0
                    model = m.get("model") or "unknown"
                    if out_tok:
                        model_tokens[model] += out_tok
                        if day:
                            day_model_tokens[day][model] += out_tok
                    content = m.get("content")
                    if isinstance(content, list) and day:
                        days_tools[day] += sum(1 for b in content
                                               if isinstance(b, dict) and b.get("type") == "tool_use")
    except OSError:
        return {}
    return {
        "messages": messages,
        "first_ts": first_ts,
        "last_ts": last_ts,
        "days_msgs": dict(days_msgs),
        "days_tools": dict(days_tools),
        "model_tokens": dict(model_tokens),
        "day_model_tokens": {d: dict(m) for d, m in day_model_tokens.items()},
        "day_hours": {d: dict(h) for d, h in day_hours.items()},
    }


def _load_cache(cache_path: Path) -> dict:
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def scan(claude_dir: Optional[Path] = None, *, use_cache: bool = True) -> dict:
    """Measure live stats from every transcript under claude_dir/projects.

    Returns a dict in the stats-cache shape (drop-in for dashboard/connectors),
    plus `source`/`transcripts`/`agentTranscripts` so the reader knows exactly
    what was measured. Returns {} only if the projects dir doesn't exist.
    """
    claude_dir = Path(claude_dir) if claude_dir else core.CLAUDE
    projects = claude_dir / "projects"
    if not projects.is_dir():
        return {}
    cache_path = claude_dir / CACHE_NAME
    cache = _load_cache(cache_path) if use_cache else {}
    entries = cache.get("files", {})
    fresh: dict[str, dict] = {}
    sessions = 0
    agent_files = 0

    for p in sorted(projects.rglob("*.jsonl")):
        try:
            st = p.stat()
        except OSError:
            continue
        rel = p.relative_to(projects).as_posix()
        is_agent = p.name.startswith(_AGENT_PREFIX)
        if is_agent:
            agent_files += 1
        cached = entries.get(rel)
        if cached and cached.get("mtime") == st.st_mtime and cached.get("size") == st.st_size:
            summary = cached.get("summary", {})
        else:
            summary = _summarise_file(p)
        fresh[rel] = {"mtime": st.st_mtime, "size": st.st_size, "summary": summary}
        if not is_agent and summary.get("messages"):
            sessions += 1

    # persist the incremental cache (best-effort; the numbers never depend on it)
    try:
        core._atomic_write(cache_path, json.dumps({"files": fresh}))
    except OSError:
        pass

    # aggregate
    days_msgs: dict[str, int] = defaultdict(int)
    days_tools: dict[str, int] = defaultdict(int)
    model_usage: dict[str, int] = defaultdict(int)
    day_model: dict[str, dict] = defaultdict(lambda: defaultdict(int))
    day_hours: dict[str, dict] = defaultdict(lambda: defaultdict(int))
    total_messages = 0
    first_ts = ""
    for rel, e in fresh.items():
        s = e.get("summary") or {}
        total_messages += s.get("messages", 0)
        ts = s.get("first_ts", "")
        if ts and (not first_ts or ts < first_ts):
            first_ts = ts
        for d, n in (s.get("days_msgs") or {}).items():
            days_msgs[d] += n
        for d, n in (s.get("days_tools") or {}).items():
            days_tools[d] += n
        for m, n in (s.get("model_tokens") or {}).items():
            model_usage[m] += n
        for d, mm in (s.get("day_model_tokens") or {}).items():
            for m, n in mm.items():
                day_model[d][m] += n
        for d, hh in (s.get("day_hours") or {}).items():
            for h, n in hh.items():
                day_hours[d][h] += n

    hours: dict[str, int] = defaultdict(int)
    for hh in day_hours.values():
        for h, n in hh.items():
            hours[h] += n
    daily_activity = [{"date": d, "messageCount": days_msgs[d], "toolCallCount": days_tools.get(d, 0)}
                      for d in sorted(days_msgs)]
    daily_model_tokens = [{"date": d, "tokensByModel": dict(day_model[d])} for d in sorted(day_model)]
    return {
        "source": "live-transcripts",           # measured NOW from ~/.claude/projects
        "lastComputedDate": datetime.now().strftime("%Y-%m-%d"),
        "transcripts": sessions,
        "agentTranscripts": agent_files,
        "totalSessions": sessions,
        "totalMessages": total_messages,
        "firstSessionDate": first_ts,
        "dailyActivity": daily_activity,
        "dailyModelTokens": daily_model_tokens,
        "modelUsage": {m: {"outputTokens": n} for m, n in
                       sorted(model_usage.items(), key=lambda kv: -kv[1])},
        "hourCounts": dict(hours),
        "dayHours": {d: dict(h) for d, h in day_hours.items()},  # per-day, so merge can respect the cutoff
    }


def merge_with_cache(live: dict, cache: dict) -> dict:
    """Live measurement + the frozen cache's pre-cutoff history. No double counting.

    Transcripts get pruned from disk, so a pure live scan under-counts history
    (e.g. only reaches back to mid-May). The frozen stats-cache legitimately
    recorded the days BEFORE it froze. Rule: cache owns days <= its
    lastComputedDate, live owns every day after. Cumulative totals = cache
    totals + live activity strictly after the cutoff. `source` says exactly
    what was combined; if either side is missing, the other passes through.
    """
    if not cache:
        return live
    if not live:
        out = dict(cache)
        out["source"] = f"frozen-cache-only(as-of {cache.get('lastComputedDate', '?')})"
        return out
    cutoff = cache.get("lastComputedDate", "")

    daily_activity = ([d for d in cache.get("dailyActivity", []) if d.get("date", "") <= cutoff]
                      + [d for d in live.get("dailyActivity", []) if d.get("date", "") > cutoff])
    daily_activity.sort(key=lambda d: d.get("date", ""))
    daily_model = ([d for d in cache.get("dailyModelTokens", []) if d.get("date", "") <= cutoff]
                   + [d for d in live.get("dailyModelTokens", []) if d.get("date", "") > cutoff])
    daily_model.sort(key=lambda d: d.get("date", ""))

    model_usage: dict[str, int] = defaultdict(int)
    for m, v in (cache.get("modelUsage") or {}).items():
        model_usage[m] += (v or {}).get("outputTokens", 0)
    for d in live.get("dailyModelTokens", []):
        if d.get("date", "") > cutoff:
            for m, n in (d.get("tokensByModel") or {}).items():
                model_usage[m] += n

    live_msgs_after = sum(d.get("messageCount", 0)
                          for d in live.get("dailyActivity", []) if d.get("date", "") > cutoff)
    firsts = [x for x in (cache.get("firstSessionDate", ""), live.get("firstSessionDate", "")) if x]

    # hourCounts: the cache owns the pre-cutoff distribution (complete up to when it froze);
    # add ONLY the live hours from days strictly after the cutoff, so overlapping old
    # transcripts still on disk are not double-counted.
    hours: dict[str, int] = defaultdict(int)
    for h, n in (cache.get("hourCounts") or {}).items():
        hours[str(h).zfill(2)[:2]] += n
    for day, hh in (live.get("dayHours") or {}).items():
        if day > cutoff:
            for h, n in hh.items():
                hours[str(h).zfill(2)[:2]] += n

    return {
        "source": f"live-transcripts + frozen-cache(<= {cutoff})",
        "lastComputedDate": live.get("lastComputedDate", ""),
        "transcripts": live.get("transcripts", 0),
        "agentTranscripts": live.get("agentTranscripts", 0),
        # sessions: definitions differ between the app and the cache — we report the
        # on-disk measured count, never the frozen cache's smaller stale figure.
        "totalSessions": max(live.get("totalSessions", 0), cache.get("totalSessions", 0)),
        "totalMessages": cache.get("totalMessages", 0) + live_msgs_after,
        "firstSessionDate": min(firsts) if firsts else "",
        "dailyActivity": daily_activity,
        "dailyModelTokens": daily_model,
        "modelUsage": {m: {"outputTokens": n} for m, n in
                       sorted(model_usage.items(), key=lambda kv: -kv[1])},
        "hourCounts": dict(hours),
    }


def measured(claude_dir: Optional[Path] = None) -> dict:
    """The one call sites use: live scan merged with the frozen cache's history."""
    claude_dir = Path(claude_dir) if claude_dir else core.CLAUDE
    live = scan(claude_dir)
    try:
        cache = json.loads((claude_dir / "stats-cache.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    return merge_with_cache(live, cache)
