import tempfile
import unittest
from unittest import mock
from pathlib import Path

from dewey import ocr


class Ocr(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.lib = self.root / "library"
        self.lib.mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_missing_file(self) -> None:
        r = ocr.extract(self.root / "nope.png")
        self.assertFalse(r.ok)
        self.assertIn("no such file", r.note)

    def test_unsupported_type(self) -> None:
        p = self.root / "note.txt"
        p.write_text("hello", encoding="utf-8")
        r = ocr.extract(p)
        self.assertFalse(r.ok)
        self.assertIn("unsupported", r.note)

    def test_image_ocr_graceful_when_backend_absent(self) -> None:
        p = self.root / "x.png"
        p.write_bytes(b"not-a-real-image")
        with mock.patch.object(ocr, "_tesseract", return_value=None):
            r = ocr._extract_image(p)
        self.assertFalse(r.ok)
        self.assertIn("Tesseract", r.note)

    def test_pdf_graceful_when_pypdf_absent(self) -> None:
        p = self.root / "x.pdf"
        p.write_bytes(b"%PDF-1.4")
        with mock.patch.object(ocr, "_pypdf", return_value=None):
            r = ocr._extract_pdf(p)
        self.assertFalse(r.ok)
        self.assertIn("pypdf", r.note)

    @unittest.skipUnless(ocr._tesseract() is not None, "Tesseract/pytesseract not installed")
    def test_real_image_ocr_roundtrip(self) -> None:
        from PIL import Image, ImageDraw, ImageFont
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 44)
        except Exception:
            self.skipTest("no truetype font for a legible OCR sample")
        img = self.root / "sample.png"
        im = Image.new("RGB", (520, 110), "white")
        ImageDraw.Draw(im).text((20, 30), "DEWEY OCR 42", fill="black", font=font)
        im.save(img)
        res = ocr.capture(self.lib, img, today="2026-01-01")
        self.assertTrue(res.ok, res.note)
        self.assertEqual(res.method, "tesseract")
        self.assertIn("DEWEY", res.text.upper())
        self.assertTrue(res.path.is_file())


if __name__ == "__main__":
    unittest.main()
