"""dewey merge: archive byte-identical cross-silo extras, flag conflicts, never merge per-agent files."""
import tempfile
import unittest
from pathlib import Path

from dewey import core


class MergeDedup(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._saved = core.CLAUDE
        core.CLAUDE = self.root  # discover_silos + the ~/.claude boundary use this

    def tearDown(self) -> None:
        core.CLAUDE = self._saved
        self._tmp.cleanup()

    def _mk(self, silo: str, name: str, body: str) -> Path:
        d = self.root / "projects" / silo / "memory"
        d.mkdir(parents=True, exist_ok=True)
        p = d / name
        p.write_text(body, encoding="utf-8")
        return p

    def test_plan_classifies_and_skips_identity_files(self) -> None:
        self._mk("A", "note_same.md", "identical body\n")
        self._mk("B", "note_same.md", "identical body\n")
        self._mk("A", "note_diff.md", "short\n")
        self._mk("B", "note_diff.md", "a much longer body that differs\n")
        # per-agent / per-silo identity files must NEVER be cross-silo merged
        self._mk("A", "MEMORY.md", "index A\n")
        self._mk("B", "MEMORY.md", "index B is different\n")
        self._mk("A", "soul.md", "agent A soul\n")
        self._mk("B", "soul.md", "agent B soul is different\n")
        groups = {g.name: g for g in core.find_name_duplicates(core.discover_silos())}
        self.assertNotIn("MEMORY.md", groups)
        self.assertNotIn("soul.md", groups)
        self.assertEqual(len(groups["note_same.md"].redundant), 1)
        self.assertEqual(len(groups["note_same.md"].conflicts), 0)
        self.assertEqual(len(groups["note_diff.md"].conflicts), 1)
        self.assertTrue(groups["note_diff.md"].canonical.read_text().startswith("a much longer"))

    def test_apply_archives_identical_only_and_flags_conflicts(self) -> None:
        self._mk("A", "note_same.md", "identical body\n")
        self._mk("B", "note_same.md", "identical body\n")
        self._mk("A", "note_diff.md", "short\n")
        self._mk("B", "note_diff.md", "a much longer body that differs\n")
        groups = core.find_name_duplicates(core.discover_silos())
        archive = core.merge_archive_dir()
        moved = core.apply_merge(groups, archive)
        self.assertEqual(moved, 1)                                                       # only the identical extra
        self.assertEqual(len(list(Path(archive).rglob("*.md"))), 1)                      # preserved in archive
        self.assertEqual(len(list((self.root / "projects").rglob("note_same.md"))), 1)   # collapsed to one
        self.assertEqual(len(list((self.root / "projects").rglob("note_diff.md"))), 2)   # conflict untouched


if __name__ == "__main__":
    unittest.main()
