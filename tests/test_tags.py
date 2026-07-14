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
        text = "---\ndescription: x\ntags:\n  call: 400.01 ONDA\n  project: onda\n  keywords: pepeha, stripe\n---\nbody\n"
        tags = core.parse_tags(text)
        self.assertEqual(tags["call"], "400.01 ONDA")
        self.assertEqual(tags["project"], "onda")
        self.assertIn("stripe", tags["keywords"])

    def test_parse_inline_flow_form(self) -> None:
        text = "---\ntags: { call: 400.02 HAPA, project: hapai, keywords: [wof, rego] }\n---\nbody\n"
        tags = core.parse_tags(text)
        self.assertEqual(tags["call"], "400.02 HAPA")
        self.assertEqual(tags["project"], "hapai")

    def test_no_frontmatter_returns_empty(self) -> None:
        self.assertEqual(core.parse_tags("just a body, no frontmatter\n"), {})

    def test_call_number_is_meaningful_and_accession_stable(self) -> None:
        reg: dict = {}
        first = core.call_number(reg, "400-projects", "onda")
        second = core.call_number(reg, "400-projects", "hapai")
        again = core.call_number(reg, "400-projects", "onda")
        self.assertEqual(first, "400.01 ONDA")     # class . subject-decimal CUTTER
        self.assertEqual(second, "400.02 HAPA")    # next accession in the class
        self.assertEqual(again, first)             # a number, once assigned, never moves
        self.assertEqual(core.call_number(reg, "500-reference", "kv8"), "500.01 KV8")

    def test_backfill_is_idempotent_and_call_stable(self) -> None:
        plan1, reg1 = core.plan_tag(self.lib)
        self.assertTrue(plan1.targets)
        self.assertEqual(core.apply_tag(self.lib, plan1, reg1), len(plan1.targets))
        onda = self.lib / "400-projects" / "project_onda.md"
        tags = core.parse_tags(onda.read_text(encoding="utf-8"))
        self.assertRegex(tags["call"], r"^400\.\d{2} ONDA$")
        self.assertEqual(tags["project"], "onda")
        first_call = tags["call"]
        # the register persisted beside the library
        self.assertTrue((self.lib / core.CATALOGUE_NAME).is_file())
        # second pass: nothing to change, call number unmoved (accession law)
        plan2, _ = core.plan_tag(self.lib)
        self.assertEqual(plan2.targets, [])
        self.assertEqual(core.parse_tags(onda.read_text(encoding="utf-8"))["call"], first_call)

    def test_backfill_preserves_description(self) -> None:
        plan, reg = core.plan_tag(self.lib)
        core.apply_tag(self.lib, plan, reg)
        onda = (self.lib / "400-projects" / "project_onda.md").read_text(encoding="utf-8")
        self.assertIn("description: Onda beauty booking", onda)

    def test_search_reads_body_not_just_summary(self) -> None:
        # "stripe" appears only in the BODY, never in name/summary/class.
        hits = core.search_library(self.lib, "stripe")
        self.assertEqual([e.name for e in hits], ["project_onda.md"])

    def test_search_reads_tags(self) -> None:
        plan, reg = core.plan_tag(self.lib)
        core.apply_tag(self.lib, plan, reg)
        # after cataloguing, the derived project keyword is searchable via the tags block
        hits = core.search_library(self.lib, "onda")
        self.assertTrue(any(e.name == "project_onda.md" for e in hits))

    # --- regression tests for the review bugs -------------------------------

    def test_parse_tags_tolerates_blank_line_in_block(self) -> None:
        # HIGH bug: a blank line inside the block used to silently drop every key after it.
        text = "---\ntags:\n  call: 400.01 ONDA\n\n  date: 2026-07-14\n  project: onda\n---\nbody\n"
        tags = core.parse_tags(text)
        self.assertEqual(tags.get("call"), "400.01 ONDA")
        self.assertEqual(tags.get("date"), "2026-07-14")   # was dropped before the fix
        self.assertEqual(tags.get("project"), "onda")

    def test_upsert_leaves_unclosed_frontmatter_untouched(self) -> None:
        # HIGH bug: opening --- with no closing --- used to nest a block and swallow keys.
        broken = "---\ntitle: foo\nbody line with no closing fence\n"
        out = core.upsert_tags(broken, {"call": "400.01 ONDA"})
        self.assertEqual(out, broken)  # never corrupt a malformed file
        self.assertIn("title: foo", out)

    def test_upsert_idempotent_with_blank_line_in_old_block(self) -> None:
        # MEDIUM bug: a blank line in the OLD tags block broke idempotency (never stabilised).
        text = ("---\ndescription: x\ntags:\n  call: 400.01 ONDA\n\n  date: 2026-07-14\n"
                "---\nbody\n")
        once = core.upsert_tags(text, {"call": "400.01 ONDA", "date": "2026-07-14"})
        twice = core.upsert_tags(once, {"call": "400.01 ONDA", "date": "2026-07-14"})
        self.assertEqual(once, twice)                 # stable across runs
        self.assertIn("description: x", once)         # non-tag frontmatter preserved

    def test_parse_flow_tags_preserves_trailing_brace_value(self) -> None:
        # MEDIUM bug: rstrip('}') ate the '}' inside a value like url/{id}.
        tags = core.parse_tags("---\ntags: { call: 400.01 ONDA, notion: url/{id} }\n---\nbody\n")
        self.assertEqual(tags.get("call"), "400.01 ONDA")
        self.assertIn("{id}", tags.get("notion", ""))


if __name__ == "__main__":
    unittest.main()
