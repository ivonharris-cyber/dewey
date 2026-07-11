# Changelog

All notable changes to Dewey are documented here. This project follows [Semantic Versioning](https://semver.org).

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
