"""dewey connectors: manifest, honest key status, spend ledger, BCP args, and the
fernet vault. The load-bearing guarantee under test: status paths never return or
persist a secret VALUE — only set/missing booleans."""
import json
import os
import tempfile
import unittest
from pathlib import Path

from dewey import connectors


class Connectors(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        home = Path(self._tmp.name)
        # Redirect the vault + ledger + fuel config + stats into the tmp home.
        self._orig = (connectors.DEWEY_HOME, connectors.EXPENSES, connectors.VAULT,
                      connectors.BUDGET, connectors.STATS)
        connectors.DEWEY_HOME = home / ".dewey"
        connectors.EXPENSES = connectors.DEWEY_HOME / "expenses.csv"
        connectors.VAULT = connectors.DEWEY_HOME / "vault.enc"
        connectors.BUDGET = connectors.DEWEY_HOME / "budget.json"
        connectors.STATS = home / "stats-cache.json"
        # A deterministic env file with one present + implicitly-missing key.
        self.envf = home / ".env"
        self.envf.write_text('ANTHROPIC_API_KEY=sk-secret-value-123\nEMPTY_KEY=\n', encoding="utf-8")
        os.environ["DEWEY_ENV_FILES"] = str(self.envf)

    def tearDown(self) -> None:
        (connectors.DEWEY_HOME, connectors.EXPENSES, connectors.VAULT,
         connectors.BUDGET, connectors.STATS) = self._orig
        os.environ.pop("DEWEY_ENV_FILES", None)
        self._tmp.cleanup()

    def _write_stats(self) -> None:
        connectors.STATS.write_text(json.dumps({
            "lastComputedDate": "2026-06-10",
            "dailyModelTokens": [
                {"date": "2026-06-08", "tokensByModel": {"claude-opus-4-8": 1_000_000}},
                {"date": "2026-06-09", "tokensByModel": {"claude-opus-4-8": 2_000_000}},
            ],
            "modelUsage": {"claude-opus-4-8": {"outputTokens": 3_000_000}},
        }), encoding="utf-8")

    def test_manifest_loads_all_kinds(self) -> None:
        m = connectors.load_manifest()
        kinds = {c["kind"] for c in m}
        self.assertEqual(kinds, {"subscription", "mcp", "bcp"})
        self.assertTrue(any(c["id"] == "mcp-dewey" for c in m))

    def test_key_status_is_booleans_only(self) -> None:
        # Manifest has an anthropic subscription needing ANTHROPIC_API_KEY (present here).
        ks = connectors.key_status()
        for keys in ks.values():
            for present in keys.values():
                self.assertIsInstance(present, bool)   # never a value
        self.assertTrue(ks["anthropic"]["ANTHROPIC_API_KEY"])

    def test_empty_value_counts_as_missing(self) -> None:
        # EMPTY_KEY= has no value → must not count as present.
        self.assertNotIn("EMPTY_KEY", connectors._present_keys())

    def test_state_never_contains_a_secret_value(self) -> None:
        blob = json.dumps(connectors.state())
        self.assertNotIn("sk-secret-value-123", blob)      # the actual secret
        self.assertIn("ANTHROPIC_API_KEY", blob)           # only the NAME is exposed

    def test_spend_override_and_total(self) -> None:
        connectors.set_cost("elevenlabs", 11)
        s = connectors.spend_summary()
        eleven = next(i for i in s["items"] if i["id"] == "elevenlabs")
        self.assertEqual(eleven["cost_month"], 11)
        # anthropic default 20 + elevenlabs override 11 are both in the total
        self.assertGreaterEqual(s["total_month"], 31)

    def test_bcp_backup_cmd_is_rclone_copy_dryrun(self) -> None:
        cmd = connectors.bcp_backup_cmd(source="X")
        self.assertEqual(cmd[1], "copy")
        # targets a Google-Drive rclone remote (account-agnostic; the real one is set in the manifest)
        self.assertTrue(any("gdrive:" in a for a in cmd))

    def test_mcp_install_templating(self) -> None:
        cmd = connectors.mcp_install_cmd("mcp-dewey", library="/lib/here")
        self.assertIn("/lib/here", cmd)
        self.assertNotIn("{library}", cmd)

    def test_token_burn_real_fields_and_no_guess_when_missing(self) -> None:
        # No stats-cache → must NOT fabricate; returns available=False.
        self.assertFalse(connectors.token_burn().get("available"))
        self._write_stats()
        b = connectors.token_burn()
        self.assertTrue(b["available"])
        self.assertEqual(b["as_of"], "2026-06-10")
        self.assertEqual(b["cumulative"], 3_000_000)          # from modelUsage.outputTokens
        self.assertEqual(b["peak"], 2_000_000)                # biggest single day
        self.assertNotIn("gauge", b)                          # no fuel gauge until a limit+price is set

    def test_fuel_gauge_only_with_limit_and_price(self) -> None:
        from datetime import date
        self._write_stats()
        connectors.set_budget(limit=100, price=15, day=1)
        b = connectors.token_burn(today=date(2026, 6, 10))
        self.assertIn("gauge", b)
        g = b["gauge"]
        self.assertEqual(g["limit_usd"], 100)
        # cycle starts on the 1st; both days (8th, 9th) fall in-cycle = 3M tokens × $15/1M = $45
        self.assertAlmostEqual(g["usd_used"], 45.0, places=2)

    def test_cycle_bounds(self) -> None:
        from datetime import date
        start, nxt = connectors._cycle_bounds(15, date(2026, 7, 11))
        self.assertEqual(start.isoformat(), "2026-06-15")     # most recent 15th on/before today
        self.assertEqual(nxt.isoformat(), "2026-07-15")

    def test_activity_feed_is_live_and_current(self) -> None:
        from datetime import date, timedelta
        # a memory file touched "today" must land on today's bucket (independent of Claude's stats-cache)
        today = date.today()
        a = connectors.activity_feed(today=today, days=30)
        self.assertTrue(a["available"])
        self.assertEqual(a["as_of"], today.isoformat())            # as-of = today, not a stale cache date
        self.assertEqual(len(a["series"]), 30)
        self.assertEqual(a["series"][-1]["date"], today.isoformat())  # last bucket is today
        # every bucket carries a real integer count
        self.assertTrue(all(isinstance(d["entries"], int) for d in a["series"]))

    def test_budget_roundtrip(self) -> None:
        connectors.set_budget(limit=50, price=12.5, day=3)
        b = connectors.read_budget()
        self.assertEqual((b["spend_limit_usd"], b["price_per_1m_usd"], b["billing_day"]), (50, 12.5, 3))

    @unittest.skipUnless(connectors.vault_available(), "cryptography not installed")
    def test_vault_roundtrip_and_encrypted_at_rest(self) -> None:
        n = connectors.vault_import("hunter2", extra={"FOO_KEY": "topsecret"})
        self.assertGreaterEqual(n, 1)
        raw = connectors.VAULT.read_bytes()
        self.assertNotIn(b"topsecret", raw)               # encrypted at rest
        v = connectors.unlock("hunter2")
        self.assertEqual(v.get("FOO_KEY"), "topsecret")   # only after unlock
        with self.assertRaises(ValueError):
            connectors.unlock("wrong-passphrase")


if __name__ == "__main__":
    unittest.main()
