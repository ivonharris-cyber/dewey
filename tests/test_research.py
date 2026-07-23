import tempfile
import unittest
from unittest import mock
from pathlib import Path

from dewey import research


class Research(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.lib = Path(self._tmp.name) / "library"
        self.lib.mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_slug_is_filesystem_safe(self) -> None:
        self.assertEqual(research._slug("Hello, World!!"), "hello-world")
        self.assertEqual(research._slug(""), "query")

    def test_no_key_is_graceful(self) -> None:
        with mock.patch.object(research, "_api_key", return_value=None):
            r = research.query("anything")
        self.assertFalse(r.ok)
        self.assertIn("API key", r.note)

    def test_no_key_capture_writes_nothing(self) -> None:
        with mock.patch.object(research, "_api_key", return_value=None):
            r = research.capture(self.lib, "anything")
        self.assertFalse(r.ok)
        self.assertIsNone(r.path)
        self.assertEqual(list(self.lib.rglob("*.md")), [])

    def test_capture_shelves_a_recallable_card(self) -> None:
        fake = research.Research(True, "what is x", content="X is Y.",
                                 citations=["http://a", "http://b"])
        with mock.patch.object(research, "query", return_value=fake):
            res = research.capture(self.lib, "what is x", today="2026-01-01")
        self.assertTrue(res.ok)
        self.assertTrue(res.path.is_file())
        text = res.path.read_text(encoding="utf-8")
        self.assertIn("X is Y.", text)
        self.assertIn("http://a", text)
        self.assertIn("source: perplexity", text)
        self.assertTrue(res.path.name.startswith("2026-01-01-"))


if __name__ == "__main__":
    unittest.main()
