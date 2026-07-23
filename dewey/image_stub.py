"""dewey image — keep a lightweight recollection stub of an image, not the pixels.

The full image stays on disk; the library gets a small card describing it (filename,
dimensions, format, mode, byte size, modified date, a short palette sample, and an
optional caption) so it can be recalled by `dewey ask` without ever loading the binary
into context. This is the multimodal arm of the "make memory smaller" mantra.

Optional extra: `pip install "dewey[image]"` (pillow). Without it, `describe()` still
returns the filesystem facts and degrades gracefully with a clear note.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class ImageStub:
    ok: bool
    meta: dict = field(default_factory=dict)
    path: Optional[Path] = None   # the written stub card
    note: str = ""


def _pillow():
    try:
        from PIL import Image
        return Image
    except Exception:
        return None


def available() -> bool:
    """True if Pillow is importable (richer stubs). Basic stubs work without it."""
    return _pillow() is not None


def describe(src: Path) -> ImageStub:
    """Build a recollection stub (metadata only) for an image file."""
    src = Path(src)
    if not src.is_file():
        return ImageStub(False, note=f"no such file: {src}")
    st = src.stat()
    meta = {
        "name": src.name,
        "path": str(src),
        "bytes": st.st_size,
        "modified": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d"),
    }
    Image = _pillow()
    if Image is None:
        meta["note"] = 'install "dewey[image]" (pillow) for dimensions + palette'
        return ImageStub(True, meta=meta, note="basic stub (no Pillow)")
    try:
        with Image.open(src) as im:
            meta["format"] = im.format
            meta["mode"] = im.mode
            meta["width"], meta["height"] = im.size
            thumb = im.convert("RGB").resize((16, 16))
            colors = thumb.getcolors(256) or []
            top = sorted(colors, reverse=True)[:3]
            meta["palette"] = ["#%02x%02x%02x" % rgb for _, rgb in top]
    except Exception as e:
        return ImageStub(False, meta=meta, note=f"pillow error: {e}")
    return ImageStub(True, meta=meta)


def _render(meta: dict, caption: Optional[str], today: str) -> str:
    dims = f"{meta.get('width','?')}×{meta.get('height','?')}" if "width" in meta else "?"
    lines = ["---",
             f"description: Image stub — {meta['name']}",
             "metadata:", "  node_type: memory", "  type: reference", "  source: image",
             f"  original: {meta['path']}", f"  captured: {today}",
             "---", "",
             f"# {meta['name']} — recollection stub", "",
             f"_image stub · captured {today} · full file stays at `{meta['path']}`_", "",
             f"- **dimensions:** {dims}",
             f"- **format / mode:** {meta.get('format','?')} / {meta.get('mode','?')}",
             f"- **size:** {meta['bytes']} bytes",
             f"- **modified:** {meta['modified']}"]
    if meta.get("palette"):
        lines.append(f"- **palette:** {', '.join(meta['palette'])}")
    if caption:
        lines += ["", f"**caption:** {caption}"]
    return "\n".join(lines) + "\n"


def capture(library: Path, src: Path, *, caption: Optional[str] = None,
            today: Optional[str] = None) -> ImageStub:
    """Describe an image and shelve the stub as a library card; the pixels stay on disk."""
    res = describe(src)
    if not res.ok:
        return res
    today = today or datetime.now().strftime("%Y-%m-%d")
    stem = Path(src).stem.lower().replace(" ", "-")
    dest = Path(library) / "500-reference" / "images" / f"{today}-{stem}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(_render(res.meta, caption, today), encoding="utf-8")
    res.path = dest
    return res
