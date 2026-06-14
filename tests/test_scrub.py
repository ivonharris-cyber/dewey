"""dewey scrub: redact secret values from notes, leave the rest, keep the .env as the source."""
import tempfile
import unittest
from pathlib import Path

from dewey import core


class ScrubSecrets(unittest.TestCase):
    def test_known_key_formats_are_redacted(self) -> None:
        text = (
            "google key AIza" + "B" * 35 + "\n"
            "openai sk-" + "a" * 30 + "\n"
            "bot 8703628497:" + "C" * 35 + "\n"
            "password: hunter2secretvalue\n"
            "a perfectly normal sentence about the project\n"
        )
        new, n = core.scrub_text(text)
        self.assertNotIn("AIza" + "B" * 35, new)
        self.assertNotIn("sk-" + "a" * 30, new)
        self.assertNotIn("hunter2secretvalue", new)
        self.assertIn("[redacted -> .env]", new)
        self.assertIn("a perfectly normal sentence about the project", new)  # prose untouched
        self.assertGreaterEqual(n, 4)

    def test_extra_literal_password(self) -> None:
        new, n = core.scrub_text("login me@x.com / SuperPass1!\n", ["SuperPass1!"])
        self.assertNotIn("SuperPass1!", new)
        self.assertEqual(n, 1)

    def test_no_secrets_means_no_change(self) -> None:
        text = "# A note\n\njust notes, no secrets here.\n"
        new, n = core.scrub_text(text)
        self.assertEqual(n, 0)
        self.assertEqual(new, text)

    def test_apply_rewrites_in_place_only_inside_claude(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        saved = core.CLAUDE
        core.CLAUDE = root
        try:
            d = root / "projects" / "demo" / "memory"
            d.mkdir(parents=True)
            secret = d / "creds.md"
            secret.write_text("password: topsecretvalue\n", encoding="utf-8")
            clean = d / "clean.md"
            clean.write_text("nothing to see\n", encoding="utf-8")
            silo = core.Silo("demo", d, "project", core._md_files(d))
            changed = core.apply_scrub([silo])
            self.assertEqual(changed, 1)
            self.assertNotIn("topsecretvalue", secret.read_text(encoding="utf-8"))
            self.assertEqual(clean.read_text(encoding="utf-8"), "nothing to see\n")
        finally:
            core.CLAUDE = saved


if __name__ == "__main__":
    unittest.main()
