"""dewey call: the circulation desk — resolve a call number to the card (library, not catalogue)."""
import tempfile
import unittest
from pathlib import Path

from dewey import core


class Circulation(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.lib = Path(self._tmp.name) / "library"
        (self.lib / "400-projects").mkdir(parents=True)
        (self.lib / "500-reference").mkdir()
        self._card("400-projects/project_onda.md", "400.01 ONDA", "onda booking")
        self._card("400-projects/project_hapai.md", "400.02 HAPA", "hapai fleet")
        self._card("500-reference/reference_kv8.md", "500.01 KV8", "kv8 box")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _card(self, rel: str, call: str, desc: str) -> None:
        (self.lib / rel).write_text(
            f"---\ndescription: {desc}\ntags:\n  call: {call}\n---\nbody of {rel}\n", encoding="utf-8")

    def test_exact_call_withdraws_one_card(self) -> None:
        hits = core.resolve_call(self.lib, "400.01 ONDA")
        self.assertEqual([e.name for e in hits], ["project_onda.md"])

    def test_bare_decimal_withdraws_that_card(self) -> None:
        hits = core.resolve_call(self.lib, "400.02")
        self.assertEqual([e.name for e in hits], ["project_hapai.md"])

    def test_class_lists_the_whole_shelf_ordered(self) -> None:
        hits = core.resolve_call(self.lib, "400")
        self.assertEqual([e.tags["call"] for e in hits], ["400.01 ONDA", "400.02 HAPA"])

    def test_miss_returns_empty(self) -> None:
        self.assertEqual(core.resolve_call(self.lib, "900.99"), [])

    def test_case_and_space_insensitive(self) -> None:
        self.assertEqual([e.name for e in core.resolve_call(self.lib, "  400.01   onda ")],
                         ["project_onda.md"])


if __name__ == "__main__":
    unittest.main()
