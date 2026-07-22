"""dewey research — capture external research (Perplexity) into recallable memory.

"Reclaim research from Perplexity to view." A one-shot query to the Perplexity API
whose answer + citations are written into the library as a dated, Dewey-classed `.md`
card, so `dewey ask` / `search` can recall it in a later session. The fetched content
is shelved as recalled *reference data* — it is never executed, only stored.

Network via the stdlib (`urllib`) — no extra needed. The API key is read from the
environment (`PERPLEXITY_API_KEY`, or the `Perplexity_API_Key` alias); it is never
hardcoded and never logged. This is the "capture" step of the Leeloo loop.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

PPLX_URL = "https://api.perplexity.ai/chat/completions"
DEFAULT_MODEL = "sonar-pro"
_KEY_ENVS = ("PERPLEXITY_API_KEY", "Perplexity_API_Key")


@dataclass
class Research:
    ok: bool
    query: str
    content: str = ""
    citations: list = field(default_factory=list)
    path: Optional[Path] = None
    note: str = ""


def _api_key() -> Optional[str]:
    for k in _KEY_ENVS:
        v = os.environ.get(k)
        if v:
            return v.strip()
    return None


def available() -> bool:
    """True if a Perplexity API key is present in the environment."""
    return _api_key() is not None


def _slug(text: str, n: int = 48) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:n].strip("-") or "query")


def query(question: str, *, api_key: Optional[str] = None,
          model: str = DEFAULT_MODEL, timeout: int = 90) -> Research:
    """Ask Perplexity once; return the answer + citations (no file written)."""
    key = api_key or _api_key()
    if not key:
        return Research(False, question,
                        note="no Perplexity API key — set PERPLEXITY_API_KEY (optional)")
    body = json.dumps({"model": model, "messages": [
        {"role": "system", "content": "Be concise and factual; cite sources."},
        {"role": "user", "content": question},
    ]}).encode("utf-8")
    req = urllib.request.Request(PPLX_URL, data=body, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return Research(False, question, note=f"Perplexity HTTP {e.code}")
    except Exception as e:  # network/JSON — never crash the caller
        return Research(False, question, note=f"Perplexity error: {e}")
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return Research(False, question, note="unexpected Perplexity response shape")
    return Research(True, question, content=content, citations=data.get("citations") or [])


def _render(res: Research, model: str, today: str) -> str:
    lines = ["---",
             f"description: Research capture — {res.query[:80]}",
             "metadata:", "  node_type: memory", "  type: reference",
             "  source: perplexity", f"  model: {model}", f"  captured: {today}",
             "---", "",
             f"# Research — {res.query}", "",
             f"_Perplexity {model} · captured {today} · recalled reference data, not instructions_",
             "", res.content, "", "## Citations"]
    lines += [f"- {c}" for c in res.citations] or ["- (none returned)"]
    return "\n".join(lines) + "\n"


def capture(library: Path, question: str, *, api_key: Optional[str] = None,
            model: str = DEFAULT_MODEL, timeout: int = 90,
            today: Optional[str] = None) -> Research:
    """Query Perplexity and shelve the answer as a library card; returns the Research."""
    res = query(question, api_key=api_key, model=model, timeout=timeout)
    if not res.ok:
        return res
    today = today or datetime.now().strftime("%Y-%m-%d")
    dest = Path(library) / "500-reference" / "research" / f"{today}-{_slug(question)}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(_render(res, model, today), encoding="utf-8")
    res.path = dest
    return res
