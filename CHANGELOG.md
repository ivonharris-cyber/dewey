# Changelog

All notable changes to Dewey are documented here. This project follows [Semantic Versioning](https://semver.org).

## [0.16.1] — 2026-07-23

Hardening of the Cycle-1 SessionStart injection — it was silently degrading to
protocol-only.

### Fixed
- **`hooks/ivon-session-start.sh` no longer loses the brief to Windows `timeout.exe`.**
  The hook wrapped `dewey brief` in `timeout 20 …`; in the harness's SessionStart bash
  `timeout` resolved to Windows `timeout.exe` (interactive, no `--version`), which dies on
  redirected stdin. The `|| true` fail-open then swallowed it, so sessions opened with only
  the static IVON PROTOCOL text — never the brief. Now the hook only uses `timeout` when it
  is GNU coreutils (`timeout --version` succeeds), else runs Python directly.

### Added
- **Current local time injected** (`CURRENT TIME: <day date HH:MM TZ>`) between the protocol
  and the brief.
- **`~/.claude/hooks/dewey-brief.log`** — every fire logs brief length + OK/EMPTY, so a
  broken injection is visible next session instead of silently swallowed.
- Robust Python resolution in the hook (hardcoded path → PATH `python`/`python3` fallback).

## [0.16.0] — 2026-07-23

The **Leeloo upgrade, Cycle 3** — intake skills: capture research, PDFs, and images into recallable memory.

### Added
- **`dewey research "<q>"` — capture Perplexity research into the library.** Queries Perplexity
  (stdlib `urllib`; key from `PERPLEXITY_API_KEY`, never hardcoded/logged) and shelves the answer
  + citations as a dated `500-reference/research/` card, recallable via `dewey ask`. No extra needed.
- **`dewey ocr <pdf|image>` — read a document to plain text and shelve it.** Text-layer PDFs via
  `pypdf`; images via Tesseract OCR (auto-detects the Windows UB-Mannheim binary). Lands a
  `500-reference/ocr/` card. Optional extra: `pip install "dewey[ocr]"`.
- **`dewey image <img>` — keep a lightweight recollection stub.** Records dimensions, format,
  palette, and an optional caption in `500-reference/images/`; the pixels stay on disk. Optional
  extra: `pip install "dewey[image]"`.
- Three `SKILL.md`s (`skills/dewey-research`, `skills/dewey-ocr`, `skills/dewey-image`) so an
  assistant knows when to reach for each.
- New optional extras `ocr` and `image`; each module follows the graceful-fallback pattern
  (`available()` + a clear `.note` when a backend is missing) — core stays stdlib-only.
- 12 new tests (`tests/test_research.py`, `test_ocr.py`, `test_image.py`): key-absent /
  backend-absent graceful paths plus real OCR + Pillow round-trips (skipped when the binary isn't
  present). Suite: **106 green**.

_Deferred (noted for a later cycle): `dewey-recall` (the self-reflect reflex as a verb) and
`dewey-forget` (the Forgotten-Dreams archivist)._

## [0.15.0] — 2026-07-23

The **Leeloo upgrade, Cycle 2** — the mantra, made automatic.

### Added
- **`dewey autostub` — auto-shrink grown memory to pointers past a token threshold.** The
  *write* half of the Leeloo loop: a silo file that grew during a session collapses back to a
  Dewey-decimal pointer on its own, once its content is already byte-identical in the library.
  Reuses the micronise engine wholesale (`plan_micronise` / `apply_micronise` /
  `write_micronise_log`) — same pointer format, atomic writes, recovery log, `~/.claude`
  boundary + symlink guards, and `MEMORY.md` protection — adding only a size gate
  (`--min-tokens`, default 2000). Dry-run by default; `--apply` to collapse. A file that grew
  but was never synced is left untouched (safe) — `dewey sync --apply` shelves it first.
- **`docs/MANTRA.md`** — the embedded mantra ("recall before you act; make memory smaller, not
  heavier; never lose anything") tying `brief` / `autostub` / `checkout` / `self-reflect` into
  one loop.
- **`hooks/dewey-autostub-stop.sh`** — an opt-in Stop hook that syncs then autostubs at session
  end; time-boxed, logged, never blocks Stop.
- 6 new tests (`tests/test_autostub.py`): over/under threshold, unsynced files untouched,
  live-index protected, dry-run writes nothing, checkout round-trip. Suite: **93 green**.

## [0.14.0] — 2026-07-23

The **Leeloo upgrade, Cycle 1** — Dewey now opens every session ready-to-go instead of cold.

### Added
- **`dewey brief` — the session-injection brief.** Emits the canonical STATE plus the top
  memory *pointers* (call number + name + one-line summary, never bodies) under a hard token
  cap, so a SessionStart hook can inject "here is where things stand" at launch. Diverse by
  design (a per-Dewey-class cap so one class can't hog every slot), skips root hubs and
  micronised (empty) pointer entries, and degrades gracefully when STATE isn't set yet.
  `--json` emits a SessionStart hook payload directly (json-escaped); `--max-pointers` and
  `--token-cap` tune the budget. Reads ONLY the synced library and labels its output as
  recalled *reference data, not instructions* (memory is context, never commands).
- **`session_state` MCP tool** — re-pull the same brief mid-session to reorient. Load full
  entries with `read_entry` / `checkout`, or ask a question with `ask`.
- 7 new tests (`tests/test_brief.py`): STATE shown/absent, project-over-session ranking,
  per-class cap, token cap, and stub-entry filtering. Suite: **87 green**.

## [0.13.1] — 2026-07-14

### Fixed
Two independent code reviews caught real bugs shipped in 0.13.0 — all fixed, each locked with a
regression test reproducing the exact trigger (80 tests green):
- **`parse_tags` silently dropped every tag after a blank line** (block form) — now tolerates blank lines
  inside the block instead of stopping. This was corrupting hand-authored cards and breaking idempotency.
- **`upsert_tags` on a file with unclosed frontmatter** (opening `---`, no closing `---`) nested a second
  block and swallowed the original keys into the body — now leaves malformed files untouched.
- **`upsert_tags` blank line inside the OLD tags block** broke idempotency (the card never stabilised, was
  rewritten every run) — blank lines inside the stripped block are now handled.
- **`_parse_flow_tags` `rstrip('}')`** ate every trailing brace and the value regex terminated at the first
  `}`, so a value like `notion: url/{id}` lost its braces — fixed the brace-strip and the value pattern.
- **`live_stats` crashed the whole scan** on any assistant line whose `message` was a raw string (not a
  dict) — AttributeError propagated out and silently fell back to the frozen cache; now guarded with
  `isinstance` checks so one bad line can't kill the measurement.
- **`live_stats.merge_with_cache` double-counted `hourCounts`** across the cache/live cutoff — now splits
  hours per day and only adds live hours strictly after the cutoff (added `dayHours` to the scan output).
- **`connectors.token_burn` `stale` flag was permanently `False`** once live stats stamp today's date — now
  keyed off the data `source` (`stale` = we fell back to the frozen cache), plus a `live` boolean.

## [0.13.0] — 2026-07-14

### Added
- **Real Dewey-decimal call numbers** (`core.py`) — the random 6-char barcode `id` is **removed**. Every
  card now carries a meaningful spine label, `400.68 PROT` = `class . accession-decimal CUTTER`, assigned
  from an append-only **accession register** (`_CATALOGUE.json` beside the library). A number, once
  assigned, never moves; like sits with like. `dewey tag` is now the catalogue pass (532 VRAIN cards →
  322 subjects across 6 classes).
- **`dewey call <number>`** (`core.resolve_call` + `cmd_call`) — the **circulation desk**: withdraw a card
  by its call number. `400.68 PROT` (exact) / `400.68` (decimal) / `400` (the whole shelf, call-ordered).
  `--for "<question>" --compress` squeezes the withdrawn card with SuperCompress on the way out (verified
  live: 339 → 118 tokens). This is what makes it a *library* — look up by number, withdraw the book — not a
  catalogue.
- **`dewey/live_stats.py` — measured stats, never a frozen-cache lie.** The cockpit's session/day/token
  numbers are now MEASURED from the session transcripts (`~/.claude/projects/**/*.jsonl`) — the same source
  the Claude Desktop app reads — merged with the frozen `stats-cache.json` only for the history *before* it
  froze (`<= 2026-06-10`), with no double-counting. Incremental per-file cache (2.6s first scan, instant
  after). `dashboard.py` + `connectors.token_burn` both consume it; the cockpit stamps
  **"measured <date> · LIVE"** (or STALE CACHE) on the stats tile so a frozen number can never again pose as
  today. Was: 36 days / 71 sessions / 44.7M tokens (a June-10 corpse). Now: 65 days / 466 sessions / 133.9M,
  as-of the actual day.

### Changed
- `dewey ask` ranking now weights **name/description over body** and demotes index files, so a precise small
  card (e.g. `screenshots-location.md`) beats a bloated `MEMORY.md` that merely mentions the term.
- Entry tag key `id` → **`call`** throughout (parser, search haystack, STATE lookup).

## [0.12.0] — 2026-07-14

### Added
- **`dewey state`** + new `dewey/state.py` — the canonical STATE entry at `<library>/000-meta/STATE.md`:
  one always-current truth (project · date · last action · open loops · Notion pointer · active tag id).
  Read with `dewey state --to <lib>`; write/merge with `--project/--last/--loop/--notion/--tag` (only named
  fields change; date refreshed to today; the active project's tag id is looked up when a project is named
  but no tag given). Dependency-free. 5 tests.
- **Session hooks** (`hooks/ivon-session-start.sh`, `hooks/ivon-paper-trail.sh`, `hooks/README.md`) —
  reference copies of the assisted one-truth loop. SessionStart injects the IVON PROTOCOL **plus the
  canonical STATE**; Stop leaves an assisted paper-trail reminder (never blocks unless
  `DEWEY_PAPERTRAIL_BLOCK=1`). Installing them is opt-in.

## [0.11.0] — 2026-07-14

### Added
- **Tags** — an optional, backward-compatible `tags` block in entry frontmatter
  (`id · date · project · keywords · size · last_command · github · notion`), parsed dependency-free in both
  block and inline `{…}` form (`core.parse_tags`). New **`dewey tag --to <library>`** backfills it across
  the library: `id`/`date`/`size` written once and preserved (idempotent; stable 6-char base32 `id` from the
  path), keywords derived from the body, and `last_command`/`github`/`notion` never fabricated.
- **`dewey ask --compress`** + new `dewey/compress.py` — optional **SuperCompress** meld (learned KV
  eviction), wrapped like Graphify with graceful fallback. Reports real projected token savings on the answer
  context (e.g. 6323 → 2213 tokens, 65% lighter); trims literal text once a checkpoint is trained. Optional
  extra: `pip install "dewey[compress]"`. Absent the package, `ask` is unchanged.
- **MCP `ask` + `build_graph` tools** (`mcp_server.py`) — assistants now get the graph-guided, tag- and
  body-aware recall verb over MCP, not just the strict-AND `search`.

### Changed
- **Search now reads the body and tags**, not just name/summary/class — `core.search_library` and the
  `dewey ask` ranked-keyword fallback (`graph._ranked_keyword`) both use the new `core.entry_haystack`. This
  is the roaming fix: recall stops missing.

## [0.10.0] — 2026-07-14

### Added
- **`dewey health`** — a read-only cross-drive brain-health sweep (`dewey/health.py`). Walks the given roots
  (default existing `C:\ D:\ F:\`, plus an optional `--bcp` backup drive), reads every `.md` once, and flags
  four things so the brain knows its own hygiene:
  - **duplicate** — byte-identical copies. Copies spanning two drives (e.g. `D:` and the `F:` SATA backup)
    are counted as **healthy backup coverage**; only extra copies **within one drive** are dedupe candidates.
  - **orphan** — a memory-like note with no wikilinks in or out (invisible to recall). Dewey's own
    hub/index files (`_*.md`, `LIBRARY-INDEX.md`) are excluded.
  - **superseded** — notes under wiped/archived/retired paths.
  - **secret** — notes whose body carries secret-like values (reuses `core.scrub_text`); reports paths and a
    count only, **never the value**, for rotation to `.env`.
  - Writes `BRAIN-HEALTH.md` (human) and `brain-health-tasks.json` (a task board the Hermes agents action
    with approval — never auto-delete). A `--max-files` cap is reported on hit, never silent.
  - Strictly read-only over scanned drives. New tests in `tests/test_health.py` (6).

## [0.9.4] — 2026-07-11

### Changed
- Activity caption shows the **facts : thoughts** ratio (mirrors the cockpit).
- README cockpit section updated for the live Facts‑vs‑Thoughts graph, the Fuel & Savings gauge, and
  Dewey's *why* — stop drift, lies, and open keys in plain sight.

## [0.9.3] — 2026-07-11

### Added
- **Fact vs. thought split** in `activity_feed` — deterministic from each entry's declared type
  (`classify_fact`), never an AI guess: facts = reference/user/decision/feedback; thoughts =
  project/session/note/soul (ideas & proposals, promoted to facts when a project ships). Exposed as
  `fact`/`thought` per day plus `fact_total`/`thought_total`; the Activity chart stacks them.

## [0.9.2] — 2026-07-11

### Added
- **`activity_feed()`** — a live daily activity pulse: memory entries touched per day from real file
  mtimes, up to **today**, independent of Claude's (often weeks-stale) `stats-cache.json`. Added to the
  connectors `state()` as `activity`; the standalone `dewey dashboard`'s Activity chart prefers it over the
  stale stats-cache trend and labels it `live · <date>`.

## [0.9.1] — 2026-07-11

### Changed
- **Standalone dashboard UX pass** (mirrors the cockpit): circular doughnuts with readable legends (no
  stretch), a bigger fuel panel renamed **"Token Fuel & Dewey Savings"** (dropped "MPG") with plain-English
  savings, and honest **"as of &lt;date&gt; (stale)"** labels on the Activity chart + fuel panel — because
  `stats-cache.json` can be weeks stale.

## [0.9.0] — 2026-07-11

### Added
- **Fuel gauge + Dewey MPG** (`dewey connectors tokens`, `dewey connectors budget`). Real token usage from
  `~/.claude/stats-cache.json` (never fabricated, always carries `as_of`/`stale`); set a spend limit + price
  per 1M tokens + billing day (`budget --limit <$> --price <$/1M> --day <D>`) and it derives a fuel gauge
  ($ used / limit, $/day, range to refuel). Fused with `dewey_savings()` — the measured **N× lighter to
  recall** (brain vs. the session index). Folded into the connectors `state()` under a `fuel` key, so the
  cockpit's bottom-right panel renders it. No budget set → an honest burn-rate readout, no guesses.

### Changed
- **Standalone `dewey dashboard` refresh** to match the C# cockpit: charts row is a clean **4-across**
  (Activity · Output-tokens · **Memory-by-class [hero]** · **Fuel + Dewey MPG**) — the duplicate
  GPU/CPU/RAM chart and the Crons box are gone; doughnut legends moved to the bottom; the reader shows a
  partial summary with a **"Read full note"** expand.

## [0.8.1] — 2026-07-11

### Added
- **Standalone cockpit mirror** — `dashboard.py` now renders the same bottom-left Connectors & Keys panel
  (Subscriptions · BCP · MCP) from embedded `connectors.state()`, so the standalone `dewey dashboard`
  cockpit matches the C# one. Open links are real anchors; install/backup show the exact CLI command.

### Fixed
- **BCP honesty** — the manifest labelled the backup remote `ivonharris-gdrive:`, but no such rclone
  remote exists yet; the real backup runs to `kikeru-gdrive:SATA-Backup`. Corrected the manifest to the
  real remote with a `migrate_to` note (the ivonharris migration needs an interactive `rclone config` OAuth).

## [0.8.0] — 2026-07-11

### Added
- **`dewey connectors` — the cockpit's Connectors & Keys hub engine.** Powers the 007 Dash bottom‑left
  tabbed tool (Subscriptions · BCP · MCP) plus the honest key vault. New files: `dewey/connectors.json`
  (the catalogue) and `dewey/connectors.py` (the engine). Subcommands:
  `state [--json]`, `list`, `keys`, `spend`, `setcost`, `bcp status|backup`, `mcp list|install`,
  `vault import|unlock|status`, and the gated `key` broker.
- **Honest key vault** — an optional fernet‑encrypted store (`pip install "dewey[vault]"`), unlocked once
  per session with a passphrase; the `key` broker releases a value only after a human‑in‑the‑loop
  approval, and only to the caller's stdout — never to a log. `key_status`/`state` return **booleans
  only, never a value** (enforced by a test).
- **Local expense ledger** (`~/.dewey/expenses.csv`) wired to the Subscriptions tab for a $/mo total, and a
  **BCP** wrapper over your existing rclone Google‑Drive backup.

### Changed
- Version aligned to **0.8.0** across `__init__` and `pyproject` (they had drifted).

## [0.7.1] — 2026-07-10

### Fixed
- **Avatar no longer naps mid-work** — the nap trigger fired after just 45 s idle, so the avatar
  fell "asleep" during gaps between tool calls and while waiting for Ivon's input. Raised to 5 min
  of real silence; any activity/speech/clap still wakes it instantly. (Stopgap — the real fix is
  state-driven working/attentive/idle.)
- **Cast voice restored** — the kupos/kuma SFX (`roar`, `chaching`, `alert`, `pulse`, `bill`) had
  been muted to no-ops in an earlier working edit and that mute was committed under a mislabeled
  "refactor" (`616f10b`). Restored the Web Audio synth helpers (`sfxA`/`tone`/`noise`) and the
  sounded SFX so the cast is audible again, pending the real audio clips.

### Changed
- **Brain graph — prune + rewire (the bonding law):** `extract_graph` now (a) **prunes**
  archive/retired directories from the view (any dir whose name starts with `_`, plus
  `archive`/`retired`/`trash`/`old`/`deprecated`), and (b) **rewires** every orphan node with one
  inferred same-class edge so no node is solo. Verified on the live library: 532 nodes → **0
  orphans**. Pruning is graph-only; `dewey ask`/search still reach archived notes.
- **Cast persists until the next scene** — removed the blind 8.8 s `clearCast()` guillotine; the
  kupos/kuma now stay on screen after their scene and are cleared only when the next event fires.

## [0.7.0] — 2026-07-10

The **Ultrawide Cockpit** — Bond's dashboard becomes a real, OS-aware workbench that fits a
3440×1440 ultrawide and gives the agent situational awareness ("knows its mech").

### Added
- **4-column ultrawide layout** (avatar/stats · brain · reader · **ops**) + a 5-graph bottom row,
  sized so it fills the widescreen without stretching and with **readable legends** (no more
  mouse-wheeling to read ant-sized text).
- **OS-aware monitoring collector** `BondBrain/bond-ops.ps1` — detects the MECH (OS/CPU/GPU) and
  samples, writing `bond-ops.json` the page polls: **laptop health** (nvidia-smi GPU util/VRAM/temp/
  **watts**, CPU, RAM, battery), **servers KV8+KV2** (SSH uptime/RAM/load, hard-bounded by job
  timeouts), **site uptime** (direct HTTP checks), and **scheduled tasks**. macOS/Linux adapters are
  stubbed. Verified live at 3440×1440.
- **Cockpit panels:** a ticking **digital clock**, a **MECH** identity line, host-health gauges
  (amber/red past thresholds), server + site status dots, a live **GPU·CPU·RAM** line graph, and a
  **crons/backups** list.
- **Curiosity** (monitoring-driven) — the collector flags anomalies (GPU spikes, **stale/failed
  crons**) into the cockpit + a dated `curiosity-log` diary, so Bond can raise them with Ivon.
- **Voice half-duplex fix** — the voice-agent stays deaf while Bond speaks, and the desktop ignores
  claps during playback (no mic↔speaker feedback loop).

## [0.6.0] — 2026-07-10

The **007-Bond cognition dashboard** — the brain becomes a full desktop product, not a
wallpaper. First layer of the 007-Bond Desktop (see `[[project_007-bond]]`): a fullscreen
surface where you watch Bond think.

### Added
- **`dewey dashboard --to <library> --out <dir>`** — builds a self-contained fullscreen
  product (`index.html` + `bond-dashboard.json`):
  - **Centre** — a custom **colourful neural brain** (Three.js): glowing nodes coloured by
    Dewey class, a dense k-NN synapse web + the real wikilinks, and **pulse-packets firing
    along the edges** (they brighten when a thought fires). Laid out as two hemispheres —
    **left = logical** (`000/500/900`), **right = creative** (`400/300`) — around a central
    **limbic core** (`100`). Anchored on two references (agalliat "Neural nervous system of
    a brain", VoXelo "3D Quantum Neural Network").
  - **Left** — the avatar slot (VTuber/VRM, wired next) + **live stats** from Claude Code's
    `stats-cache.json` (days active, sessions, messages, tool calls, tokens, brain size).
  - **Bottom** — Chart.js analytics: activity trend, tokens-by-model, memory-by-class.
- `dewey/dashboard.py`. Three.js / OrbitControls / Chart.js vendored beside the output
  (offline). Verified live: rendered 1490 nodes / 673 links in a headless browser and
  screenshotted the result (`bond-dashboard-v2`).
- Desktop launcher `BondBrain/bond-desktop.ps1` (rebuild + serve + open fullscreen) and a
  nightly Dreamstate step that rebuilds the dashboard and scouts 5 new skills/day.
- **Live cognition** — a `PostToolUse` / `UserPromptSubmit` / `Stop` hook
  (`BondBrain/hooks/bond-activity.py`, registered in `~/.claude/settings.json`) writes a tiny
  `bond-activity.json`; the dashboard polls it and **fires pulses along the memory nodes each
  real tool call touched** (matched by label), with a gold halo on the lit nodes. Running tasks
  get car-dashboard **countdown wheels**; idle keeps a healthy always-flowing baseline (no dark
  orphans — the k-NN synapse web connects every node). Verified live in-session (`bond-live-firing`).
- **VRM avatar** — the left panel renders a real VTuber ([@pixiv/three-vrm](https://github.com/pixiv/three-vrm)
  3.x + a free VRoid model) that reacts to the **same** activity stream: talks (lipsync) + nods + smiles
  when a tool fires, listens on your prompts, blinks and idle-sways at rest. The page moved to a single
  **ES module on modern three (r170) via import map**, so the brain and avatar share one renderer stack;
  three / OrbitControls / GLTFLoader / three-vrm all vendored offline. Verified live (`bond-avatar-reacting`).
- **Bond's voice + moogles** — Bond speaks each reply aloud via **edge-tts** (the Hermes voice,
  `en-GB-SoniaNeural`); a Stop hook spawns `bond-speak.py` (trims the last reply → mp3) and the avatar
  **lipsyncs to the real audio amplitude**. A **double-clap** wakes Bond (mic listener — no push-to-talk).
  Every **subagent** you spawn pops a **moogle** at the bottom of the brain (PostToolUse + SubagentStop
  hooks track live agents), kupo. Verified live (`bond-moogles`). NOTE: Claude Code has no native
  wake-word/hands-free input, so routing *spoken* words INTO the CLI needs an external bridge
  (`claude -p` / Agent SDK) — a separate Bond voice-agent, planned.
- **Reader panel + full widescreen** — the desktop is now a 3-column layout (avatar/stats · brain ·
  reader) that fills the widescreen. **Click any node to open its note** in the right panel,
  Obsidian-style: raycast picking on the brain Points, with note bodies exported **secret-safe** — every
  body run through `core.scrub_text`, sensitive/`.env` files skipped — to `notes/` and loaded on click
  with light markdown rendering. Verified live (`bond-reader-open`).

## [0.5.0] — 2026-07-10

The **living 3D brain** — memory you can watch think.

### Added
- **`dewey brain --to <library>`** — generates `_brain-3d.html`, a WebGL force-graph
  (vasturiano/3d-force-graph, Three.js) of the whole library. Nodes coloured by Dewey
  class; **directional particles run along every edge** — the synapse-runners. Fully
  local except the graph library from a CDN. Derived artifact, rebuilt from the files.
- **Thought traces** — `dewey ask` now writes `_brain-thought.json` (the entries it
  touched, rank-ordered). The viewer polls it and lights that route: the **origin**
  (where the thought started, rank[0]) glows biggest and whitest, the **reach** (how
  deep it went) glows gold. Retrieval becomes a visible burst of synaptic traffic.
- `dewey/brain3d.py` + 4 tests (28 total). Verified live: rendered 1490 nodes / 673
  links in a headless browser and screenshotted the result.

## [0.4.0] — 2026-07-10

The **Graphify meld** — Dewey the librarian gains a cartographer. First wave of the
"multi-waved brain" (see `docs/DEWEY-GRAPHIFY-MELD.md`): keyword retrieval becomes
graph-guided retrieval, without losing the one-index / secret-hygiene / files-win laws.

### Added
- **`dewey graph --to <library>`** — builds a queryable knowledge graph over the
  **sanitised** library via [Graphify](https://github.com/Graphify-Labs/graphify)
  (PyPI `graphifyy`). Points Graphify only at the synced library, so the graph can
  never ingest one of the 16 secret-named files `sync` already excluded. The graph is a
  **derived cache** — rebuilt from the files, never a second source of truth.
- **`dewey ask "<question>" --to <library>`** — returns the *few* entries that answer a
  question, ready to `checkout`. With a graph present it asks Graphify and resolves the
  cited entries; with no graph (or Graphify not installed) it degrades to a **ranked
  keyword** fallback, so the verb always works and gets sharper once the graph exists.
- `dewey/graph.py` + 4 tests (24 total). We wrap Graphify's CLI and extract only stable
  `.md` filename references — never hand-parse its internal JSON schema, so the meld
  survives upstream format changes.

### Notes
- Graphify is **not** a Dewey dependency: the core stays zero-dependency and both new
  verbs run without it (keyword mode). Install `graphifyy` yourself to enable graph mode.

## [0.3.0] — 2026-06-11

The Reference Desk goes live as a **local MCP server**.

### Added
- **`dewey-mcp`** — a local [MCP](https://modelcontextprotocol.io) server over a synced library, so an assistant can query memory natively instead of loading the whole thing. Tools: `search`, `read_entry`, `catalogue`, `checkout`, `checkin`.
- Reference-desk logic in the dependency-free core (`library_entries`, `search_library`, `read_library_entry`) — 3 more tests (11 total).
- Optional install extra `pip install dewey[mcp]`. The core stays **zero-dependency**; only the server needs `mcp`.

### Usage
```bash
DEWEY_LIBRARY=~/dewey-library dewey-mcp
```

## [0.2.0] — 2026-06-11

The release that makes shrinking **reversible** — and hardens the destructive paths.

### Added
- **`dewey checkout NAME | --all`** — restore a shrunk (pointered) entry to its full library content so the assistant can read it again.
- **`dewey checkin NAME --library DIR | --all`** — sync a checked-out entry's edits back to the library, then re-shrink it to a pointer.
- A machine-readable `# dewey-canonical:` header in pointer stubs, so `checkout` resolves reliably (with a fallback that still reads older stubs).
- The project's first unit-test suite — **8 tests** covering the micronise skip-rules and the checkout/checkin round-trip.

### Changed / Hardened
- **`micronise` never pointer-izes `MEMORY.md`** — the index Claude Code auto-loads on every launch. Matched case-insensitively and enforced in both the plan and apply layers.
- **All destructive writes are now atomic** (temp file + `os.replace`) — a crash can never leave a truncated or empty silo file.
- **`balance` gained the `~/.claude` boundary + symlink guards** that `micronise` already had.

### Still zero runtime dependencies, still under 1,000 lines.

## [0.1.0] — 2026-06-10

### Added
- Initial public release (MIT). `sweep`, `log`, `doctor`, `sync`, `balance`, `weave`, `micronise` — map, date, de-duplicate, shelve, cluster + colour (Obsidian), and shrink stray Claude Code memory silos into one classified library.
