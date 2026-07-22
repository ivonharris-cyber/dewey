import tempfile
import unittest
from unittest import mock
from pathlib import Path

from dewey import image_stub


class ImageStub(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.lib = self.root / "library"
        self.lib.mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_missing_file(self) -> None:
        r = image_stub.describe(self.root / "nope.png")
        self.assertFalse(r.ok)
        self.assertIn("no such file", r.note)

    def test_basic_stub_without_pillow(self) -> None:
        p = self.root / "x.png"
        p.write_bytes(b"bytes-on-disk")
        with mock.patch.object(image_stub, "_pillow", return_value=None):
            r = image_stub.describe(p)
        self.assertTrue(r.ok)                    # filesystem facts still captured
        self.assertEqual(r.meta["bytes"], len(b"bytes-on-disk"))
        self.assertNotIn("width", r.meta)
        self.assertIn("pillow", r.note.lower())

    @unittest.skipUnless(image_stub._pillow() is not None, "Pillow not installed")
    def test_pillow_stub_has_dimensions_and_palette(self) -> None:
        from PIL import Image
        p = self.root / "tile.png"
        Image.new("RGB", (64, 48), "white").save(p)
        res = image_stub.capture(self.lib, p, caption="a white tile", today="2026-01-01")
        self.assertTrue(res.ok, res.note)
        self.assertEqual((res.meta["width"], res.meta["height"]), (64, 48))
        self.assertEqual(res.meta["format"], "PNG")
        self.assertTrue(res.meta.get("palette"))
        text = res.path.read_text(encoding="utf-8")
        self.assertIn("64×48", text)
        self.assertIn("a white tile", text)      # the pixels stay on disk; only the stub is shelved


if __name__ == "__main__":
    unittest.main()
