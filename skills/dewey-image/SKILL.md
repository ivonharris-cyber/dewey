---
name: dewey-image
description: >
  This skill should be used when the user asks to "remember this image", "keep a stub of
  this picture", "note this screenshot for later", "catalogue this image", or wants an
  image recalled by description without loading the pixels into context. Backed by
  `dewey image`, which writes a lightweight recollection stub (dimensions, format,
  palette, optional caption) into the library while the full image stays on disk.
version: 0.1.0
---

# dewey-image — keep a recollection stub, not the pixels

Images are heavy and opaque to a text brain. This skill keeps a **small stub** — enough
to recognise and find the image later (name, dimensions, format, a palette sample, an
optional caption) — while the full file stays on disk. Recall stays cheap; nothing
loads the binary into context until you actually open it.

## When to reach for it
- The user shares a screenshot/photo/diagram they'll want to find or reference later.
- You want the brain to *know an image exists* and what it roughly is, without its bytes.

## How to use it
1. For dimensions + palette, install the extra: `pip install "dewey[image]"` (pillow).
   Without it, a basic stub (name, size, date) is still written.
2. Run: `dewey image <file> --to <library> [--caption "what it shows"]`.
3. The stub lands at `<library>/500-reference/images/<date>-<slug>.md`; recall via
   `dewey ask`. The stub records the original path so you can open the real file on demand.

## The mantra
This is the multimodal arm of "make memory smaller, not heavier": the library carries a
pointer-sized description; the pixels never bloat the context. Add a human `--caption`
when the picture's meaning isn't obvious from its metadata alone.
