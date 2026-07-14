"""dewey tag: backfill + parse a tags block; search now reads tags + body."""
import tempfile
import unittest
from pathlib import Path

from dewey import core


def _lib(base: Path) -> Path:
    lib = base / "library"
    leaf = lib / "400-projects"
    leaf.mkdir(parents=True)
    (leaf / "project_onda.md").write_text(
        "---\ndescription: Onda beauty booking\n---\n"
        "Onda handles payment hardening with Stripe identity verification.\n",
        encoding="utf-8",
    )
    (lib / "500-reference").mkdir()
    (lib / "500-reference" / "reference_kv8.md").write_text(
        "KV8 is the Hermes office box running Cain and Abel.\n", encoding="utf-8",
    )
    return lib


class Tags(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.lib = _lib(Path(self._tmp.name))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_parse_block_form(self) -> None:
        text = "---\ndescription: x\ntags:\n  id: ABC123\n  project: onda\n  keywords: pepeha, stripe\n---\nbody\n"
        tags = core.parse_tags(text)
        self.assertEqual(tags["id"], "ABC123")
        self.assertEqual(tags["project"], "onda")
        self.assertIn("stripe", tags["keywords"])

    def test_parse_inline_flow_form(self) -> None:
        text = "---\ntags: { id: XY9, project: hapai, keywords: [wof, rego] }\n---\nbody\n"
        tags = core.parse_tags(text)
        self.assertEqual(tags["id"], "XY9")
        self.assertEqual(tags["project"], "hapai")

    def test_no_frontmatter_returns_empty(self) -> None:
        self.assertEqual(core.parse_tags("just a body, no frontmatter\n"), {})

    def test_backfill_is_idempotent_and_stable_id(self) -> None:
        plan1 = core.plan_tag(self.lib)
        self.assertTrue(plan1.targets)
        self.assertEqual(core.apply_tag(plan1), len(plan1.targets))
        onda = self.lib / "400-projects" / "project_onda.md"
        tags = core.parse_tags(onda.read_text(encoding="utf-8"))
        self.assertEqual(len(tags["id"]), 6)
        self.assertEqual(tags["project"], "onda")
        first_id = tags["id"]
        # second pass: nothing left to change, and the id is stable
        plan2 = core.plan_tag(self.lib)
        self.assertEqual(plan2.targets, [])
        self.assertEqual(core.parse_tags(onda.read_text(encoding="utf-8"))["id"], first_id)

    def test_backfill_preserves_description(self) -> None:
        core.apply_tag(core.plan_tag(self.lib))
        onda = (self.lib / "400-projects" / "project_onda.md").read_text(encoding="utf-8")
        self.assertIn("description: Onda beauty booking", onda)

    def test_search_reads_body_not_just_summary(self) -> None:
        # "stripe" appears only in the BODY, never in name/summary/class.
        hits = core.search_library(self.lib, "stripe")
        self.assertEqual([e.name for e in hits], ["project_onda.md"])

    def test_search_reads_tags(self) -> None:
        core.apply_tag(core.plan_tag(self.lib))
        # after tagging, the derived project keyword is searchable via the tags block
        hits = core.search_library(self.lib, "onda")
        self.assertTrue(any(e.name == "project_onda.md" for e in hits))


if __name__ == "__main__":
    unittest.main()
