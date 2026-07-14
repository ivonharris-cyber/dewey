"""live_stats: measured from transcripts, merged with frozen-cache history — never a stale lie."""
import json
import tempfile
import unittest
from pathlib import Path

from dewey import live_stats


def _line(typ, ts, model=None, out=0, tools=0):
    d = {"type": typ, "timestamp": ts, "isSidechain": False}
    if typ == "assistant":
        content = [{"type": "tool_use", "id": f"t{i}"} for i in range(tools)]
        d["message"] = {"model": model or "claude-opus-4-8",
                        "usage": {"output_tokens": out}, "content": content}
    else:
        d["message"] = {"role": "user", "content": "hi"}
    return json.dumps(d)


class LiveStats(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.claude = Path(self._tmp.name)
        proj = self.claude / "projects" / "D--demo"
        proj.mkdir(parents=True)
        (proj / "aaaa-session.jsonl").write_text("\n".join([
            _line("user", "2026-07-01T09:00:00Z"),
            _line("assistant", "2026-07-01T09:00:05Z", out=100, tools=2),
            _line("user", "2026-07-02T10:00:00Z"),
            _line("assistant", "2026-07-02T10:00:05Z", out=50),
        ]) + "\n", encoding="utf-8")
        # a subagent transcript: its work counts, but it is NOT a session Ivon opened
        (proj / "agent-bbbb.jsonl").write_text(
            _line("assistant", "2026-07-01T09:01:00Z", out=25) + "\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_scan_measures_the_transcripts(self) -> None:
        s = live_stats.scan(self.claude)
        self.assertEqual(s["source"], "live-transcripts")
        self.assertEqual(s["totalSessions"], 1)          # agent transcript ≠ a session
        self.assertEqual(s["agentTranscripts"], 1)
        self.assertEqual(s["totalMessages"], 5)          # 4 main + 1 agent
        self.assertEqual(len(s["dailyActivity"]), 2)     # two distinct days
        tok = sum(m["outputTokens"] for m in s["modelUsage"].values())
        self.assertEqual(tok, 175)                       # 100 + 50 + 25, counted not guessed
        self.assertEqual(s["dailyActivity"][0]["toolCallCount"], 2)

    def test_incremental_cache_gives_same_numbers(self) -> None:
        first = live_stats.scan(self.claude)
        second = live_stats.scan(self.claude)             # served from the per-file cache
        self.assertEqual(first["totalMessages"], second["totalMessages"])
        self.assertEqual(first["modelUsage"], second["modelUsage"])

    def test_merge_no_double_counting(self) -> None:
        live = live_stats.scan(self.claude)
        cache = {  # a frozen cache that recorded history up to 2026-06-30
            "lastComputedDate": "2026-06-30",
            "totalSessions": 10, "totalMessages": 1000,
            "firstSessionDate": "2026-04-11T00:00:00Z",
            "dailyActivity": [{"date": "2026-06-29", "messageCount": 7, "toolCallCount": 1}],
            "dailyModelTokens": [{"date": "2026-06-29", "tokensByModel": {"claude-opus-4-8": 500}}],
            "modelUsage": {"claude-opus-4-8": {"outputTokens": 500}},
        }
        m = live_stats.merge_with_cache(live, cache)
        # cumulative = cache history + live activity strictly AFTER the cutoff
        self.assertEqual(m["totalMessages"], 1000 + 5)
        self.assertEqual(m["modelUsage"]["claude-opus-4-8"]["outputTokens"], 500 + 175)
        self.assertEqual(m["firstSessionDate"], "2026-04-11T00:00:00Z")
        dates = [d["date"] for d in m["dailyActivity"]]
        self.assertEqual(dates, sorted(dates))
        self.assertIn("live-transcripts", m["source"])   # the stamp says what was measured

    def test_missing_projects_dir_is_empty_not_fake(self) -> None:
        self.assertEqual(live_stats.scan(self.claude / "nope"), {})


if __name__ == "__main__":
    unittest.main()
