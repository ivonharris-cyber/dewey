"""Command-line entry point for Dewey."""
from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__, core

_PLANNED = (
    "Designed, not yet implemented — see the library model in README.md.\n"
    "  checkout : load Dewey call-numbers into a silo\n"
    "  checkin  : sync a silo back to the vault, leave pointer stubs\n"
    "  balance  : self-healing reconcile across all silos + the vault"
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
    plan = core.plan_sync(core.discover_silos(), target)
    print(f"Library target: {target}")
    print(f"  {len(plan.copied)} books to shelve - {len(plan.skipped_sensitive)} skipped (sensitive)")
    for p in plan.skipped_sensitive[:15]:
        print(f"    skip (sensitive): {p.name}")
    if not args.apply:
        print("\n(dry-run) add --apply to write the library.")
        return
    core.apply_sync(plan, target)
    print(f"\n[ok] Shelved {len(plan.copied)} books into {target}")


def cmd_planned(_: argparse.Namespace) -> None:
    print(_PLANNED)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="dewey", description="A Dewey-decimal memory librarian for Claude Code.")
    parser.add_argument("--version", action="version", version=f"dewey {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("sweep", help="list every memory silo").set_defaults(fn=cmd_sweep)
    sub.add_parser("log", help="captain's log: all memory by stardate").set_defaults(fn=cmd_log)

    doctor = sub.add_parser("doctor", help="scan repos for .env leaks + hygiene")
    doctor.add_argument("root", nargs="?", default=".", help="dir containing git repos")
    doctor.set_defaults(fn=cmd_doctor)

    sync = sub.add_parser("sync", help="shelve memory into a Markdown library (secret-aware, dry-run default)")
    sync.add_argument("--to", required=True, help="target library directory")
    sync.add_argument("--apply", action="store_true", help="actually write (default: dry-run)")
    sync.set_defaults(fn=cmd_sync)

    for name in ("checkout", "checkin", "balance"):
        sub.add_parser(name, help=f"[planned] {name}").set_defaults(fn=cmd_planned)

    args = parser.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
