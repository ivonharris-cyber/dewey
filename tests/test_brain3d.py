"""dewey brain: the living 3D viewer — graph extraction, thought traces, html generation."""
import json
import tempfile
import unittest
from pathlib import Path

from dewey import brain3d


class Brain3D(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.library = Path(self._tmp.name) / "library"
        leaf = self.library / "400-projects"
        leaf.mkdir(parents=True)
        (leaf / "project_onda.md").write_text(
            "---\ndescription: Onda booking\n---\nsee [[project_shop]] and [[reference_x]]\n", encoding="utf-8")
        (leaf / "project_shop.md").write_text(
            "---\ndescription: the shop\n---\nbody\n", encoding="utf-8")
        ref = self.library / "500-reference"
        ref.mkdir()
        (ref / "reference_x.md").write_text("ref body\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_extract_resolves_wikilinks_to_links(self) -> None:
        g = brain3d.extract_graph(self.library)
        self.assertEqual(len(g["nodes"]), 3)
        pairs = {(l["source"], l["target"]) for l in g["links"]}
        self.assertIn(("project_onda.md", "project_shop.md"), pairs)
        self.assertIn(("project_onda.md", "reference_x.md"), pairs)

    def test_nodes_coloured_by_class(self) -> None:
        g = brain3d.extract_graph(self.library)
        onda = next(n for n in g["nodes"] if n["id"] == "project_onda.md")
        self.assertEqual(onda["klass"], "400-projects")
        self.assertTrue(onda["color"].startswith("#"))

    def test_thought_records_origin_and_depth(self) -> None:
        p = brain3d.write_thought(self.library, ["project_onda.md", "project_shop.md"])
        payload = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(payload["origin"], "project_onda.md")  # rank[0] = where it started
        self.assertEqual(payload["depth"], 2)

    def test_write_brain_emits_html_with_data(self) -> None:
        out, n, m = brain3d.write_brain(self.library)
        self.assertTrue(out.exists())
        self.assertEqual(n, 3)
        self.assertGreaterEqual(m, 2)
        html = out.read_text(encoding="utf-8")
        self.assertIn("ForceGraph3D", html)
        self.assertIn("project_onda.md", html)


if __name__ == "__main__":
    unittest.main()
