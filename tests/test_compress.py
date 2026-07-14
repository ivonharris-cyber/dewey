"""dewey compress: the optional SuperCompress meld — graceful with or without the tool."""
import unittest
from unittest import mock

from dewey import compress


class Compress(unittest.TestCase):
    def test_empty_text_is_a_noop(self) -> None:
        c = compress.compress("   ", "any question?")
        self.assertFalse(c.ok)
        self.assertEqual(c.original_tokens, 0)

    def test_graceful_when_tool_absent(self) -> None:
        # Simulate `import supercompress` failing inside compress().
        import builtins
        real_import = builtins.__import__

        def _blow_up(name, *a, **k):
            if name == "supercompress" or name.startswith("supercompress."):
                raise ImportError("no supercompress")
            return real_import(name, *a, **k)

        with mock.patch("builtins.__import__", side_effect=_blow_up):
            c = compress.compress("some real context here", "what is here?")
        self.assertFalse(c.ok)
        self.assertIn("not installed", c.note)
        self.assertEqual(c.text, "some real context here")  # original returned unchanged

    def test_saved_pct_math(self) -> None:
        c = compress.Compression(True, "x", original_tokens=100, kept_tokens=35,
                                 policy="H2O", note="compressed")
        self.assertEqual(c.saved_pct, 65)

    def test_runs_when_supercompress_present(self) -> None:
        if not compress.available():
            self.skipTest("supercompress not installed")
        c = compress.compress(
            "Onda handles beauty booking and Stripe payments.\n"
            "The weather in London was rainy and is irrelevant.\n",
            "what does onda do?",
        )
        self.assertTrue(c.ok)
        self.assertGreater(c.original_tokens, 0)
        self.assertLessEqual(c.kept_tokens, c.original_tokens)


if __name__ == "__main__":
    unittest.main()
