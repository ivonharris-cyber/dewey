"""checkout restores a shrunk entry to full content; checkin syncs edits back and re-shrinks."""
import tempfile
import unittest
from pathlib import Path

from dewey import core


class CheckoutCheckinRoundTrip(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.silo_dir = self.root / "projects" / "demo" / "memory"
        self.library = self.root / "library"
        self.lib_leaf = self.library / "400-projects" / "project-demo"
        self.silo_dir.mkdir(parents=True)
        self.lib_leaf.mkdir(parents=True)
        self.full = "the full body\nwith two lines\n"
        self.canonical = self.lib_leaf / "project_foo.md"
        self.canonical.write_text(self.full, encoding="utf-8")
        self.silo_file = self.silo_dir / "project_foo.md"
        self.silo_file.write_text(core._pointer_stub(self.canonical), encoding="utf-8")
        self._saved = core.CLAUDE
        core.CLAUDE = self.root  # let the ~/.claude boundary guard accept our temp silo

    def tearDown(self) -> None:
        core.CLAUDE = self._saved
        self._tmp.cleanup()

    def test_checkout_restores_full_content(self) -> None:
        self.assertTrue(self.silo_file.read_text().startswith("# moved by"))   # starts as a stub
        self.assertTrue(core.checkout_entry(self.silo_file))
        self.assertEqual(self.silo_file.read_text(encoding="utf-8"), self.full)

    def test_checkin_syncs_edits_then_reshrinks(self) -> None:
        core.checkout_entry(self.silo_file)
        edited = self.full + "an edit made while checked out\n"
        self.silo_file.write_text(edited, encoding="utf-8")
        self.assertTrue(core.checkin_entry(self.silo_file, self.library))
        self.assertEqual(self.canonical.read_text(encoding="utf-8"), edited)    # edit reached the shelf
        self.assertTrue(self.silo_file.read_text().startswith("# moved by"))    # silo is a pointer again

    def test_checkout_ignores_a_normal_file(self) -> None:
        plain = self.silo_dir / "plain.md"
        plain.write_text("not a stub\n", encoding="utf-8")
        self.assertFalse(core.checkout_entry(plain))

    def test_checkin_refuses_when_no_library_home(self) -> None:
        core.checkout_entry(self.silo_file)
        self.silo_file.write_text("edited\n", encoding="utf-8")
        self.canonical.unlink()  # remove the shelf copy
        self.assertFalse(core.checkin_entry(self.silo_file, self.library))      # refuses rather than guess


if __name__ == "__main__":
    unittest.main()
