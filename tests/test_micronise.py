"""micronise must never pointer-ize MEMORY.md (the live session index)."""
import tempfile
import unittest
from pathlib import Path

from dewey import core


class MicroniseSkipsMemoryIndex(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.silo_dir = root / "silo" / "memory"
        self.library = root / "library"
        lib_leaf = self.library / "000-meta" / "project-demo"
        self.silo_dir.mkdir(parents=True)
        lib_leaf.mkdir(parents=True)
        # both files are byte-identical between silo and library, so both *would*
        # qualify as micronise targets — only the skip-rule should hold MEMORY.md back.
        for d in (self.silo_dir, lib_leaf):
            (d / "note.md").write_text("a normal body\n", encoding="utf-8")
            (d / "MEMORY.md").write_text("the live index\n", encoding="utf-8")
        self.silo = core.Silo("demo", self.silo_dir, "project", core._md_files(self.silo_dir))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_memory_md_is_never_a_micronise_target(self) -> None:
        targets = {src.name for src, _ in core.plan_micronise([self.silo], self.library).targets}
        self.assertIn("note.md", targets)        # ordinary entries still shrink
        self.assertNotIn("MEMORY.md", targets)   # the live index is protected


if __name__ == "__main__":
    unittest.main()
