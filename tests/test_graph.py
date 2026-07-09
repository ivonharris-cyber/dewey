"""dewey graph / ask: the Graphify meld — graceful without the tool, ranked keyword fallback."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from dewey import graph


class GraphMeld(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.library = Path(self._tmp.name) / "library"
        leaf = self.library / "400-projects"
        leaf.mkdir(parents=True)
        (leaf / "project_onda.md").write_text(
            "---\ndescription: Onda beauty booking payment hardening and booking status\n---\nbody\n",
            encoding="utf-8",
        )
        (leaf / "project_shop.md").write_text(
            "---\ndescription: the shop storefront woocommerce\n---\nbody\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_build_graph_without_graphify_is_graceful(self) -> None:
        with mock.patch.object(graph, "graphify_cli", return_value=None):
            build = graph.build_graph(self.library)
        self.assertFalse(build.ok)
        self.assertIn("not installed", build.message)

    def test_ask_falls_back_to_ranked_keyword(self) -> None:
        with mock.patch.object(graph, "graphify_cli", return_value=None):
            res = graph.ask(self.library, "onda payment hardening booking status")
        self.assertEqual(res.mode, "keyword")
        self.assertTrue(res.entries)
        # The Onda entry (4 term hits) must outrank the shop entry (0 hits).
        self.assertEqual(res.entries[0].name, "project_onda.md")

    def test_ask_ranks_by_term_hits(self) -> None:
        with mock.patch.object(graph, "graphify_cli", return_value=None):
            res = graph.ask(self.library, "shop storefront")
        self.assertEqual(res.entries[0].name, "project_shop.md")

    def test_graph_mode_extracts_cited_filenames(self) -> None:
        (self.library / graph.GRAPH_DIRNAME).mkdir()
        fake = mock.Mock(returncode=0, stdout="Path: 400-projects/project_onda.md L3\n", stderr="")
        with mock.patch.object(graph, "graphify_cli", return_value="/usr/bin/graphify"), \
             mock.patch("dewey.graph.subprocess.run", return_value=fake):
            res = graph.ask(self.library, "which project handles payments")
        self.assertEqual(res.mode, "graph")
        self.assertEqual(res.entries[0].name, "project_onda.md")


if __name__ == "__main__":
    unittest.main()
