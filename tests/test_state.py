"""dewey state: the canonical one-truth entry — read/write/merge, with tag lookup."""
import tempfile
import unittest
from pathlib import Path

from dewey import state


class StateEntry(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.lib = Path(self._tmp.name) / "library"
        (self.lib / "400-projects").mkdir(parents=True)
        # a tagged project entry so tag lookup can resolve
        (self.lib / "400-projects" / "project_ngati.md").write_text(
            "---\ndescription: ngati toa governance\ntags:\n  id: NGT001\n  project: ngati-toa\n---\nbody\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_read_missing_is_none(self) -> None:
        self.assertIsNone(state.read_state(self.lib))

    def test_write_then_read_roundtrip(self) -> None:
        st, path = state.update_state(
            self.lib, project="ngati-toa", last="submitted the pepeha",
            loops=["confirm tupuna", "notion sync"], notion="https://notion.so/x", today="2026-07-14",
        )
        self.assertTrue(path.is_file())
        back = state.read_state(self.lib)
        self.assertEqual(back.project, "ngati-toa")
        self.assertEqual(back.last, "submitted the pepeha")
        self.assertEqual(back.loops, ["confirm tupuna", "notion sync"])
        self.assertEqual(back.notion, "https://notion.so/x")
        self.assertEqual(back.date, "2026-07-14")

    def test_tag_looked_up_from_project(self) -> None:
        st, _ = state.update_state(self.lib, project="ngati-toa", today="2026-07-14")
        self.assertEqual(st.tag, "NGT001")

    def test_partial_update_preserves_other_fields(self) -> None:
        state.update_state(self.lib, project="ngati-toa", last="first",
                           loops=["keep me"], today="2026-07-14")
        # update only the last action; project + loops must survive
        st, _ = state.update_state(self.lib, last="second action", today="2026-07-15")
        self.assertEqual(st.project, "ngati-toa")
        self.assertEqual(st.last, "second action")
        self.assertEqual(st.loops, ["keep me"])
        self.assertEqual(st.date, "2026-07-15")

    def test_loops_parse_only_under_header(self) -> None:
        # the field bullets (**Project:** etc.) must never be read back as open loops
        state.update_state(self.lib, project="ngati-toa", last="x",
                           loops=["only real loop"], today="2026-07-14")
        self.assertEqual(state.read_state(self.lib).loops, ["only real loop"])


if __name__ == "__main__":
    unittest.main()
