"""dewey health: read-only cross-drive sweep — duplicates, orphans, superseded, secrets.

Two temp dirs stand in for two drives (e.g. D: and the F: SATA backup) so the
within-drive vs cross-drive duplicate distinction can be proven.
"""
import json
import tempfile
import unittest
from pathlib import Path

from dewey import health


def _w(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class HealthSweep(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.d = base / "driveD"      # the working drive
        self.f = base / "driveF"      # the SATA backup drive
        Y = "---\ndescription: kv8 infra\n---\nkv8 office notes\n"

        # linked pair: project_onda -> reference_kv8 (neither is an orphan)
        _w(self.d / "400-projects" / "project_onda.md",
           "---\ndescription: onda booking\n---\nsee [[reference_kv8]]\n")
        _w(self.d / "500-reference" / "reference_kv8.md", Y)
        # a second copy of Y WITHIN drive D -> one redundant (dedupe target)
        _w(self.d / "_extra" / "reference_kv8.md", Y)
        # the SAME bytes on drive F -> healthy cross-drive backup, NOT redundant
        _w(self.f / "500-reference" / "reference_kv8.md", Y)

        # an orphan: memory-like, no links in or out
        _w(self.d / "900-sessions" / "session_orphan.md",
           "---\ndescription: stray\n---\nnothing links here\n")
        # a note carrying a secret-like value
        _w(self.d / "300-agents" / "soul_bond.md",
           "token lives here: sk-proj-ABCDEFGHIJKLMNOPQRSTUVWX\n")
        # a superseded note under a wiped vault path
        _w(self.d / "_VAULT-WIPED-20260624" / "project_hapai.md",
           "---\ndescription: hapai\n---\nold copy\n")

        self.snap = health.sweep([self.d, self.f])
        self.by_name = {}
        for n in self.snap.notes:
            self.by_name.setdefault(n.path.name, []).append(n)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _one(self, name: str, root: Path):
        return next(n for n in self.by_name[name] if n.root == root)

    def test_within_drive_duplicate_is_redundant(self) -> None:
        copies = [n for n in self.by_name["reference_kv8.md"] if n.root == self.d]
        redundant = [n for n in copies if n.redundant]
        self.assertEqual(len(redundant), 1, "exactly one intra-drive copy is redundant")
        self.assertIsNotNone(redundant[0].canonical)

    def test_cross_drive_copy_is_a_backup_not_redundant(self) -> None:
        f_copy = self._one("reference_kv8.md", self.f)
        self.assertFalse(f_copy.redundant, "the F: backup copy must not be flagged as waste")
        self.assertGreaterEqual(health._backup_coverage(self.snap.notes), 1)

    def test_orphan_detection(self) -> None:
        self.assertTrue(self._one("session_orphan.md", self.d).orphan)
        # the linked reference is NOT an orphan (project_onda points at it)
        self.assertFalse(self._one("reference_kv8.md", self.d).orphan)
        self.assertFalse(self._one("project_onda.md", self.d).orphan)

    def test_secret_flagged(self) -> None:
        self.assertGreater(self._one("soul_bond.md", self.d).secret_hits, 0)

    def test_superseded_flagged(self) -> None:
        self.assertTrue(self._one("project_hapai.md", self.d).superseded)

    def test_reports_written_with_task_board(self) -> None:
        out = Path(self._tmp.name) / "out"
        report, tasks = health.write_reports(self.snap, out)
        self.assertTrue(report.is_file() and tasks.is_file())
        board = json.loads(tasks.read_text(encoding="utf-8"))
        actions = {t["action"] for t in board["tasks"]}
        self.assertEqual(
            {"dedupe", "scrub-secret", "retire-superseded", "review-orphan"} & actions,
            {"dedupe", "scrub-secret", "retire-superseded", "review-orphan"},
        )


if __name__ == "__main__":
    unittest.main()
