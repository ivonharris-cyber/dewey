<p align="center">
  <img src="assets/dewey-mascot.webp" width="150" alt="Dewey">
</p>

<h1 align="center">007‑Bond — the Dewey Cockpit</h1>

<p align="center"><b>A living brain and an agentic cockpit for your own AI — running on your mech, your network, your content and revenue.</b></p>

<p align="center"><i>No more "message me for how to set it up." Install it as an MCP, say <b>"Lets go"</b>, and the avatar walks you in.</i></p>

---

007‑Bond is what happens when [**Dewey**](#the-engine-dewey-a-living-brain) — the memory librarian that
collapses a coding assistant's memory to near‑zero tokens — grows a body. It fuses the Dewey library
(the brain), a Graphify‑style knowledge graph (the mind's eye), and a native Hermes/OpenClaw agent TUI
(the hands) into **one cockpit that boots your own AI with a full arsenal of tools out of the box.**

It speaks to you. A VRM **avatar with STT + TTS** guides the setup, reads its own thoughts aloud, and
reacts as the crew works — so onboarding is a conversation, not a wiki.

## Why it matters: 99.99% token savings

A coding assistant's context window is fixed. Your memory is not. Left alone, a brain grows past the
point it can ever be loaded at once. Dewey's answer is a librarian, not a bigger backpack: **ask for the
few entries you need, never carry the whole library.**

Measured live on a real estate (see [docs/BENCHMARK.md](docs/BENCHMARK.md)):

| Metric | Value |
|---|---:|
| Whole brain re‑read cold | ~1,445,000 tokens (7.2× over a 200K window) |
| One `dewey ask` (the 3 entries that answered it) | ~171 tokens |
| **Savings on recall** | **99.99% — 8,451× lighter, lossless** |

That is the whole thesis of the Bond evolution: **never repeat what you already learned.** In practice it
**stretches a Claude Pro subscription to the next tier's headroom without the next tier's price** — you
spend tokens on the work, not on re‑reading what you already know.

## The Cockpit — the 007 Dash

A completely customisable command surface (a WebGL cockpit you can embed or run standalone):

- **The living 3D brain** — your memory rendered as a colour‑classed neural graph; nodes light as the
  agent thinks, and click any node to read that (secret‑scrubbed) note.
- **Fable‑ready split mind** — a left panel that separates **Facts** from **Fiction / Thoughts**, so the
  reflective (dream‑state) mind and the waking (intellect) mind stay legibly apart.
- **The avatar** — VRM slot, **STT + TTS** two‑way voice, lip‑sync, and a bottom command bar to talk to
  your agent by keyboard or voice.
- **Live ops** — Tailscale network health, GPU/CPU/RAM, crons & backups, and an alert theatre that only
  cries wolf for the things that matter.

## Out of the box — the arsenal

007‑Bond exposes real tool surfaces the moment it boots, over the **native MCP**, so your agentic agent
starts in its own environment already holding:

- **Content & Revenue** — reels and content‑creation automation pipelines, **ComfyUI** and **RunPod**
  image/video generation, staged image UIs (Forge, A1111).
- **Cyber Security** — **Shannon** (autonomous white‑box AI pentester) and a **local Kali** (WSL2)
  lane — offensive tooling that stays on *your* machine, human‑in‑the‑loop.
- **Web & Commerce** — website launchers and **Shopify / WooCommerce** connectors for your storefronts.
- **The agent itself** — a native **OpenClaw / Hermes agent TUI**: pick your own model (NVIDIA NIM,
  z.ai GLM, local Ollama, Anthropic, and more), on your own keys.
- **Automation** — n8n workflows and Uptime Kuma monitoring, wired to the cockpit.

> Some surfaces ship as live connectors and some as staged panels you arm with your own keys — the
> cockpit is honest about which is which, and never fires anything outward without your say‑so.

## Connectors & Keys — the bottom‑left hub

A tabbed tool docked at the **bottom‑left of the 007 Dash** that makes onboarding self‑serve — monitor and
manage everything in one place. The design principle is Dewey's own: **stay honest, leak nothing.** Backed
by the `dewey connectors` engine (a `connectors.json` catalogue + a local ledger + a fernet key vault).

- **Subscriptions** — every service as a card: what it *powers*, an **Open** deep‑link to the provider's
  API‑key page (grab your key), a `✓ set / ✗ missing` pill (**never the value**), and a **$/mo billable
  wired to a local `expenses.csv`** with a running total.
- **BCP** — one‑click **Back up now** that triggers your proven `BCP‑to‑GoogleDrive` rclone task, with
  live rclone/last‑backup status.
- **MCP** — a **load‑and‑choice catalogue with popularity** (Obsidian, Notion, Full‑Note pages, Additional
  AI, Dewey, Graphify, …), each with an Install button that opens a human‑in‑the‑loop console.

**The hard rule — the honest key vault:**
- **`.env` is git‑ignored automatically** and never enters a commit (`dewey doctor` proves it — see [Security](#security)).
- **Keys are encrypted at rest** (fernet); the vault **unlocks once per session with a passphrase**, and
  **every AI command that needs a key passes a human‑in‑the‑loop approval** before release.
- **No key is ever echoed, pooled, or written into a note** — the cockpit panel and the `state` payload
  carry only names + booleans, never a value. **No leaked keys, anywhere.**

```bash
dewey connectors state --json     # what the cockpit panel reads (booleans only)
dewey connectors keys             # ✓/✗ per service
dewey connectors spend            # the $/mo total from your local ledger
dewey connectors mcp list         # the catalogue, by popularity
dewey connectors bcp status       # your Google‑Drive backup connector
pip install "dewey[vault]"        # add the encrypted key vault
```

## The engine: Dewey, a living brain

Under the cockpit is the original Dewey — **under 1,000 lines of dependency‑free Python** — that keeps the
brain small and honest. It maps your scattered memory silos, dates them, de‑duplicates them, and collapses
each oversized file into a pointer: a call number, a one‑line summary, and a link. The full content lives
once, in your Obsidian vault or Notion; the file the assistant loads each session shrinks from kilobytes
to bytes.

| Command | Description |
|---|---|
| `dewey sweep` / `dewey log` | List every memory silo / entry |
| `dewey sync --to DIR` | Copy memory into a browsable, classified Markdown library |
| `dewey weave --to DIR` | Cluster + colour the library into a Graphify‑style Obsidian graph |
| `dewey micronise` | Replace shelved silo files with pointers (reversible; never touches `MEMORY.md`) |
| `dewey checkout` / `checkin` | Restore an entry to full content, then re‑shrink it after edits |
| `dewey ask` | Ask the library one question; get back only the entries that answer it |

Entries are classified first by type — an established **fact** vs. a **proposal / idea / thought** — then
by subject in a Dewey `000`–`900` range. When an idea ships, it re‑files from *idea* to *fact*. That split
is exactly what the cockpit's Facts / Fiction panels render.

### Reference Desk (MCP)

```bash
pip install dewey[mcp]
DEWEY_LIBRARY=~/dewey-library dewey-mcp
```

Tools: `search`, `read_entry`, `catalogue`, `checkout`, `checkin`. The core stays dependency‑free — only
the server needs `mcp`.

## Install — "Lets go"

007‑Bond is designed to onboard *you*, not the other way around. Two paths:

1. **Guided (recommended).** Install the Dewey MCP, open the cockpit, and say **"Lets go."** The avatar
   prompts you through it, **human‑in‑the‑loop**, and can auto‑install the pieces it needs — pointing at
   your Obsidian vault, weaving the Graphify graph, and connecting your chosen agent.
2. **Manual.** Follow the MCP + **Obsidian Vault + Graphify** setup in [SETUP.md](SETUP.md).

```bash
pipx install git+https://github.com/ivonharris-cyber/dewey
dewey --version
dewey sweep          # map your existing memory
dewey ask "..."      # ask the librarian
```

The startup process hands the wheel to **your** choice of agentic agent, running on **your** mech, **your**
network, against **your** current content and revenue. No resume file to hunt for next session — the brain
already knows itself. Just say **"Lets go."**

## Security

- The repository is code only — never your data. Memory, `.env`, and credential files are excluded by
  `.gitignore` and skipped by `sync`/`micronise`.
- `dewey doctor` detects leaks (tracked `.env`, missing ignore rules) without printing any secret value.
- The cockpit's control surface is loopback‑only and token‑gated; the agent never posts anything outward
  without your approval.

## Docs

- [docs/BENCHMARK.md](docs/BENCHMARK.md) — the measured 99.99% / 8,451× token benchmark.
- [docs/DEWEY-GRAPHIFY-MELD.md](docs/DEWEY-GRAPHIFY-MELD.md) — how the Graphify knowledge‑graph layer melds in.
- [SETUP.md](SETUP.md) · [CHANGELOG.md](CHANGELOG.md) · [CONTRIBUTING.md](CONTRIBUTING.md)

## License

MIT — see [LICENSE](LICENSE).
