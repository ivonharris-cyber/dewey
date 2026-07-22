import tempfile
import unittest
from pathlib import Path

from dewey import brief, state as state_mod


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


class BriefBasics(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.lib = Path(self._tmp.name) / "library"
        _write(self.lib / "400-projects" / "p" / "project_alpha.md",
               "---\ndescription: Alpha the live project\n---\nbody\n")
        _write(self.lib / "500-reference" / "r" / "reference_beta.md",
               "Beta the durable reference fact\n")
        _write(self.lib / "900-sessions" / "s" / "session_old.md",
               "an old session log line\n")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_state_block_shown_when_set(self) -> None:
        state_mod.update_state(self.lib, project="ngati-toa", last="filed the pepeha",
                               loops=["draft the karakia"])
        text = brief.brief(self.lib)
        self.assertIn("project: ngati-toa", text)
        self.assertIn("filed the pepeha", text)
        self.assertIn("draft the karakia", text)

    def test_no_state_is_graceful(self) -> None:
        text = brief.brief(self.lib)  # no STATE.md written
        self.assertIn("not set yet", text)
        self.assertIn("mantra:", text)  # still renders the full brief

    def test_project_outranks_session(self) -> None:
        text = brief.brief(self.lib)
        self.assertIn("project_alpha.md", text)
        self.assertLess(text.index("project_alpha.md"), text.index("session_old.md"))

    def test_state_entry_not_a_pointer(self) -> None:
        state_mod.update_state(self.lib, project="x", last="y")
        b = brief.build_brief(self.lib)
        self.assertNotIn("STATE.md", "\n".join(
            l for l in b.text.splitlines() if l.strip().startswith("0")))


class BriefFiltersAndCaps(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.lib = Path(self._tmp.name) / "library"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_micronised_stub_entries_are_filtered(self) -> None:
        _write(self.lib / "500-reference" / "r" / "reference_real.md",
               "A genuine reference body\n")
        _write(self.lib / "500-reference" / "r" / "reference_empty.md",
               "The full copy lives in the library:\n\n`~/x`\n")
        text = brief.brief(self.lib)
        self.assertIn("reference_real.md", text)
        self.assertNotIn("reference_empty.md", text)

    def test_per_class_cap_keeps_the_brief_diverse(self) -> None:
        for i in range(6):
            _write(self.lib / "500-reference" / "r" / f"reference_{i}.md", f"ref body {i}\n")
        _write(self.lib / "400-projects" / "p" / "project_solo.md", "the one project\n")
        b = brief.build_brief(self.lib, max_pointers=10, per_class_cap=2)
        self.assertEqual(b.text.count("500-reference"), 2)   # class was capped
        self.assertIn("project_solo.md", b.text)             # other classes still surface

    def test_token_cap_is_enforced(self) -> None:
        for i in range(80):
            _write(self.lib / "500-reference" / "r" / f"reference_{i:03d}.md",
                   f"a reasonably long durable reference summary number {i} " * 2 + "\n")
        b = brief.build_brief(self.lib, max_pointers=80, token_cap=200, per_class_cap=80)
        self.assertLess(b.shown, b.total)                    # cap forced a trim
        self.assertLessEqual(int(len(b.text) / brief.BYTES_PER_TOKEN), 200 + 30)


if __name__ == "__main__":
    unittest.main()
