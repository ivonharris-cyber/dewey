"""Command-line entry point for Dewey."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, core

_PLANNED = (
    "Planned — these arrive with the MCP layer.\n"
    "  checkout : load specific entries into a silo for context\n"
    "  checkin  : sync a silo back to the library and leave pointers"
)


def cmd_sweep(_: argparse.Namespace) -> None:
    silos = core.discover_silos()
    total = sum(len(s.files) for s in silos)
    print(f"{len(silos)} memory silos, {total} files\n")
    for s in sorted(silos, key=lambda x: len(x.files), reverse=True):
        print(f"  [{s.kind:7}] {s.name:34} {len(s.files):>4}")


def cmd_log(_: argparse.Namespace) -> None:
    rows = core.build_log(core.discover_silos())
    month = ""
    for r in rows:
        tag = r.date.strftime("%Y-%m")
        if tag != month:
            print(f"\n== {r.date:%B %Y} ==")
            month = tag
        print(f"  {r.date:%Y-%m-%d}  {r.category:9} {r.title}  ({r.silo})")
    print(f"\n{len(rows)} entries.")


def cmd_doctor(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"error: {root} is not a directory")
        raise SystemExit(2)
    print(f"Scanning git repos under {root} for .env leaks (no secrets read)\n")
    leaks = 0
    for h in core.doctor_env(root):
        if h.verdict != "ok":
            leaks += 1
        flag = "ok " if h.verdict == "ok" else "!! "
        print(f"{flag}{h.name:26} {h.verdict}")
        if h.env_files:
            print(f"       env: {', '.join(h.env_files)}  (ignored={h.gitignore_covers_env})")
    print(f"\n{leaks} repo(s) need attention.")


def cmd_sync(args: argparse.Namespace) -> None:
    target = Path(args.to).resolve()
    if str(target).startswith(str(core.CLAUDE.resolve())):
        print("error: --to must not point inside ~/.claude (it would create a feedback loop)")
        raise SystemExit(2)
    plan = core.plan_sync(core.discover_silos(), target)
    print(f"Library target: {target}")
    print(f"  {len(plan.copied)} entries to copy - {len(plan.skipped_sensitive)} skipped (sensitive)")
    for p in plan.skipped_sensitive[:15]:
        print(f"    skip (sensitive): {p.name}")
    if len(plan.skipped_sensitive) > 15:
        print(f"    ... and {len(plan.skipped_sensitive) - 15} more")
    if not args.apply:
        print("\n(dry-run) add --apply to write the library.")
        return
    written = core.apply_sync(plan, target)
    print(f"\n[ok] Copied {len(written)} entries into {target}")


def cmd_balance(args: argparse.Namespace) -> None:
    groups = core.find_duplicates(core.discover_silos())
    dups = [g for g in groups if g.identical_stale]
    conflicts = [g for g in groups if g.conflicts]
    stale_count = sum(len(g.identical_stale) for g in dups)
    print(f"{len(groups)} duplicated names - {stale_count} exact stale copies - {len(conflicts)} conflicts\n")
    for g in dups[:30]:
        print(f"  dup   {g.name}  ({len(g.identical_stale)} stale copy/ies) -> keep newest")
    if len(dups) > 30:
        print(f"  ... and {len(dups) - 30} more duplicate group(s)")
    for g in conflicts[:30]:
        print(f"  !!    {g.name}  same name, different content across silos (needs you)")
    if len(conflicts) > 30:
        print(f"  ... and {len(conflicts) - 30} more conflict(s)")
    if not args.apply:
        print("\n(dry-run) add --apply to replace exact duplicates with a pointer. Conflicts are never touched.")
        return
    log = core.write_balance_log(dups)
    healed = sum(core.heal_duplicate(g) for g in dups)
    print(f"\n[ok] replaced {healed} exact duplicates with a pointer. {len(conflicts)} conflicts left for you.")
    print(f"recovery log: {log}")


def cmd_planned(_: argparse.Namespace) -> None:
    print(_PLANNED)


def main(argv: list[str] | None = None) -> None:
    for _stream in (sys.stdout, sys.stderr):  # print unicode paths on any console
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(prog="dewey", description="A Dewey-decimal memory librarian for Claude Code.")
    parser.add_argument("--version", action="version", version=f"dewey {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("sweep", help="list all memory silos").set_defaults(fn=cmd_sweep)
    sub.add_parser("log", help="list every memory entry in date order").set_defaults(fn=cmd_log)

    doctor = sub.add_parser("doctor", help="scan repositories for committed .env files")
    doctor.add_argument("root", nargs="?", default=".", help="directory containing git repositories")
    doctor.set_defaults(fn=cmd_doctor)

    sync = sub.add_parser("sync", help="copy memory into a Markdown library (skips credentials; dry-run by default)")
    sync.add_argument("--to", required=True, help="target library directory")
    sync.add_argument("--apply", action="store_true", help="write the library (default: dry-run)")
    sync.set_defaults(fn=cmd_sync)

    balance = sub.add_parser("balance", help="find duplicate entries across silos; replace exact duplicates with a pointer (dry-run by default)")
    balance.add_argument("--apply", action="store_true", help="replace byte-identical duplicates with a pointer (conflicts are never modified)")
    balance.set_defaults(fn=cmd_balance)

    for name in ("checkout", "checkin"):
        sub.add_parser(name, help=f"planned (MCP layer): {name}").set_defaults(fn=cmd_planned)

    args = parser.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
