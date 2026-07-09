"""Command-line entry point for Dewey."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, core, graph, brain3d, dashboard

def _selected(silos, name, want_all):
    """Yield (silo, file) pairs matching a filename, or every file with --all."""
    for s in silos:
        for f in s.files:
            if want_all or f.name == name:
                yield s, f


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


def cmd_weave(args: argparse.Namespace) -> None:
    library = Path(args.to).resolve()
    if not library.is_dir():
        print(f"error: {library} is not a library directory (run sync first)")
        raise SystemExit(2)
    moc, total, classes = core.weave_library(library)
    print(f"[ok] woven {total} entries into topic clusters ({moc.name})")
    vault = core.find_vault(library)
    if vault:
        gpath = core.weave_colors(vault, library, classes)
        coloured = len([c for c in classes if c in core._CLASS_COLORS])
        print(f"[ok] coloured {coloured} classes (000-900) in {gpath.name}")
    else:
        print("(no .obsidian vault found above the library - skipped colouring)")
    print("Reload Obsidian / reopen Graph View: clusters are linked + coloured by class.")


def cmd_micronise(args: argparse.Namespace) -> None:
    library = Path(args.library).resolve()
    if not library.is_dir():
        print(f"error: {library} is not a library directory (run sync first)")
        raise SystemExit(2)
    plan = core.plan_micronise(core.discover_silos(), library)
    if not plan.targets:
        print("nothing to micronise yet — no silo files have an identical copy in the library (run sync first).")
        return
    saved = plan.before_bytes - plan.after_bytes
    pct = saved / plan.before_bytes * 100 if plan.before_bytes else 0
    print(f"{len(plan.targets)} shelved entries can shrink to pointers:")
    print(f"  before: {plan.before_bytes/1024:.0f} KB  ->  after: {plan.after_bytes/1024:.1f} KB   ({pct:.0f}% smaller)")
    if not args.apply:
        print("\n(dry-run) add --apply to replace those silo files with pointers. The full content stays in the library.")
        return
    log = core.write_micronise_log(plan)
    done = core.apply_micronise(plan)
    print(f"\n[ok] micronised {done} entries. recovery log: {log}")
    print("NOTE: those silo files are now pointer stubs — your assistant reads the pointer, not the")
    print("      content, until a checkout/restore command exists. Re-run `dewey sync` to rebuild the")
    print("      library, or restore originals from the recovery log if needed.")


def cmd_checkout(args: argparse.Namespace) -> None:
    if not args.all and not args.name:
        print("error: name an entry (e.g. project_foo.md) or pass --all")
        raise SystemExit(2)
    done = 0
    for s, f in _selected(core.discover_silos(), args.name, args.all):
        if core.checkout_entry(f):
            print(f"  checked out  {f.name}  ({s.name})")
            done += 1
    print(f"\n[ok] checked out {done} entr{'y' if done == 1 else 'ies'} — full content restored.")


def cmd_checkin(args: argparse.Namespace) -> None:
    if not args.all and not args.name:
        print("error: name an entry (e.g. project_foo.md) or pass --all")
        raise SystemExit(2)
    library = Path(args.library).resolve()
    if not library.is_dir():
        print(f"error: {library} is not a library directory (run sync first)")
        raise SystemExit(2)
    done = 0
    for s, f in _selected(core.discover_silos(), args.name, args.all):
        if core.checkin_entry(f, library):
            print(f"  checked in   {f.name}  ({s.name})")
            done += 1
    print(f"\n[ok] checked in {done} entr{'y' if done == 1 else 'ies'} — edits synced, re-shrunk to pointers.")


def cmd_scrub(args: argparse.Namespace) -> None:
    extra = [x for x in (args.also or "").split(",") if x]
    silos = core.discover_silos()
    hits = core.scan_secret_notes(silos, extra)
    total = sum(n for _, n in hits)
    print(f"{len(hits)} note(s) contain secret-like values - {total} redaction(s)\n")
    for f, n in hits[:60]:
        print(f"  {n:>3}x  {core.portable(f)}")
    if len(hits) > 60:
        print(f"  ... and {len(hits) - 60} more")
    if not args.apply:
        print("\n(dry-run) add --apply to replace those values with '[redacted -> .env]' in place. Your .env is never touched.")
        return
    changed = core.apply_scrub(silos, extra)
    print(f"\n[ok] scrubbed {changed} note(s). Secret values now live only in your .env.")


def cmd_consolidate(args: argparse.Namespace) -> None:
    target = Path(args.to).resolve()
    if str(target).startswith(str(core.CLAUDE.resolve())):
        print("error: --to must not be inside ~/.claude")
        raise SystemExit(2)
    extra = [x for x in (args.also or "").split(",") if x]
    arteries = core.plan_consolidate(core.discover_silos(), args.min)
    notes = sum(len(v) for v in arteries.values())
    print(f"{len(arteries)} arteries from {notes} notes:\n")
    for k, files in sorted(arteries.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:40]:
        print(f"  {len(files):>3}  {k}")
    if len(arteries) > 40:
        print(f"  ... and {len(arteries) - 40} more")
    if not args.apply:
        print("\n(dry-run) add --apply to write one scrubbed MD per artery into the target dir.")
        return
    written = core.write_arteries(arteries, target, extra)
    print(f"\n[ok] wrote {len(written)} artery files to {target} (secrets scrubbed inline).")


def cmd_merge(args: argparse.Namespace) -> None:
    groups = core.find_name_duplicates(core.discover_silos())
    if not groups:
        print("no duplicate-named entries across silos - nothing to merge.")
        return
    red = sum(len(g.redundant) for g in groups)
    con = sum(len(g.conflicts) for g in groups)
    print(f"{len(groups)} duplicated name(s) across silos - {red} identical extra(s) to archive, {con} conflict(s) to flag\n")
    for g in groups[:40]:
        print(f"  {g.name}  -> keep {core.portable(g.canonical)}")
        for r in g.redundant:
            print(f"      identical (archive): {core.portable(r)}")
        for c in g.conflicts:
            print(f"      CONFLICT  (flag)   : {core.portable(c)}")
    if len(groups) > 40:
        print(f"  ... and {len(groups) - 40} more")
    if not args.apply:
        print("\n(dry-run) --apply archives the identical extras to ~/.claude/_dewey-retired (nothing deleted).")
        print("Conflicts (different content, e.g. per-agent notes) are only flagged, never moved - you resolve those.")
        return
    archive = core.merge_archive_dir()
    log = core.write_merge_log(groups, archive)
    moved = core.apply_merge(groups, archive)
    print(f"\n[ok] archived {moved} identical duplicate(s) to {archive} (nothing deleted).")
    print(f"     {con} conflict(s) left in place for you to resolve. recovery log: {log}")


def cmd_graph(args: argparse.Namespace) -> None:
    library = Path(args.to).resolve()
    if not library.is_dir():
        print(f"error: {library} is not a library directory (run sync first)")
        raise SystemExit(2)
    build = graph.build_graph(library)
    print(build.message)
    if build.ok:
        print(f"[ok] graph cached in {core.portable(build.out_dir)}")
        for a in build.artifacts:
            print(f"     {a.name}")
        print("The graph is a derived cache — rebuilt from the library, never a second source of truth.")
    else:
        raise SystemExit(1)


def cmd_brain(args: argparse.Namespace) -> None:
    library = Path(args.to).resolve()
    if not library.is_dir():
        print(f"error: {library} is not a library directory (run sync first)")
        raise SystemExit(2)
    out, n, m = brain3d.write_brain(library)
    print(f"[ok] living 3D brain: {core.portable(out)}")
    print(f"     {n} nodes, {m} links — nodes coloured by Dewey class, runners flow along every path.")
    print(f"     Open it in a browser. Each `dewey ask` lights the path it touched (via {brain3d.THOUGHT_JSON}).")


def cmd_dashboard(args: argparse.Namespace) -> None:
    library = Path(args.to).resolve()
    if not library.is_dir():
        print(f"error: {library} is not a library directory (run sync first)")
        raise SystemExit(2)
    out_dir = Path(args.out).resolve()
    claude_dir = Path(args.claude_dir).expanduser().resolve()
    index, stats = dashboard.write_dashboard(library, out_dir, claude_dir)
    print(f"[ok] 007-Bond cognition dashboard: {core.portable(index)}")
    print(f"     {stats['brainNodes']} nodes / {stats['brainLinks']} links · "
          f"{stats['daysActive']} days active · {stats['sessions']} sessions")
    print(f"     Serve the folder and open it fullscreen (vendored libs beside it).")


def cmd_ask(args: argparse.Namespace) -> None:
    library = Path(args.to).resolve()
    if not library.is_dir():
        print(f"error: {library} is not a library directory (run sync first)")
        raise SystemExit(2)
    res = graph.ask(library, args.question)
    # Fire the runners: record the path this thought touched so a living 3D brain lights it up.
    brain3d.write_thought(library, [e.name for e in res.entries[:args.limit]])
    print(f"[{res.mode}] {res.note}\n")
    if not res.entries:
        print("  no entries matched.")
        return
    for e in res.entries[:args.limit]:
        print(f"  {e.klass:13} {e.name}")
        if e.summary:
            print(f"                {e.summary[:100]}")
    shown = min(len(res.entries), args.limit)
    print(f"\n{shown} of {len(res.entries)} entr{'y' if len(res.entries) == 1 else 'ies'}. "
          f"Load with:  dewey checkout <name>")


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

    weave = sub.add_parser("weave", help="link the synced library into topic clusters + colour each class (Obsidian)")
    weave.add_argument("--to", required=True, help="the library directory created by sync")
    weave.set_defaults(fn=cmd_weave)

    micronise = sub.add_parser("micronise", help="shrink shelved silo files to pointers (content stays in the library; dry-run by default)")
    micronise.add_argument("--library", required=True, help="the library directory created by sync")
    micronise.add_argument("--apply", action="store_true", help="replace shelved silo files with pointers (re-verified; recovery log written)")
    micronise.set_defaults(fn=cmd_micronise)

    checkout = sub.add_parser("checkout", help="restore a shrunk entry to full content (so the assistant can read it)")
    checkout.add_argument("name", nargs="?", help="entry filename, e.g. project_foo.md (omit with --all)")
    checkout.add_argument("--all", action="store_true", help="check out every pointer stub")
    checkout.set_defaults(fn=cmd_checkout)

    checkin = sub.add_parser("checkin", help="sync a checked-out entry back to the library and re-shrink it")
    checkin.add_argument("name", nargs="?", help="entry filename (omit with --all)")
    checkin.add_argument("--all", action="store_true", help="check in every full (non-pointer) entry")
    checkin.add_argument("--library", required=True, help="the library directory created by sync")
    checkin.set_defaults(fn=cmd_checkin)

    merge = sub.add_parser("merge", help="consolidate duplicate-named entries across silos to one canonical copy (archives the rest; dry-run by default)")
    merge.add_argument("--apply", action="store_true", help="retire the extra copies to ~/.claude/_dewey-retired (nothing deleted; recovery log written)")
    merge.set_defaults(fn=cmd_merge)

    scrub = sub.add_parser("scrub", help="redact secret values from memory notes; your .env stays the single source (dry-run by default)")
    scrub.add_argument("--apply", action="store_true", help="rewrite notes with secret values replaced by [redacted -> .env]")
    scrub.add_argument("--also", help="comma-separated extra literal strings to redact (e.g. a known password)")
    scrub.set_defaults(fn=cmd_scrub)

    con = sub.add_parser("consolidate", help="stitch notes into one scrubbed Markdown per major artery (topic); dry-run by default")
    con.add_argument("--to", required=True, help="output directory for the artery MDs")
    con.add_argument("--min", type=int, default=2, help="min notes to form an artery (smaller fold into _misc)")
    con.add_argument("--also", help="comma-separated extra literal strings to scrub")
    con.add_argument("--apply", action="store_true", help="write the artery files")
    con.set_defaults(fn=cmd_consolidate)

    brain = sub.add_parser("brain", help="generate a living 3D brain (WebGL force-graph; runners fire on every thought)")
    brain.add_argument("--to", required=True, help="the library directory created by sync")
    brain.set_defaults(fn=cmd_brain)

    dash = sub.add_parser("dashboard", help="build the 007-Bond cognition dashboard (colourful neural brain + avatar + stats + charts)")
    dash.add_argument("--to", required=True, help="the library directory created by sync")
    dash.add_argument("--out", required=True, help="output directory for the dashboard product (vendored libs must sit in <out>/vendor)")
    dash.add_argument("--claude-dir", default="~/.claude", help="Claude Code dir holding stats-cache.json (default ~/.claude)")
    dash.set_defaults(fn=cmd_dashboard)

    graph_p = sub.add_parser("graph", help="build a queryable knowledge graph over the library (via Graphify; derived cache)")
    graph_p.add_argument("--to", required=True, help="the library directory created by sync")
    graph_p.set_defaults(fn=cmd_graph)

    ask = sub.add_parser("ask", help="find the few entries that answer a question (graph-guided; falls back to keyword)")
    ask.add_argument("question", help="a plain-language question about your memory")
    ask.add_argument("--to", required=True, help="the library directory created by sync")
    ask.add_argument("--limit", type=int, default=8, help="max entries to show (default 8)")
    ask.set_defaults(fn=cmd_ask)

    args = parser.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
