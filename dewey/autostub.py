"""dewey autostub — the auto-stubbing mantra: memory grows into pointers by reflex.

"Make memory smaller, not heavier." This is the *write* half of the Leeloo loop —
meant to run unattended (e.g. from a Stop hook at session end) so a silo file that
grew during a session collapses back to a small Dewey-decimal pointer on its own.

Safety is inherited, not reinvented: a file only ever collapses once its full
content is **byte-identical** to a copy already shelved in the library, so nothing
is ever lost. That is exactly `micronise` — autostub just adds a size threshold
(small files aren't worth the churn) and leans on the same engine:
`core.plan_micronise` / `apply_micronise` / `write_micronise_log`. Same pointer
format, same atomic writes, same recovery log, same `~/.claude` boundary + symlink
guards, same `_NEVER_STUB` protection for the live index (MEMORY.md).

Because the gate is "identical copy already in the library", a file that grew but
was never synced is simply left alone (safe). To shelve this session's new content
first, run `dewey sync --apply` before autostub — the Stop-hook wrapper does both.

Dependency-free (stdlib only), like the rest of core.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import core

BYTES_PER_TOKEN = 3.9
DEFAULT_MIN_TOKENS = 2000  # only collapse files big enough to be worth the token win


@dataclass
class AutostubPlan:
    plan: core.MicroPlan   # the filtered micronise plan (only targets over the threshold)
    skipped_small: int     # micronisable, but under the threshold — deliberately left in place
    min_tokens: int


def _tokens(path: Path) -> int:
    try:
        return int(path.stat().st_size / BYTES_PER_TOKEN)
    except OSError:
        return 0


def plan_autostub(silos: list[core.Silo], library: Path,
                  min_tokens: int = DEFAULT_MIN_TOKENS) -> AutostubPlan:
    """Micronise plan, filtered to silo files whose size clears the token threshold."""
    full = core.plan_micronise(silos, library)
    over: list[tuple[Path, Path]] = []
    before = after = small = 0
    for silo_file, lib_copy in full.targets:
        if _tokens(silo_file) >= min_tokens:
            over.append((silo_file, lib_copy))
            before += silo_file.stat().st_size
            after += len(core._pointer_stub(lib_copy).encode("utf-8"))
        else:
            small += 1
    return AutostubPlan(core.MicroPlan(over, before, after), small, min_tokens)
