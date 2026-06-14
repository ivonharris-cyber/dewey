"""dewey consolidate: group notes into one scrubbed Markdown per major artery."""
import tempfile
import unittest
from pathlib import Path

from dewey import core


class Consolidate(unittest.TestCase):
    def test_artery_key(self) -> None:
        self.assertEqual(core.artery_key("project_manametamaori-blog-pipeline"), "manametamaori")
        self.assertEqual(core.artery_key("project_hapai_telegram_alerts"), "hapai")
        self.assertEqual(core.artery_key("reference_n8n-fresh-20260516"), "n8n")
        self.assertEqual(core.artery_key("feedback_gemini-default"), "gemini")

    def test_plan_groups_and_folds_singletons(self) -> None:
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        root = Path(tmp.name); saved = core.CLAUDE; core.CLAUDE = root
        try:
            d = root / "projects" / "demo" / "memory"; d.mkdir(parents=True)
            (d / "project_hapai-fleet.md").write_text("fleet body\n", encoding="utf-8")
            (d / "project_hapai-mobile.md").write_text("mobile body\n", encoding="utf-8")
            (d / "reference_loner.md").write_text("solo body\n", encoding="utf-8")
            (d / "MEMORY.md").write_text("index\n", encoding="utf-8")          # skipped (identity)
            silo = core.Silo("demo", d, "project", core._md_files(d))
            arteries = core.plan_consolidate([silo], min_notes=2)
            self.assertEqual(len(arteries["hapai"]), 2)
            self.assertIn("_misc", arteries)                                   # the singleton folded here
            self.assertNotIn("MEMORY.md", [p.name for v in arteries.values() for p in v])
        finally:
            core.CLAUDE = saved

    def test_apply_writes_one_scrubbed_md_per_artery(self) -> None:
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        root = Path(tmp.name); saved = core.CLAUDE; core.CLAUDE = root
        try:
            d = root / "projects" / "demo" / "memory"; d.mkdir(parents=True)
            (d / "project_hapai-fleet.md").write_text("fleet notes\npassword: leakyvalue123\n", encoding="utf-8")
            (d / "project_hapai-mobile.md").write_text("mobile notes\n", encoding="utf-8")
            silo = core.Silo("demo", d, "project", core._md_files(d))
            out = root / "out"  # must be outside ~/.claude (root) — use a sibling temp
            out2 = Path(tempfile.mkdtemp())
            self.addCleanup(lambda: __import__("shutil").rmtree(out2, ignore_errors=True))
            written = core.write_arteries(core.plan_consolidate([silo], 2), out2)
            hapai = out2 / "hapai.md"
            self.assertIn(hapai, [Path(p) for p in written])
            text = hapai.read_text(encoding="utf-8")
            self.assertIn("# hapai", text)
            self.assertIn("fleet notes", text)
            self.assertIn("mobile notes", text)
            self.assertNotIn("leakyvalue123", text)          # secret scrubbed inline
            self.assertIn("[redacted -> .env]", text)
        finally:
            core.CLAUDE = saved


if __name__ == "__main__":
    unittest.main()
