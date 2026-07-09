# Dewey × Graphify — Meld Design (EXPLORE → PLAN)

**Status:** PLAN (2026-07-10). Not yet built. Own EXPLORE→PLAN→BUILD→TEST→DOCUMENT session to follow.
**Goal (Ivon):** meld Dewey into Graphify with new features — a *scalable multi-waved brain that
interlinks, succincts token usage*; take the Dewey system "to the internet-of-things wiki."

---

## 1. EXPLORE — what each tool actually is

### Dewey (ours, `ivonharris-cyber/dewey`, public)
The **librarian**. Operates on scattered `.md` memory silos:
- `sweep`/`log` — inventory + date-order every entry across 17 silos / 545 entries.
- `sync` — mirror silos → one canonical Markdown library (VRAIN), **skips 16 sensitive/secret files**.
- `balance` — dedupe across silos, replace exact dupes with pointers.
- `weave` — link the library into topic clusters + colour each Dewey class (Obsidian graph view).
- `micronise` / `checkout` / `checkin` — shrink shelved entries to pointers; restore on demand. **This is the token-saver**: less-not-more, collapse to pointers.
- `doctor` — scan repos for committed `.env` leaks.
- `merge` / `scrub` / `consolidate` — reconciliation.
**Strengths:** governance, secret-hygiene, human-readable, Dewey-decimal discipline, ONE INDEX law.
**Weakness:** retrieval is keyword/pointer. It can't answer "what connects X to Y" cheaply.

### Graphify (`Graphify-Labs/graphify`, 80.9k★, YC S26, forked → `ivonharris-cyber/graphify`)
The **cartographer**. Turns a folder into a **queryable knowledge graph**:
- `graphify .` → `graph.json` (traversable graph), `graph.html` (clickable), `GRAPH_REPORT.md`.
- `explain <node>` / `path A B` / `query "<question>"` — traverse, don't grep.
- Code parsed **locally via tree-sitter AST — no LLM, nothing leaves the machine** (~40 langs).
  Docs/PDF/image/video use a semantic pass (model or configured key) — **opt-in only**.
- Every edge tagged `EXTRACTED` (explicit) vs `INFERRED` (resolved) — honesty built in.
- **Not embeddings** — a real graph. God-nodes, Leiden communities, cross-file links.
- Benchmarks: beats mem0 + supermemory on LOCOMO recall; **0 LLM credits to build the graph**.
- Ships a `--platform hermes` AND `--platform claw` AND `--platform agents` installer.

### The insight
They are **different organs, not competitors**. Dewey = governance + hygiene + human view.
Graphify = relationship retrieval + machine query. Ivon already chose Dewey over supermemory;
Graphify beats supermemory on the same benchmarks → this is the retrieval layer Dewey never had.
The 2nd-most-starred graphify-adjacent repo is literally "Obsidian + Graphify memory, 71.5× fewer
tokens/session" — the meld is a proven pattern, we just do it with governance + IoT reach on top.

---

## 2. PLAN — the meld ("multi-waved brain")

**Architecture law (unbroken):** ONE INDEX, ONE LIBRARY. The graph is a **derived cache**, rebuilt
from the files, never hand-edited, never a second source of truth. Files win every disagreement.

### The waves (why "multi-waved")
1. **Wave 0 — Silos** (raw `~/.claude/.../memory/`): unchanged. Capture layer.
2. **Wave 1 — Library** (VRAIN, Dewey `sync`): canonical, sanitized, human-readable, Dewey-classed.
3. **Wave 2 — Graph** (Graphify over Wave 1): the interlink layer — query/path/explain for the agent.
4. **Wave 3 — Pointers** (Dewey `micronise`): the succinct layer — the graph tells you *which* few
   entries to `checkout`, so a query loads 3 pointers instead of 545 files. **This is the token win.**

Retrieval flow: agent asks a question → **graph** finds the subgraph (cheap, local) → returns the
handful of entry IDs → Dewey `checkout` loads only those → answer. Today Dewey guesses by keyword;
with the graph it *knows the path*.

### New features to build INTO Dewey (the meld, not a bolt-on)
- **`dewey graph`** — wrap `graphify` over the synced library; write `graph.json` beside the index.
  Respects the sensitive-skip list (graph never ingests the 16 secret files).
- **`dewey ask "<question>"`** — graph query → entry IDs → auto-`checkout` → assembled context.
  The retrieval verb Dewey lacks. Token-metered (logs tokens-to-answer, extends the 770K→800 bench).
- **`weave` upgrade** — today weave does topic clusters by hand-ish rules; regenerate the Obsidian
  colouring FROM the Graphify communities (Leiden) so the human graph view and the machine graph agree.
- **`micronise` feedback loop** — use graph **degree/centrality** to decide what to shrink: god-nodes
  stay full, leaf entries collapse to pointers first. Data-driven succinctness.
- **Edge honesty carries through** — surface Graphify's `EXTRACTED`/`INFERRED` tags in `dewey ask`
  output, matching the "evidence beside every claim / never fabricate" law.

### "Internet of Things wiki" — the scale-out
The same pipeline pointed at MORE than markdown:
- Point `dewey graph` at each **repo** (onda-platform, valuepod, shop) → code knowledge graphs the
  agents query instead of re-grepping (`what calls /complete?`). Graphify does this LLM-free.
- **Federated graphs**: one graph per node/project, a thin top index stitching them (mirrors the
  mesh: KV8, KV2, laptop). "Multi-waved" across machines, not just layers.
- **Agent access**: Graphify ships `--platform hermes` + `--platform claw` — Chewy and The Doc can
  each carry a `graphify` skill over THEIR scoped brain (The Doc queries the valuepod graph, never yours).
  This is the "IoT wiki": every agent/device a node, each with a local graph, one governance layer (Dewey).

---

## 3. Guardrails (the laws this must not break)
- **Secrets:** graph builds ONLY over the Dewey-synced library (16 sensitive files already excluded).
  Never point Graphify at raw silos, `.env`, or the master env. Verify local-only before first media pass.
- **ONE INDEX:** `00-INDEX.md` stays the index. Graph = disposable derived artifact.
- **Reuse-first:** forked to `ivonharris-cyber/graphify` (done) — add a README note on WHY we forked
  before we depend on it (upstream is YC-backed + fast-moving; pin a known-good tag).
- **Compare-before-create:** extend Dewey's CLI, don't fork a parallel tool. One brain, more organs.

## 4. Build order (next session)
1. Fork README note + pin upstream tag. Secret-scan the fork.
2. `pip install graphifyy`; `dewey graph` wrapper over VRAIN; eyeball `graph.html`.
3. `dewey ask` — measure tokens-to-answer vs `dewey search` on 5 real questions (BENCH gate).
4. If it wins: `weave`←communities, `micronise`←centrality, ship as Dewey minor version + CHANGELOG.
5. Stretch: per-repo graphs + Hermes/Claw skill install for Chewy + The Doc.

## 5. Backups done this session (2026-07-10)
- VRAIN → `ivonharris-cyber/vrain` (PRIVATE); 18 secret-flagged files git-excluded (queued for scrub + rotation).
- Dewey → `ivonharris-cyber/dewey` pushed current.
- Graphify → forked to `ivonharris-cyber/graphify`.
