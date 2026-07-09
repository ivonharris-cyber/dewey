"""dewey brain — a LIVING 3D view of the memory.

Not a static model: a WebGL force-graph (vasturiano/3d-force-graph, Three.js) where
**directional particles run along the edges** — the synapse-runners firing between
notes. Nodes are coloured by Dewey class; the whole thing rotates, zooms, and pulses.

"Runners move every time you think": `dewey ask` writes the entries it touched to
`_brain-thought.json` beside the html; the viewer reads it and lights that path
brighter than the resting pulse. Retrieval = a thought = a burst of runners on that route.

The html is a DERIVED artifact — rebuilt from the library, never a source of truth.
Fully local: the only external fetch is the 3d-force-graph library from a CDN.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import core

_WIKILINK = re.compile(r"\[\[([^\]|#]+)")  # [[target]], [[target|alias]], [[target#h]]
BRAIN_HTML = "_brain-3d.html"
THOUGHT_JSON = "_brain-thought.json"


def _stem(name: str) -> str:
    return Path(name.strip()).stem.lower()


def extract_graph(library: Path) -> dict:
    """Nodes (entries, coloured by class) + links (resolved wikilinks) from the library."""
    entries = core.library_entries(library)
    by_stem: dict[str, core.Entry] = {_stem(e.name): e for e in entries}

    nodes = []
    for e in entries:
        colour = core._CLASS_COLORS.get(e.klass, "9AA0A6")
        nodes.append({
            "id": e.name,
            "label": e.name.replace(".md", ""),
            "klass": e.klass,
            "color": f"#{colour}",
            "summary": (e.summary or "")[:140],
        })

    seen = set()
    links = []
    for e in entries:
        try:
            text = e.path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in _WIKILINK.findall(text):
            tgt = by_stem.get(_stem(m))
            if tgt and tgt.name != e.name:
                key = (e.name, tgt.name)
                if key not in seen:
                    seen.add(key)
                    links.append({"source": e.name, "target": tgt.name})

    return {"nodes": nodes, "links": links}


def write_thought(library: Path, entry_names: list[str]) -> Path:
    """Record the path a thought just traversed so the living brain can light it up.

    entry_names is RANK-ORDERED: [0] is where the thought STARTED (the strongest
    hit — the origin), the rest are how far it reached. The viewer reads `origin`
    to mark the start-point and `active` (in order) to show the depth of the reach.
    """
    out = Path(library) / THOUGHT_JSON
    payload = {
        "origin": entry_names[0] if entry_names else None,
        "active": entry_names,
        "depth": len(entry_names),
    }
    out.write_text(json.dumps(payload), encoding="utf-8")
    return out


_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>VRAIN — living 3D brain</title>
<style>
  body {{ margin:0; background:#05060a; overflow:hidden; font-family:system-ui,sans-serif; }}
  #legend {{ position:fixed; top:12px; left:12px; z-index:10; color:#cfd3dc; font-size:12px;
            background:rgba(10,12,20,.6); padding:10px 12px; border-radius:8px; line-height:1.7; }}
  #legend b {{ color:#fff; }} .sw {{ display:inline-block; width:10px; height:10px; border-radius:50%;
            margin-right:6px; vertical-align:middle; }}
  #hint {{ position:fixed; bottom:12px; left:12px; z-index:10; color:#6b7280; font-size:11px; }}
</style></head><body>
<div id="legend"><b>VRAIN</b> — {n} nodes, {m} links · runners = active thought
<div id="classes"></div></div>
<div id="hint">drag to rotate · scroll to zoom · runners flow along every path; a thought lights its route brighter</div>
<div id="graph"></div>
<script src="https://unpkg.com/3d-force-graph"></script>
<script>
const DATA = {data};
const CLASSES = {classes};
const legend = document.getElementById('classes');
for (const [k,c] of Object.entries(CLASSES)) {{
  legend.innerHTML += `<div><span class="sw" style="background:${{c}}"></span>${{k}}</div>`;
}}
const Graph = ForceGraph3D()(document.getElementById('graph'))
  .graphData(DATA)
  .backgroundColor('#05060a')
  .nodeColor(n => n.color)
  .nodeLabel(n => `<div style="max-width:280px"><b>${{n.label}}</b><br><span style="color:#9aa0a6">${{n.summary}}</span></div>`)
  .nodeRelSize(3)
  .linkColor(() => 'rgba(120,130,160,0.25)')
  .linkDirectionalParticles(2)          // the runners — always flowing
  .linkDirectionalParticleWidth(1.6)
  .linkDirectionalParticleSpeed(0.006);

// "Runners move every time you think": poll the thought file; the active path
// gets brighter, faster, denser runners — a burst of synaptic traffic on that route.
let activeSet = new Set(), origin = null;
const think = document.createElement('div');
think.style = 'position:fixed;top:12px;right:12px;z-index:10;color:#ffd778;font-size:12px;background:rgba(10,12,20,.6);padding:8px 12px;border-radius:8px;max-width:320px';
document.body.appendChild(think);
async function pollThought() {{
  try {{
    const r = await fetch('{thought_json}?t=' + Date.now(), {{cache:'no-store'}});
    if (r.ok) {{ const j = await r.json(); activeSet = new Set(j.active || []); origin = j.origin; }}
  }} catch (e) {{}}
  const on = l => activeSet.has(l.source.id ?? l.source) && activeSet.has(l.target.id ?? l.target);
  Graph.linkDirectionalParticles(l => on(l) ? 8 : 2)
       .linkDirectionalParticleSpeed(l => on(l) ? 0.02 : 0.006)
       .linkColor(l => on(l) ? 'rgba(255,215,120,0.9)' : 'rgba(120,130,160,0.25)')
       // origin = where the thought STARTED (biggest, whitest); active = how DEEP it reached (gold)
       .nodeColor(n => n.id === origin ? '#fff2b0' : (activeSet.has(n.id) ? '#ffd778' : n.color))
       .nodeVal(n => n.id === origin ? 9 : (activeSet.has(n.id) ? 4 : 1));
  think.innerHTML = origin
    ? `<b>thinking…</b><br>started at: ${{(origin||'').replace('.md','')}}<br>depth: ${{activeSet.size}} node(s)`
    : 'resting — runners idle until a thought fires';
}}
pollThought();
setInterval(pollThought, 1500);
</script></body></html>
"""


def write_brain(library: Path) -> tuple[Path, int, int]:
    """Generate the living 3D brain html from the library. Returns (path, nodes, links)."""
    library = Path(library).resolve()
    data = extract_graph(library)
    classes = {k: f"#{v}" for k, v in core._CLASS_COLORS.items()
               if any(n["klass"] == k for n in data["nodes"])}
    html = _HTML.format(
        data=json.dumps(data),
        classes=json.dumps(classes),
        n=len(data["nodes"]),
        m=len(data["links"]),
        thought_json=THOUGHT_JSON,
    )
    out = library / BRAIN_HTML
    out.write_text(html, encoding="utf-8")
    return out, len(data["nodes"]), len(data["links"])
