"""Reference-desk logic: list, search, and read library entries (what the MCP wraps)."""
import tempfile
import unittest
from pathlib import Path

from dewey import core


class ReferenceDesk(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.lib = Path(self._tmp.name)
        leaf = self.lib / "400-projects" / "project-demo"
        leaf.mkdir(parents=True)
        (leaf / "project_waka.md").write_text(
            "---\nname: waka\ndescription: the WAKA fleet app for whanau\n---\nbody here\n",
            encoding="utf-8",
        )
        (leaf / "note_plain.md").write_text(
            "# Heading\n\nfirst real line about eyewear\n", encoding="utf-8"
        )
        # hub + index files must be ignored by the reference desk
        (self.lib / "_LIBRARY-MAP.md").write_text("# map\n", encoding="utf-8")
        (self.lib / "LIBRARY-INDEX.md").write_text("# index\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_entries_skip_hubs_and_summarise(self) -> None:
        entries = {e.name: e for e in core.library_entries(self.lib)}
        self.assertEqual(set(entries), {"project_waka.md", "note_plain.md"})
        self.assertEqual(entries["project_waka.md"].summary, "the WAKA fleet app for whanau")
        self.assertEqual(entries["note_plain.md"].summary, "first real line about eyewear")
        self.assertEqual(entries["project_waka.md"].klass, "400-projects")

    def test_search_matches_summary(self) -> None:
        self.assertEqual([e.name for e in core.search_library(self.lib, "eyewear")], ["note_plain.md"])
        self.assertEqual([e.name for e in core.search_library(self.lib, "waka whanau")], ["project_waka.md"])
        self.assertEqual(core.search_library(self.lib, "no-such-thing"), [])

    def test_read_entry_returns_full_text(self) -> None:
        text = core.read_library_entry(self.lib, "project_waka.md")
        self.assertIn("body here", text)
        self.assertIn("description:", text)
        self.assertIsNone(core.read_library_entry(self.lib, "nope.md"))


if __name__ == "__main__":
    unittest.main()
