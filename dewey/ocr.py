"""dewey ocr — read a PDF or image into plain text and shelve it as a recallable card.

"Capture a PDF, read it, re-write it as a plain-text document." Text-layer PDFs are
read with `pypdf` (pure python); images are OCR'd with Tesseract via `pytesseract`.
The extracted text is written into the library as a dated `.md` card so `dewey ask`
can recall it — the binary itself stays where it is.

Optional extra: `pip install "dewey[ocr]"` (pytesseract, pypdf, pillow) plus a local
Tesseract install for image OCR. Any missing piece degrades gracefully with a clear
note (same pattern as compress.py / the vault broker). Core stays stdlib-only.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp"}
# UB-Mannheim's Windows installer drops the binary here; point pytesseract at it if
# it isn't already on PATH, so image OCR works without extra configuration.
_WIN_TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


@dataclass
class Ocr:
    ok: bool
    text: str = ""
    method: str = "none"   # "pypdf" | "tesseract"
    path: Optional[Path] = None
    note: str = ""


def _pypdf():
    try:
        import pypdf
        return pypdf
    except Exception:
        return None


def _tesseract():
    try:
        import pytesseract
        from PIL import Image  # noqa: F401
    except Exception:
        return None
    if not os.environ.get("TESSERACT_ON_PATH"):
        exe = pytesseract.pytesseract.tesseract_cmd
        if (exe in ("tesseract", "tesseract.exe")) and os.path.isfile(_WIN_TESSERACT):
            pytesseract.pytesseract.tesseract_cmd = _WIN_TESSERACT
    return pytesseract


def available() -> bool:
    """True if at least one extraction backend (pypdf or Tesseract) is importable."""
    return _pypdf() is not None or _tesseract() is not None


def _extract_pdf(path: Path) -> Ocr:
    pypdf = _pypdf()
    if pypdf is None:
        return Ocr(False, note='PDF support needs pypdf — pip install "dewey[ocr]"')
    try:
        reader = pypdf.PdfReader(str(path))
        text = "\n\n".join((page.extract_text() or "") for page in reader.pages).strip()
    except Exception as e:
        return Ocr(False, note=f"pypdf error: {e}")
    if not text:
        return Ocr(False, method="pypdf",
                   note="no text layer (scanned PDF?) — rasterise to images then run ocr")
    return Ocr(True, text=text, method="pypdf")


def _extract_image(path: Path) -> Ocr:
    pt = _tesseract()
    if pt is None:
        return Ocr(False, note='image OCR needs Tesseract + pytesseract — pip install "dewey[ocr]"')
    try:
        from PIL import Image
        text = pt.image_to_string(Image.open(path)).strip()
    except Exception as e:
        return Ocr(False, note=f"tesseract error: {e}")
    return Ocr(True, text=text, method="tesseract")


def extract(path: Path) -> Ocr:
    """Pull plain text from a PDF (text layer) or an image (OCR)."""
    path = Path(path)
    if not path.is_file():
        return Ocr(False, note=f"no such file: {path}")
    if path.suffix.lower() == ".pdf":
        return _extract_pdf(path)
    if path.suffix.lower() in _IMAGE_EXT:
        return _extract_image(path)
    return Ocr(False, note=f"unsupported type '{path.suffix}' (want a PDF or an image)")


def _render(src: Path, res: Ocr, today: str) -> str:
    return "\n".join([
        "---",
        f"description: OCR capture — {src.name}",
        "metadata:", "  node_type: memory", "  type: reference",
        f"  source: {res.method}", f"  original: {src}", f"  captured: {today}",
        "---", "",
        f"# {src.name} — plain text", "",
        f"_extracted via {res.method} · captured {today} · from `{src}`_", "",
        res.text, ""]) + "\n"


def capture(library: Path, src: Path, *, today: Optional[str] = None) -> Ocr:
    """Extract text from src and shelve it as a library card; returns the Ocr result."""
    res = extract(src)
    if not res.ok:
        return res
    today = today or datetime.now().strftime("%Y-%m-%d")
    stem = Path(src).stem.lower().replace(" ", "-")
    dest = Path(library) / "500-reference" / "ocr" / f"{today}-{stem}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(_render(Path(src), res, today), encoding="utf-8")
    res.path = dest
    return res
