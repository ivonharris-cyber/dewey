"""SuperCompress meld — optional ask-time context compression.

Mirrors the Graphify pattern: an OPTIONAL external tool, wrapped, with graceful
fallback. If `supercompress` (pip) is installed, `compress()` scores the few
entries `dewey ask` returned against the question and reports how much of the
KV/token budget is actually needed — so only the query-relevant context reaches
the model. If it isn't installed, `compress()` is a faithful no-op.

    dewey ask "…" --to <library> --compress

Out of the box SuperCompress runs its H2O fallback policy: it reports the token
budget it would keep (real, projected savings) without dropping lines. Train a
checkpoint once (`supercompress-train --fast`) or point
`DEWEY_SUPERCOMPRESS_CHECKPOINT` at a `.pt` file and it additionally trims the
literal text. We only ever report the numbers the tool actually returns.

Design rule (same as graph.py): the core stays dependency-free; SuperCompress is
an optional extra (`pip install "dewey[compress]"`).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

DEFAULT_BUDGET = 0.35


@dataclass
class Compression:
    ok: bool                 # True only if supercompress actually ran
    text: str                # compressed context (or the original, on fallback)
    original_tokens: int
    kept_tokens: int
    policy: str
    note: str

    @property
    def saved_pct(self) -> int:
        if not self.original_tokens:
            return 0
        return round((1 - self.kept_tokens / self.original_tokens) * 100)


def available() -> bool:
    """True if the optional `supercompress` package is importable."""
    try:
        import supercompress  # noqa: F401
        return True
    except Exception:
        return False


def _load_policy(checkpoint: Optional[str]):
    """Load a trained eviction policy if a checkpoint is configured; else None (fallback)."""
    if not checkpoint:
        return None
    try:
        from supercompress import checkpoint as ck
        return ck.load_policy(checkpoint)
    except Exception:
        return None  # no/invalid checkpoint — fall back to the built-in H2O policy


def compress(text: str, question: str, *, budget_ratio: float = DEFAULT_BUDGET,
             checkpoint: Optional[str] = None) -> Compression:
    """Compress `text` against `question`; degrade gracefully when the tool is absent."""
    if not text.strip():
        return Compression(False, text, 0, 0, "none", "empty context")
    try:
        from supercompress import compress_context
    except Exception:
        return Compression(False, text, 0, 0, "none",
                           "supercompress not installed — `pip install \"dewey[compress]\"` (optional)")
    cp = checkpoint or os.environ.get("DEWEY_SUPERCOMPRESS_CHECKPOINT")
    policy = _load_policy(cp)
    try:
        result = compress_context(text, question, budget_ratio=budget_ratio, policy=policy)
    except Exception as e:  # never let an optional tool break `ask`
        return Compression(False, text, 0, 0, "none", f"supercompress error: {e}")
    return Compression(
        ok=True,
        text=result.compressed_text,
        original_tokens=result.original_tokens,
        kept_tokens=result.kept_tokens,
        policy=result.policy_name,
        note="compressed",
    )
