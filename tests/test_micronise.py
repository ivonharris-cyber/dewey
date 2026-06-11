"""micronise/balance must never pointer-ize MEMORY.md (the live session index)."""
import tempfile
import unittest
from pathlib import Path

from dewey import core


class MicroniseSkipsMemoryIndex(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.silo_dir = self.root / "silo" / "memory"
        self.library = self.root / "library"
        self.lib_leaf = self.library / "000-meta" / "project-demo"
        self.silo_dir.mkdir(parents=True)
        self.lib_leaf.mkdir(parents=True)
        # byte-identical between silo and library, so both *would* qualify as targets —
        # only the skip-rule should hold MEMORY.md back.
        for d in (self.silo_dir, self.lib_leaf):
            (d / "note.md").write_text("a normal body\n", encoding="utf-8")
            (d / "MEMORY.md").write_text("the live index\n", encoding="utf-8")
        self.silo = core.Silo("demo", self.silo_dir, "project", core._md_files(self.silo_dir))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_plan_never_targets_memory_md(self) -> None:
        targets = {src.name for src, _ in core.plan_micronise([self.silo], self.library).targets}
        self.assertEqual(len(targets), 1)        # the fixture really did trigger the micronise path
        self.assertIn("note.md", targets)        # ordinary entries still shrink
        self.assertNotIn("MEMORY.md", targets)   # the live index is protected

    def test_apply_is_defence_in_depth(self) -> None:
        # Even a hand-crafted plan that illegally lists MEMORY.md must not overwrite it.
        saved = core.CLAUDE
        core.CLAUDE = self.root  # let the ~/.claude boundary guard accept our temp silo
        try:
            mem = self.silo_dir / "MEMORY.md"
            before = mem.read_text(encoding="utf-8")
            plan = core.MicroPlan(
                targets=[
                    (self.silo_dir / "note.md", self.lib_leaf / "note.md"),
                    (mem, self.lib_leaf / "MEMORY.md"),
                ],
                before_bytes=0, after_bytes=0,
            )
            core.apply_micronise(plan)
            self.assertTrue((self.silo_dir / "note.md").read_text().startswith("# moved by"))
            self.assertEqual(mem.read_text(encoding="utf-8"), before)  # MEMORY.md untouched
        finally:
            core.CLAUDE = saved

    def test_skip_is_case_insensitive(self) -> None:
        # a lowercase memory.md (a distinct file on Linux) must also be protected
        d = self.root / "silo2" / "memory"
        libd = self.library / "000-meta" / "project-two"
        d.mkdir(parents=True)
        libd.mkdir(parents=True)
        (d / "memory.md").write_text("idx\n", encoding="utf-8")
        (libd / "memory.md").write_text("idx\n", encoding="utf-8")
        silo = core.Silo("two", d, "project", core._md_files(d))
        targets = {src.name for src, _ in core.plan_micronise([silo], self.library).targets}
        self.assertNotIn("memory.md", targets)


if __name__ == "__main__":
    unittest.main()
