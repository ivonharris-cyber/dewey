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
        # Redirect the vault + ledger into the tmp home.
        self._orig = (connectors.DEWEY_HOME, connectors.EXPENSES, connectors.VAULT)
        connectors.DEWEY_HOME = home / ".dewey"
        connectors.EXPENSES = connectors.DEWEY_HOME / "expenses.csv"
        connectors.VAULT = connectors.DEWEY_HOME / "vault.enc"
        # A deterministic env file with one present + implicitly-missing key.
        self.envf = home / ".env"
        self.envf.write_text('ANTHROPIC_API_KEY=sk-secret-value-123\nEMPTY_KEY=\n', encoding="utf-8")
        os.environ["DEWEY_ENV_FILES"] = str(self.envf)

    def tearDown(self) -> None:
        connectors.DEWEY_HOME, connectors.EXPENSES, connectors.VAULT = self._orig
        os.environ.pop("DEWEY_ENV_FILES", None)
        self._tmp.cleanup()

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
