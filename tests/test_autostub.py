import tempfile
import unittest
from pathlib import Path

from dewey import core, autostub


class Autostub(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.silo_dir = self.root / "projects" / "demo" / "memory"
        self.library = self.root / "library"
        self.lib_leaf = self.library / "400-projects" / "project-demo"
        self.silo_dir.mkdir(parents=True)
        self.lib_leaf.mkdir(parents=True)
        self._saved = core.CLAUDE          # mock the ~/.claude boundary onto the temp root
        core.CLAUDE = self.root

    def tearDown(self) -> None:
        core.CLAUDE = self._saved
        self._tmp.cleanup()

    def _pair(self, name: str, body: str) -> Path:
        """Write byte-identical copies into the silo and the library (i.e. 'already synced')."""
        (self.silo_dir / name).write_text(body, encoding="utf-8")
        (self.lib_leaf / name).write_text(body, encoding="utf-8")
        return self.silo_dir / name

    def _silos(self):
        return core.discover_silos()

    def test_over_threshold_is_planned_and_applied(self) -> None:
        sf = self._pair("big.md", "x" * 400)               # ~102 tok
        ap = autostub.plan_autostub(self._silos(), self.library, min_tokens=50)
        self.assertEqual(len(ap.plan.targets), 1)
        self.assertEqual(core.apply_micronise(ap.plan), 1)
        self.assertTrue(sf.read_text(encoding="utf-8").startswith(core._STUB_MARKER))

    def test_under_threshold_is_left_in_place(self) -> None:
        self._pair("small.md", "y" * 40)                   # ~10 tok
        ap = autostub.plan_autostub(self._silos(), self.library, min_tokens=50)
        self.assertEqual(len(ap.plan.targets), 0)
        self.assertEqual(ap.skipped_small, 1)

    def test_unsynced_file_is_never_touched(self) -> None:
        # Large, but has NO byte-identical library copy — must not be a candidate.
        (self.silo_dir / "unsynced.md").write_text("z" * 400, encoding="utf-8")
        ap = autostub.plan_autostub(self._silos(), self.library, min_tokens=50)
        self.assertEqual(len(ap.plan.targets), 0)

    def test_live_index_is_never_stubbed(self) -> None:
        self._pair("MEMORY.md", "x" * 400)                 # over threshold + synced, but protected
        ap = autostub.plan_autostub(self._silos(), self.library, min_tokens=50)
        self.assertEqual(len(ap.plan.targets), 0)

    def test_plan_is_dry_and_writes_nothing(self) -> None:
        body = "x" * 400
        sf = self._pair("big.md", body)
        autostub.plan_autostub(self._silos(), self.library, min_tokens=50)  # plan only, no apply
        self.assertEqual(sf.read_text(encoding="utf-8"), body)

    def test_roundtrip_checkout_restores_full_content(self) -> None:
        body = "x" * 400
        sf = self._pair("big.md", body)
        ap = autostub.plan_autostub(self._silos(), self.library, min_tokens=50)
        core.apply_micronise(ap.plan)
        self.assertTrue(sf.read_text(encoding="utf-8").startswith(core._STUB_MARKER))
        core.checkout_entry(sf)
        self.assertEqual(sf.read_text(encoding="utf-8"), body)


if __name__ == "__main__":
    unittest.main()
