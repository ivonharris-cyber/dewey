"""Command-line entry point for Dewey."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import (__version__, core, graph, brain3d, dashboard, connectors, health, compress, state,
               brief as brief_mod, autostub as autostub_mod,
               research as research_mod, ocr as ocr_mod, image_stub as image_mod)

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


def cmd_health(args: argparse.Namespace) -> None:
    roots = [Path(r).resolve() for r in args.root] if args.root else health.default_roots(args.bcp)
    if not roots:
        print("error: no roots to sweep (none of C:/D:/F: exist — pass --root <dir>)")
        raise SystemExit(2)
    print(f"Sweeping (read-only) for .md across: {', '.join(str(r) for r in roots)}")
    print("This can take a while on a full drive — pruning build/system dirs.\n")
    snap = health.sweep(roots, max_files=args.max_files)
    report, tasks = health.write_reports(snap, Path(args.out).resolve())
    redundant = sum(1 for n in snap.notes if n.redundant)
    secrets = sum(1 for n in snap.notes if n.secret_hits)
    orphans = sum(1 for n in snap.notes if n.orphan)
    superseded = sum(1 for n in snap.notes if n.superseded)
    print(f"[ok] read {len(snap.notes)} notes"
          + ("  ⚠️ FILE CAP HIT (results truncated — raise --max-files)" if snap.capped else ""))
    print(f"     dedupe={redundant}  secrets={secrets}  superseded={superseded}  orphans={orphans}")
    print(f"     report: {core.portable(report)}")
    print(f"     tasks : {core.portable(tasks)}  (Hermes actions these — with approval, never auto-delete)")


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


def cmd_autostub(args: argparse.Namespace) -> None:
    library = Path(args.library).resolve()
    if not library.is_dir():
        print(f"error: {library} is not a library directory (run sync first)")
        raise SystemExit(2)
    ap = autostub_mod.plan_autostub(core.discover_silos(), library, min_tokens=args.min_tokens)
    plan = ap.plan
    if not plan.targets:
        print(f"nothing to autostub — no synced silo file is at/over {ap.min_tokens} tokens "
              f"({ap.skipped_small} smaller shelved file(s) left in place).")
        print("If this session added content, run `dewey sync --apply` first to shelve it, then retry.")
        return
    saved = plan.before_bytes - plan.after_bytes
    pct = saved / plan.before_bytes * 100 if plan.before_bytes else 0
    print(f"{len(plan.targets)} grown file(s) at/over {ap.min_tokens} tok can shrink to pointers "
          f"({ap.skipped_small} smaller left alone):")
    print(f"  before: {plan.before_bytes/1024:.0f} KB  ->  after: {plan.after_bytes/1024:.1f} KB   ({pct:.0f}% smaller)")
    if not args.apply:
        print("\n(dry-run) add --apply to replace those grown silo files with pointers "
              "(full content stays in the library; recovery log written).")
        return
    log = core.write_micronise_log(plan)
    done = core.apply_micronise(plan)
    print(f"\n[ok] autostubbed {done} file(s) — grown memory returned to pointers. recovery log: {core.portable(log)}")


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


def cmd_state(args: argparse.Namespace) -> None:
    library = Path(args.to).resolve()
    if not library.is_dir():
        print(f"error: {library} is not a library directory (run sync first)")
        raise SystemExit(2)
    writing = any(v is not None for v in (args.project, args.last, args.loop, args.notion, args.tag))
    if writing:
        st, path = state.update_state(
            library, project=args.project, last=args.last,
            loops=args.loop, notion=args.notion, tag=args.tag,
        )
        print(f"[ok] STATE updated: {core.portable(path)}")
    else:
        st = state.read_state(library)
        if st is None:
            print("no STATE yet — set it, e.g:\n"
                   '  dewey state --to <library> --project ngati-toa --last "submitted the pepeha"')
            return
    print(f"\n  Project:     {st.project or '—'}")
    print(f"  As of:       {st.date or '—'}")
    print(f"  Last action: {st.last or '—'}")
    print(f"  Notion:      {st.notion or '—'}")
    print(f"  Active tag:  {st.tag or '—'}")
    print("  Open loops:  " + (", ".join(st.loops) if st.loops else "(none)"))


def cmd_brief(args: argparse.Namespace) -> None:
    library = Path(args.to).resolve()
    if not library.is_dir():
        print(f"error: {library} is not a library directory (run sync first)")
        raise SystemExit(2)
    b = brief_mod.build_brief(library, max_pointers=args.max_pointers, token_cap=args.token_cap)
    if args.json:
        # Emit a SessionStart hook payload directly, json-escaped — the hook can
        # echo this as-is, or merge our text with its own protocol block.
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "SessionStart", "additionalContext": b.text}}))
        return
    print(b.text, end="")


def cmd_tag(args: argparse.Namespace) -> None:
    library = Path(args.to).resolve()
    if not library.is_dir():
        print(f"error: {library} is not a library directory (run sync first)")
        raise SystemExit(2)
    plan, register = core.plan_tag(library)
    print(f"{len(plan.targets)} entr{'y' if len(plan.targets) == 1 else 'ies'} to catalogue "
          f"({plan.unchanged} already carry their call number).")
    for path, _ in plan.targets[:20]:
        print(f"  catalogue  {core.portable(path)}")
    if len(plan.targets) > 20:
        print(f"  ... and {len(plan.targets) - 20} more")
    if not args.apply:
        print("\n(dry-run) add --apply to stamp each card's Dewey call number (e.g. 400.03 HAPA)")
        print(f"and grow the accession register ({core.CATALOGUE_NAME}).")
        return
    done = core.apply_tag(library, plan, register)
    subjects = sum(len(v) for v in register.values())
    print(f"\n[ok] catalogued {done} card{'s' if done != 1 else ''} — "
          f"{subjects} subjects across {len(register)} classes in the register.")
    print("     call · date · project · keywords · size — recall reads tags + body.")


def cmd_call(args: argparse.Namespace) -> None:
    library = Path(args.to).resolve()
    if not library.is_dir():
        print(f"error: {library} is not a library directory (run sync first)")
        raise SystemExit(2)
    hits = core.resolve_call(library, args.number)
    if not hits:
        print(f"nothing on the shelf at '{args.number}'. Try a class (e.g. 400) or `dewey ask`.")
        raise SystemExit(1)
    if len(hits) > 1:
        # a shelf/class was named — hand back the shelf list, call-number ordered
        print(f"shelf {args.number.strip().upper()} — {len(hits)} cards:\n")
        for e in hits:
            print(f"  {e.tags.get('call', '?'):14} {e.name}")
        print(f"\nWithdraw one:  dewey call \"{hits[0].tags.get('call', '')}\" --to <library>")
        return
    e = hits[0]
    text = e.path.read_text(encoding="utf-8", errors="ignore")
    print(f"═══ {e.tags.get('call', '')}  ·  {e.name}  [{e.klass}]  ═══\n")
    if args.compress and args.reason:
        comp = compress.compress(text, args.reason)
        if comp.ok:
            print(f"🧠 SuperCompress [{comp.policy}] against \"{args.reason}\": "
                  f"{comp.original_tokens} → {comp.kept_tokens} tokens ({comp.saved_pct}% lighter)\n")
            print(comp.text)
            return
        print(f"(compress unavailable: {comp.note})\n")
    print(text)


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
    if args.compress:
        bodies = [core.read_library_entry(library, e.name) or "" for e in res.entries[:args.limit]]
        comp = compress.compress("\n\n".join(b for b in bodies if b), args.question)
        if comp.ok:
            print(f"\n🧠 SuperCompress [{comp.policy}]: {comp.original_tokens} → {comp.kept_tokens} "
                  f"tokens ({comp.saved_pct}% lighter) for the model's context.")
        else:
            print(f"\n(compress) {comp.note}")


def cmd_research(args: argparse.Namespace) -> None:
    library = Path(args.to).resolve()
    if not library.is_dir():
        print(f"error: {library} is not a library directory (run sync first)")
        raise SystemExit(2)
    res = research_mod.capture(library, args.question, model=args.model)
    if not res.ok:
        print(f"(research) {res.note}")
        raise SystemExit(1)
    print(f"[ok] research captured: {core.portable(res.path)}  ({len(res.citations)} citation(s))")
    print(f"     recall it later:  dewey ask \"{args.question[:40]}\" --to <library>")
    if args.show:
        print("\n" + res.content[:1500] + ("…" if len(res.content) > 1500 else ""))


def cmd_ocr(args: argparse.Namespace) -> None:
    library = Path(args.to).resolve()
    if not library.is_dir():
        print(f"error: {library} is not a library directory (run sync first)")
        raise SystemExit(2)
    res = ocr_mod.capture(library, Path(args.file))
    if not res.ok:
        print(f"(ocr) {res.note}")
        raise SystemExit(1)
    print(f"[ok] ocr [{res.method}] -> {core.portable(res.path)}  ({len(res.text)} chars)")


def cmd_image(args: argparse.Namespace) -> None:
    library = Path(args.to).resolve()
    if not library.is_dir():
        print(f"error: {library} is not a library directory (run sync first)")
        raise SystemExit(2)
    res = image_mod.capture(library, Path(args.file), caption=args.caption)
    if not res.ok:
        print(f"(image) {res.note}")
        raise SystemExit(1)
    m = res.meta
    print(f"[ok] image stub -> {core.portable(res.path)}")
    if "width" in m:
        print(f"     {m.get('format')} {m['width']}x{m['height']}  palette {m.get('palette')}")


def cmd_connectors(args: argparse.Namespace) -> None:
    op = args.op
    if op == "state":
        st = connectors.state()
        if args.json:
            print(json.dumps(st))
            return
        s = st["spend"]
        print("Subscriptions")
        for sub in st["subscriptions"]:
            pill = "✓" if sub["ready"] else "✗"
            print(f"  {pill} {sub['name']:26} ${sub['cost_month']:>6}/mo   {sub['powers']}")
        print(f"  ── TOTAL  ${s['total_month']}/mo\n")
        b = st["bcp"]
        print(f"BCP → {b['remote']}{b['target']}   rclone={'ok' if b['rclone'] else 'MISSING'}")
        print(f"Vault: available={st['vault']['available']} exists={st['vault']['exists']}")
        print(f"MCP: {len(st['mcps'])} in catalogue")
        return
    if op == "list":
        for c in connectors.load_manifest():
            print(f"  [{c.get('kind','?'):12}] {c['id']:18} {c.get('name','')}")
        return
    if op == "keys":
        for cid, keys in connectors.key_status().items():
            for k, present in keys.items():
                print(f"  {'✓' if present else '✗'} {k:26} ({cid})")
        return
    if op == "spend":
        s = connectors.spend_summary()
        for it in s["items"]:
            print(f"  {it['name']:28} {it['currency']} {it['cost_month']:>7.2f} /mo")
        print(f"\n  TOTAL  {s['currency']} {s['total_month']:.2f} /mo   → {s['ledger']}")
        return
    if op == "setcost":
        if not args.arg or args.cost is None:
            print("usage: dewey connectors setcost <id> --cost <amount>")
            raise SystemExit(2)
        connectors.set_cost(args.arg, args.cost)
        print(f"[ok] {args.arg} = {args.cost}/mo")
        return
    if op == "bcp":
        which = args.arg or "status"
        if which == "status":
            b = connectors.bcp_status()
            print(f"  remote:  {b['remote']}{b['target']}")
            print(f"  rclone:  {'found' if b['rclone'] else 'NOT FOUND'}  {b['rclone_path']}")
            print(f"  task:    {b['task']}")
            print(f"  last:    {b['last_log'] or '(no log yet)'}")
        elif which == "backup":
            r = connectors.bcp_backup(dry_run=not args.apply)
            print(f"  $ {r['cmd']}\n  {'ok' if r['ok'] else 'FAILED'}")
            if r["out"]:
                print(r["out"])
            if not args.apply:
                print("\n  (dry-run) add --apply to really upload.")
        return
    if op == "mcp":
        which = args.arg or "list"
        if which == "list":
            for c in connectors.mcp_list():
                print(f"  {c.get('popularity',0):>4}k★  {c['id']:16} {c.get('name','')}")
                print(f"           {c.get('powers','')}")
        elif which == "install":
            if not args.arg2:
                print("usage: dewey connectors mcp install <id> [--library DIR]")
                raise SystemExit(2)
            cmd = connectors.mcp_install_cmd(args.arg2, library=args.library)
            if cmd:
                print(f"  run this to install (human-in-the-loop):\n\n    {cmd}\n")
            else:
                print(f"  '{args.arg2}' is user-defined — add its install command in connectors.json.")
        return
    if op == "tokens":
        st = connectors.fuel_panel()
        if args.json:
            print(json.dumps(st))
            return
        b, sv = st["burn"], st["savings"]
        if not b.get("available"):
            print("  no token stats yet (~/.claude/stats-cache.json)")
            return
        print(f"  as of {b['as_of']}" + ("  (STALE)" if b.get("stale") else ""))
        print(f"  cumulative out {b['cumulative']:,}  ·  this cycle {b['cycle_tokens']:,}  ·  avg/day {b['avg_day']:,}")
        g = b.get("gauge")
        if g:
            rng = f"{g['range_days']}d" if g["range_days"] is not None else "—"
            print(f"  ⛽ FUEL  ${g['usd_used']} / ${g['limit_usd']}  ({g['pct']}%)  ·  ${g['usd_per_day']}/day  ·  range {rng}  ·  resets in {b['reset_in_days']}d")
        else:
            print("  (set a limit + price for the fuel gauge:  dewey connectors budget --limit 100 --price 15 --day 15)")
        if sv.get("available"):
            print(f"  🧠 DEWEY MPG  brain {sv['brain_mb']}MB → recall ~{sv['recall_tokens']:,} tok  =  {sv['multiplier']}× lighter ({sv['pct_lighter']}%)")
        return
    if op == "budget":
        if args.limit is None and args.price is None and args.day is None:
            b = connectors.read_budget()
            print(f"  limit=${b.get('spend_limit_usd')}  price=${b.get('price_per_1m_usd')}/1M  day={b.get('billing_day')}")
            return
        b = connectors.set_budget(limit=args.limit, price=args.price, day=args.day)
        print(f"  [ok] limit=${b.get('spend_limit_usd')}  price=${b.get('price_per_1m_usd')}/1M  billing day={b.get('billing_day')}")
        return
    if op == "vault":
        import getpass
        which = args.arg or "status"
        if which == "status":
            print(f"  available: {connectors.vault_available()}   exists: {connectors.vault_exists()}")
        elif which == "import":
            if not connectors.vault_available():
                print('  vault needs the [vault] extra:  pip install "dewey[vault]"')
                raise SystemExit(2)
            p1 = getpass.getpass("  set vault passphrase: ")
            if not p1 or p1 != getpass.getpass("  confirm passphrase: "):
                print("  passphrases empty or don't match.")
                raise SystemExit(2)
            n = connectors.vault_import(p1)
            print(f"  [ok] encrypted {n} keys into {connectors.VAULT}")
        elif which == "unlock":
            v = connectors.unlock(getpass.getpass("  vault passphrase: "))
            print(f"  [ok] unlocked — {len(v.names())} keys this session: {', '.join(v.names())}")
        return
    if op == "key":
        # The gated broker: unlock -> HITL approval -> release the value to stdout ONCE.
        # This is the ONLY path that emits a secret value, and only to the caller's stdout.
        import getpass
        if not args.arg:
            print('usage: dewey connectors key <ENV_NAME> --for "reason"')
            raise SystemExit(2)
        v = connectors.unlock(getpass.getpass("  vault passphrase: "))
        reason = args.reason or "(unspecified)"
        if input(f"  release {args.arg} for: {reason}?  [y/N] ").strip().lower() != "y":
            print("  denied.", file=sys.stderr)
            raise SystemExit(1)
        val = v.get(args.arg)
        if val is None:
            print(f"  {args.arg} not in vault", file=sys.stderr)
            raise SystemExit(1)
        print(val)  # only place a value is emitted — to the caller, never a log
        return


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

    health_p = sub.add_parser("health", help="read-only cross-drive brain-health sweep (duplicates, orphans, superseded, secrets)")
    health_p.add_argument("--root", action="append", help="a drive/dir to sweep (repeatable; overrides the C:/D:/F: default)")
    health_p.add_argument("--bcp", help="path to the BCP/DCP backup drive to include in the default sweep")
    health_p.add_argument("--out", default=".", help="where to write BRAIN-HEALTH.md + brain-health-tasks.json (default: cwd)")
    health_p.add_argument("--max-files", type=int, default=60000, help="safety cap on notes read (a hit is reported, never silent)")
    health_p.set_defaults(fn=cmd_health)

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

    autostub = sub.add_parser("autostub", help="the mantra, automatic: shrink grown, already-synced silo files to pointers past a token threshold (dry-run by default)")
    autostub.add_argument("--library", required=True, help="the library directory created by sync")
    autostub.add_argument("--min-tokens", type=int, default=autostub_mod.DEFAULT_MIN_TOKENS, dest="min_tokens",
                          help=f"only shrink files at/over this many tokens (default {autostub_mod.DEFAULT_MIN_TOKENS})")
    autostub.add_argument("--apply", action="store_true", help="replace grown silo files with pointers (re-verified; recovery log written)")
    autostub.set_defaults(fn=cmd_autostub)

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

    state_p = sub.add_parser("state", help="read/write the canonical STATE entry — one truth, read first every session")
    state_p.add_argument("--to", required=True, help="the library directory created by sync")
    state_p.add_argument("--project", help="set the current project")
    state_p.add_argument("--last", help="set the last action")
    state_p.add_argument("--loop", action="append", help="set an open loop (repeatable; replaces the list)")
    state_p.add_argument("--notion", help="set the Notion pointer (the TRUTH artifact)")
    state_p.add_argument("--tag", help="set the active project's tag id (else looked up by project)")
    state_p.set_defaults(fn=cmd_state)

    brief_p = sub.add_parser("brief", help="emit the session-injection brief: STATE + top pointers under a token cap")
    brief_p.add_argument("--to", required=True, help="the library directory created by sync")
    brief_p.add_argument("--max-pointers", type=int, default=brief_mod.DEFAULT_MAX_POINTERS,
                         dest="max_pointers", help=f"max pointers to show (default {brief_mod.DEFAULT_MAX_POINTERS})")
    brief_p.add_argument("--token-cap", type=int, default=brief_mod.DEFAULT_TOKEN_CAP,
                         dest="token_cap", help=f"hard token ceiling for the whole brief (default {brief_mod.DEFAULT_TOKEN_CAP})")
    brief_p.add_argument("--json", action="store_true", help="emit a SessionStart hook JSON payload (json-escaped) instead of plain text")
    brief_p.set_defaults(fn=cmd_brief)

    tag = sub.add_parser("tag", help="backfill a tags block (id·date·project·keywords·size) into every library entry")
    tag.add_argument("--to", required=True, help="the library directory created by sync")
    tag.add_argument("--apply", action="store_true", help="write the tags block into each entry (default: dry-run)")
    tag.set_defaults(fn=cmd_tag)

    call = sub.add_parser("call", help="withdraw a card by its Dewey call number (e.g. 400.68), or list a shelf (e.g. 400)")
    call.add_argument("number", help="a call number: '400.68 PROT' (exact), '400.68' (decimal), or '400' (shelf)")
    call.add_argument("--to", required=True, help="the library directory created by sync")
    call.add_argument("--for", dest="reason", help="the question to SuperCompress the withdrawn card against")
    call.add_argument("--compress", action="store_true", help="squeeze the card against --for on the way out (optional tool)")
    call.set_defaults(fn=cmd_call)

    ask = sub.add_parser("ask", help="find the few entries that answer a question (graph-guided; falls back to keyword)")
    ask.add_argument("question", help="a plain-language question about your memory")
    ask.add_argument("--to", required=True, help="the library directory created by sync")
    ask.add_argument("--limit", type=int, default=8, help="max entries to show (default 8)")
    ask.add_argument("--compress", action="store_true", help="report SuperCompress token savings on the answer context (optional tool)")
    ask.set_defaults(fn=cmd_ask)

    research_p = sub.add_parser("research", help="ask Perplexity and shelve the answer as a recallable library card")
    research_p.add_argument("question", help="the research question")
    research_p.add_argument("--to", required=True, help="the library directory created by sync")
    research_p.add_argument("--model", default=research_mod.DEFAULT_MODEL,
                            help=f"Perplexity model (default {research_mod.DEFAULT_MODEL})")
    research_p.add_argument("--show", action="store_true", help="also print the answer to the console")
    research_p.set_defaults(fn=cmd_research)

    ocr_p = sub.add_parser("ocr", help="read a PDF/image to plain text and shelve it as a recallable card")
    ocr_p.add_argument("file", help="a .pdf or image file to read")
    ocr_p.add_argument("--to", required=True, help="the library directory created by sync")
    ocr_p.set_defaults(fn=cmd_ocr)

    image_p = sub.add_parser("image", help="keep a lightweight recollection stub of an image (pixels stay on disk)")
    image_p.add_argument("file", help="an image file to stub")
    image_p.add_argument("--to", required=True, help="the library directory created by sync")
    image_p.add_argument("--caption", help="an optional human caption to store with the stub")
    image_p.set_defaults(fn=cmd_image)

    con = sub.add_parser("connectors", help="the cockpit connectors/keys hub: subscriptions, BCP, MCP, vault")
    con.add_argument("op", choices=["state", "list", "keys", "spend", "setcost", "bcp", "mcp", "vault", "key", "tokens", "budget"])
    con.add_argument("arg", nargs="?", help="sub-verb (bcp/mcp/vault) or id (setcost/key)")
    con.add_argument("arg2", nargs="?", help="target id, e.g. 'mcp install <id>'")
    con.add_argument("--json", action="store_true", help="machine-readable output (for the cockpit)")
    con.add_argument("--for", dest="reason", help="reason a key is requested (the key broker)")
    con.add_argument("--library", default="", help="library dir for MCP install templating")
    con.add_argument("--cost", type=float, help="monthly cost, for setcost")
    con.add_argument("--limit", type=float, help="fuel: spend limit in USD (the tank)")
    con.add_argument("--price", type=float, help="fuel: price per 1M tokens in USD (price per litre)")
    con.add_argument("--day", type=int, help="fuel: billing day of month the cycle resets on")
    con.add_argument("--apply", action="store_true", help="really run (bcp backup uploads for real)")
    con.set_defaults(fn=cmd_connectors)

    args = parser.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
