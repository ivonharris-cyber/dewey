"""dewey dashboard — 007-Bond Desktop, v1: a fullscreen cognition dashboard.

The living brain becomes the centre of a real product surface, not a wallpaper:
  · CENTRE  — a colourful neural brain (Three.js): glowing nodes coloured by Dewey
              class, a dense synapse web, pulse-packets FIRING along the edges. Two
              hemispheres (left = logical, right = creative) + a central limbic core.
              Ambient pulses keep it alive; the thought path (dewey ask) fires brighter.
  · LEFT    — the avatar slot (VTuber, wired later) + live STATS (days active, sessions,
              messages, tool calls, tokens, brain size) from the real Claude Code stats.
  · BOTTOM  — analytics: an activity trend line + model-token and memory-class doughnuts.

Self-contained: data is inlined into the page; Three.js / OrbitControls / Chart.js are
vendored beside it. A derived artifact — rebuilt from the library + the local stats.
Endgame is a native Windows product (Ivon in C / a WebView2 shell); this is v1.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from . import brain3d, core

NOTES_DIR = "notes"
_NOTE_MAX = 6000

DASHBOARD_HTML = "index.html"
DASHBOARD_JSON = "bond-dashboard.json"

# Vivid neural palette (overrides the muted class colours for the glowing look).
_VIVID = {
    "000-meta": "#22d3ee",       # cyan   — logical
    "100-people": "#f472b6",     # pink   — limbic / emotive core
    "300-agents": "#a78bfa",     # violet — creative
    "400-projects": "#34d399",   # emerald— creative
    "500-reference": "#60a5fa",  # blue   — logical
    "900-sessions": "#fbbf24",   # amber  — logical
}
_FALLBACK = "#c4b5fd"

# left hemisphere = logical, right = creative, centre = limbic/emotive
_REGION = {
    "000-meta": "left", "500-reference": "left", "900-sessions": "left",
    "400-projects": "right", "300-agents": "right",
    "100-people": "core",
}


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower().replace(".md", "")).strip("-")


def write_notes(library: Path, out_dir: Path) -> int:
    """Export each note's body — SCRUBBED of secrets — for the reader panel. Secret-safe:
    sensitive/.env files are skipped entirely; every body runs through core.scrub_text."""
    notes = Path(out_dir) / NOTES_DIR
    notes.mkdir(parents=True, exist_ok=True)
    written = 0
    for e in core.library_entries(library):
        if core.is_sensitive(e.name) or core.is_env_file(e.name):
            continue
        try:
            body = e.path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        scrubbed, _ = core.scrub_text(body)
        (notes / f"{_slug(e.name)}.md").write_text(scrubbed[:_NOTE_MAX], encoding="utf-8")
        written += 1
    return written


def _load_stats(claude_dir: Path) -> dict:
    p = Path(claude_dir) / "stats-cache.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _load_tasks(out_dir: Path) -> list:
    """Optional: current tasks to render as bright nodes in the brain."""
    p = Path(out_dir) / "tasks.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def assemble_data(library: Path, claude_dir: Path, out_dir: Path) -> dict:
    graph = brain3d.extract_graph(Path(library))
    for n in graph["nodes"]:
        n["color"] = _VIVID.get(n["klass"], _FALLBACK)
        n["region"] = _REGION.get(n["klass"], "core")
        n["slug"] = _slug(n["id"])

    stats = _load_stats(claude_dir)
    daily = stats.get("dailyActivity", [])
    model_usage = stats.get("modelUsage", {})

    tokens_out = sum(m.get("outputTokens", 0) for m in model_usage.values())
    tool_calls = sum(d.get("toolCallCount", 0) for d in daily)

    trend = [
        {"date": d["date"], "messages": d.get("messageCount", 0),
         "tools": d.get("toolCallCount", 0)}
        for d in daily[-30:]
    ]
    model_tokens = [
        {"model": k.replace("claude-", ""), "out": v.get("outputTokens", 0)}
        for k, v in sorted(model_usage.items(), key=lambda kv: -kv[1].get("outputTokens", 0))
    ]
    class_dist = Counter(n["klass"] for n in graph["nodes"])

    return {
        "nodes": graph["nodes"],
        "links": graph["links"],
        "vivid": _VIVID,
        "stats": {
            "daysActive": len(daily),
            "sessions": stats.get("totalSessions", 0),
            "messages": stats.get("totalMessages", 0),
            "toolCalls": tool_calls,
            "tokensOut": tokens_out,
            "firstSession": stats.get("firstSessionDate", ""),
            "brainNodes": len(graph["nodes"]),
            "brainLinks": len(graph["links"]),
        },
        "trend": trend,
        "modelTokens": model_tokens,
        "classDist": [{"klass": k, "count": c, "color": _VIVID.get(k, _FALLBACK)}
                      for k, c in class_dist.most_common()],
        "tasks": _load_tasks(out_dir),
    }


def write_dashboard(library: Path, out_dir: Path, claude_dir: Path) -> tuple[Path, dict]:
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    data = assemble_data(library, claude_dir, out_dir)

    (out_dir / DASHBOARD_JSON).write_text(json.dumps(data), encoding="utf-8")
    write_notes(library, out_dir)
    html = _TEMPLATE.replace("__DATA__", json.dumps(data))
    index = out_dir / DASHBOARD_HTML
    index.write_text(html, encoding="utf-8")
    return index, data["stats"]


# ---------------------------------------------------------------------------
# The product page. Plain string (NOT an f-string / .format) so JS braces are
# safe; the data is injected via the __DATA__ token.
# ---------------------------------------------------------------------------
_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>007 · BOND — cognition</title>
<style>
  :root {
    --bg:#06070c; --panel:rgba(18,20,30,.55); --edge:rgba(140,150,190,.14);
    --ink:#e8ebf4; --dim:#8b90a4; --gold:#ffd778; --accent:#7dd3fc;
    --font:'Segoe UI',"Google Sans",system-ui,sans-serif;
  }
  * { box-sizing:border-box; }
  html,body { margin:0; height:100%; background:var(--bg); color:var(--ink);
              font-family:var(--font); overflow:hidden; }
  #app { position:fixed; inset:0; display:grid;
         grid-template-columns:300px minmax(540px,1fr) 326px 384px; grid-template-rows:1fr 300px; gap:12px; padding:12px; }
  /* reader panel (right) */
  #reader { grid-row:1; grid-column:3; display:flex; flex-direction:column; padding:16px 18px; overflow:hidden; }
  #reader-head { border-bottom:1px solid var(--edge); padding-bottom:11px; margin-bottom:12px; flex:0 0 auto; }
  #reader-title { font-size:15px; color:var(--ink); font-weight:600; }
  #reader-sub { font-size:11px; color:var(--dim); margin-top:5px; letter-spacing:.1em; }
  #reader-sub .chip { display:inline-block; border:1px solid; border-radius:20px; padding:2px 9px; font-size:10px; letter-spacing:.08em; }
  #reader-body { overflow:auto; font-size:12.5px; line-height:1.65; color:#c3c8d6; white-space:pre-wrap; word-break:break-word; }
  #reader-body h4 { color:#fff; font-size:13px; margin:13px 0 3px; }
  #reader-body code { background:rgba(255,255,255,.07); padding:1px 5px; border-radius:5px; color:var(--gold); font-size:11.5px; }
  #reader-body .wl { color:var(--accent); }
  /* ops / cockpit right column */
  #ops { grid-row:1; grid-column:4; display:flex; flex-direction:column; padding:14px 15px; gap:11px; overflow:auto; }
  #clockbox { text-align:center; }
  #clock-time { font-size:40px; font-weight:600; letter-spacing:.03em; color:#fff; line-height:1; font-variant-numeric:tabular-nums; }
  #clock-date { font-size:12px; letter-spacing:.2em; color:var(--dim); margin-top:5px; text-transform:uppercase; }
  #mech { font-size:11px; color:#9aa0b2; text-align:center; letter-spacing:.05em; border-bottom:1px solid var(--edge); padding-bottom:11px; }
  #mech b { color:#7dd3fc; }
  .ops-h { font-size:11px; letter-spacing:.16em; color:var(--dim); text-transform:uppercase; margin:2px 0 4px; }
  .metric { margin:6px 0; }
  .metric .lab { display:flex; justify-content:space-between; font-size:12px; color:#c3c8d6; margin-bottom:3px; }
  .metric .lab b { color:#fff; font-variant-numeric:tabular-nums; }
  .bar { height:7px; border-radius:4px; background:rgba(255,255,255,.08); overflow:hidden; }
  .bar > span { display:block; height:100%; border-radius:4px; background:#34d399; transition:width .4s, background .4s; }
  .bar.warn > span { background:#fbbf24; } .bar.crit > span { background:#f87171; }
  .srv, .site { display:flex; align-items:center; gap:8px; font-size:12.5px; color:#c3c8d6; padding:3px 0; }
  .dot { width:9px; height:9px; border-radius:50%; flex:0 0 auto; box-shadow:0 0 8px currentColor; }
  .dot.up { background:#34d399; color:#34d399; } .dot.down { background:#f87171; color:#f87171; }
  .srv .meta, .site .meta { margin-left:auto; color:var(--dim); font-size:11px; font-variant-numeric:tabular-nums; }
  #curiosity { margin-top:auto; }
  #curiosity .c { color:#fbbf24; font-size:11.5px; line-height:1.5; padding:3px 0; }
  #curiosity .ok { color:#5b6070; font-size:11.5px; }
  .panel { background:var(--panel); border:1px solid var(--edge); border-radius:16px;
           backdrop-filter:blur(9px); }
  /* left column */
  #left { grid-row:1; grid-column:1; display:flex; flex-direction:column; padding:18px; gap:16px; overflow:hidden; }
  #brandbar { display:flex; align-items:center; gap:12px; }
  #sigil { width:46px; height:46px; border-radius:50%; position:relative; flex:0 0 auto;
           background:conic-gradient(from 0deg,#22d3ee,#a78bfa,#f472b6,#fbbf24,#22d3ee);
           animation:spin 9s linear infinite; box-shadow:0 0 26px rgba(125,211,252,.5); }
  #sigil::after { content:''; position:absolute; inset:5px; border-radius:50%; background:#06070c; }
  #sigil::before { content:'007'; position:absolute; inset:0; display:grid; place-items:center;
                   font-size:13px; letter-spacing:.12em; color:var(--gold); z-index:2; font-weight:600; }
  @keyframes spin { to { transform:rotate(360deg); } }
  .brand h1 { margin:0; font-size:20px; letter-spacing:.30em; }
  .brand small { color:var(--dim); letter-spacing:.22em; font-size:10px; }
  /* avatar */
  #avatar { position:relative; height:200px; border-radius:14px; overflow:hidden; flex:0 0 auto;
            background:radial-gradient(circle at 50% 42%,rgba(125,211,252,.16),transparent 62%);
            border:1px solid var(--edge); display:grid; place-items:center; }
  #face { width:120px; height:120px; border-radius:50%; position:relative;
          background:radial-gradient(circle at 50% 40%,#1b2740,#0a1120 70%);
          box-shadow:0 0 40px rgba(125,211,252,.35), inset 0 0 30px rgba(125,211,252,.25); }
  .eye { position:absolute; top:46px; width:16px; height:16px; border-radius:50%;
         background:var(--accent); box-shadow:0 0 14px var(--accent); animation:blink 5.5s infinite; }
  .eye.l { left:32px; } .eye.r { right:32px; }
  @keyframes blink { 0%,92%,100%{transform:scaleY(1);} 95%{transform:scaleY(.1);} }
  .mouth { position:absolute; bottom:34px; left:50%; transform:translateX(-50%);
           width:34px; height:8px; border-radius:0 0 20px 20px; background:var(--accent);
           box-shadow:0 0 12px var(--accent); animation:talk 2.6s ease-in-out infinite; }
  @keyframes talk { 0%,100%{height:5px;} 50%{height:12px;} }
  #avatar .cap { position:absolute; bottom:8px; width:100%; text-align:center; font-size:10px;
                 letter-spacing:.22em; color:var(--dim); z-index:3; }
  #avatar.asleep { filter:brightness(.55) saturate(.7); }
  #zzz { position:absolute; top:12px; right:16px; font-size:17px; font-weight:600; color:#7dd3fc;
         opacity:0; z-index:4; pointer-events:none; }
  #avatar.asleep #zzz { animation:zzz 3.6s ease-in-out infinite; }
  @keyframes zzz { 0%{opacity:0; transform:translateY(6px) scale(.8);} 45%{opacity:.95;}
                   100%{opacity:0; transform:translateY(-14px) scale(1.1);} }
  /* stats */
  #stats { display:grid; grid-template-columns:1fr 1fr; gap:10px; overflow:auto; }
  .stat { background:rgba(255,255,255,.03); border:1px solid var(--edge); border-radius:12px; padding:11px 12px; }
  .stat .n { font-size:22px; font-weight:600; line-height:1.1; }
  .stat .k { font-size:10px; letter-spacing:.14em; color:var(--dim); text-transform:uppercase; margin-top:3px; }
  .stat .n.g { color:var(--gold); }
  #tasks { margin-top:auto; }
  #tasks h3 { font-size:11px; letter-spacing:.2em; color:var(--dim); margin:4px 0 8px; }
  .task { display:flex; align-items:center; gap:9px; font-size:12px; padding:5px 0; color:#cdd2e0; }
  @property --p { syntax:'<number>'; inherits:false; initial-value:100; }
  .task .wheel { width:18px; height:18px; border-radius:50%; flex:0 0 auto; position:relative;
    background:conic-gradient(var(--gold) calc(var(--p)*1%), rgba(255,255,255,.07) 0);
    animation:countdown var(--dur,3s) linear infinite; box-shadow:0 0 8px rgba(255,215,120,.35); }
  .task .wheel::after { content:''; position:absolute; inset:3px; border-radius:50%; background:#0b0d16; }
  .task.pending .wheel { animation:none; box-shadow:none;
    background:conic-gradient(rgba(255,255,255,.14) 100%, transparent 0); }
  @keyframes countdown { from { --p:100; } to { --p:0; } }
  /* centre brain */
  #brainwrap { grid-row:1; grid-column:2; position:relative; overflow:hidden; }
  #brain { position:absolute; inset:0; }
  #think { position:absolute; top:16px; right:18px; text-align:right; font-size:12px; color:var(--dim); }
  #think b { color:var(--gold); }
  #moogles { position:absolute; left:0; right:0; bottom:12px; display:flex; justify-content:center;
             gap:26px; z-index:10; pointer-events:none; }
  .moogle { display:flex; flex-direction:column; align-items:center; gap:2px;
            animation:bob 2.3s ease-in-out infinite; font-size:9px; letter-spacing:.1em; color:#cfd3dc; }
  .moogle .kupo { color:#ff9ecf; animation:kupo 3.6s ease-in-out infinite; }
  @keyframes bob { 0%,100%{transform:translateY(0);} 50%{transform:translateY(-9px);} }
  @keyframes kupo { 0%,70%,100%{opacity:0;} 35%{opacity:1;} }
  #brainlabel { position:absolute; left:18px; top:16px; font-size:11px; letter-spacing:.26em; color:var(--dim); }
  /* bottom charts */
  #charts { grid-row:2; grid-column:1 / -1; display:grid; grid-template-columns:1.6fr 1fr 1fr 1.5fr 1.4fr; gap:14px; padding:14px; }
  .chartbox { position:relative; min-width:0; }
  .chartbox h4 { margin:0 0 9px; font-size:12.5px; letter-spacing:.12em; color:#b3b9c9; text-transform:uppercase; font-weight:600; }
  .chartbox canvas { width:100% !important; height:214px !important; }
</style></head>
<body>
<div id="app">
  <div id="left" class="panel">
    <div id="brandbar">
      <div id="sigil"></div>
      <div class="brand"><h1>BOND</h1><small>007 · COGNITION</small></div>
    </div>
    <div id="avatar">
      <div id="face"><div class="eye l"></div><div class="eye r"></div><div class="mouth"></div></div>
      <div id="zzz">z&nbsp;z&nbsp;z</div>
      <div class="cap">AVATAR · VRM SLOT</div>
    </div>
    <div id="stats"></div>
    <div id="tasks"><h3>ACTIVE THOUGHTS</h3><div id="tasklist"></div></div>
  </div>

  <div id="brainwrap" class="panel">
    <div id="brain"></div>
    <div id="brainlabel">THE BRAIN · LEFT LOGIC · RIGHT CREATIVE · CORE LIMBIC</div>
    <div id="think">waking&hellip;</div>
    <div id="moogles"></div>
  </div>

  <div id="reader" class="panel">
    <div id="reader-head">
      <div id="reader-title">THE READER</div>
      <div id="reader-sub">click a glowing node to open its note</div>
    </div>
    <div id="reader-body">Select any node in the brain to read that memory here — like opening a note in Obsidian. Bodies are scrubbed of secrets.</div>
  </div>

  <div id="ops" class="panel">
    <div id="clockbox"><div id="clock-time">--:--:--</div><div id="clock-date">&mdash;</div></div>
    <div id="mech">MECH &middot; <b id="mech-os">detecting&hellip;</b><br><span id="mech-hw"></span></div>
    <div><div class="ops-h">Host health</div><div id="health"></div></div>
    <div><div class="ops-h">Servers</div><div id="servers"></div></div>
    <div><div class="ops-h">Sites</div><div id="sites"></div></div>
    <div id="curiosity"><div class="ops-h">Curiosity</div><div id="curiosity-list"><div class="ok">warming up&hellip;</div></div></div>
  </div>

  <div id="charts" class="panel">
    <div class="chartbox"><h4>Activity — last 30 active days</h4><canvas id="cTrend"></canvas></div>
    <div class="chartbox"><h4>Output tokens by model</h4><canvas id="cModel"></canvas></div>
    <div class="chartbox"><h4>Memory by class</h4><canvas id="cClass"></canvas></div>
    <div class="chartbox"><h4>GPU · CPU · RAM — live</h4><canvas id="cOps"></canvas></div>
    <div class="chartbox"><h4>Crons &amp; backups</h4><div id="cronlist" style="height:214px;overflow:auto"></div></div>
  </div>
</div>

<script src="vendor/chart.umd.min.js"></script>
<script type="importmap">{ "imports": { "three": "./vendor/three.module.js" } }</script>
<script type="module">
import * as THREE from 'three';
import { OrbitControls } from './vendor/jsm/controls/OrbitControls.js';
import { GLTFLoader } from './vendor/jsm/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from './vendor/three-vrm.module.js';
const BOND = __DATA__;

/* ---------- stat cards ---------- */
const fmt = n => n>=1e6 ? (n/1e6).toFixed(1)+'M' : n>=1e3 ? (n/1e3).toFixed(1)+'k' : (n||0).toString();
const S = BOND.stats;
document.getElementById('stats').innerHTML = [
  ['daysActive','DAYS ACTIVE',false],['sessions','SESSIONS',false],
  ['messages','MESSAGES',false],['toolCalls','TOOL CALLS',false],
  ['tokensOut','TOKENS OUT',true],['brainNodes','BRAIN NODES',false],
].map(([k,label,g])=>`<div class="stat"><div class="n ${g?'g':''}">${fmt(S[k])}</div><div class="k">${label}</div></div>`).join('');
const tl = document.getElementById('tasklist');
const TOOL_VERB={Read:'reading',Edit:'editing',Write:'writing',MultiEdit:'editing',Bash:'running',PowerShell:'running',
  Grep:'searching',Glob:'finding',WebSearch:'searching the web',WebFetch:'fetching',Task:'delegating an agent',
  TaskUpdate:'tracking',TaskCreate:'planning',mcp:'using a tool'};
let thoughts=[];
function renderThoughts(){
  tl.innerHTML='';
  const list = thoughts.length ? thoughts : [{live:false, g:'resting — waiting for you'}];
  list.slice(0,6).forEach((th,i)=>{ const d=document.createElement('div');
    d.className='task'+(th.live?'':' pending');
    d.innerHTML='<span class="wheel" style="--dur:'+(2.0+i*0.6).toFixed(1)+'s"></span>'+th.g;
    tl.appendChild(d); });
}
function pushThought(a){
  const verb=TOOL_VERB[(a.tool||'').split('__')[0]] || (a.tool||'thinking');
  thoughts.unshift({live:true, g:(verb + (a.target ? ' · '+a.target : '')).slice(0,44)});
  thoughts = thoughts.slice(0,6); renderThoughts();
}
renderThoughts();

/* ---------- charts ---------- */
Chart.defaults.color = '#a2a8ba'; Chart.defaults.font.family = "'Segoe UI',system-ui,sans-serif"; Chart.defaults.font.size = 12.5;
const grid = { color:'rgba(140,150,190,.08)' };
new Chart(document.getElementById('cTrend'), {
  type:'line',
  data:{ labels: BOND.trend.map(d=>d.date.slice(5)),
    datasets:[
      { label:'messages', data:BOND.trend.map(d=>d.messages), borderColor:'#7dd3fc',
        backgroundColor:'rgba(125,211,252,.12)', fill:true, tension:.4, pointRadius:0, borderWidth:2 },
      { label:'tool calls', data:BOND.trend.map(d=>d.tools), borderColor:'#fbbf24',
        backgroundColor:'rgba(251,191,36,.08)', fill:true, tension:.4, pointRadius:0, borderWidth:2 },
    ]},
  options:{ responsive:false, maintainAspectRatio:false, plugins:{legend:{labels:{boxWidth:12,font:{size:12}}}},
    scales:{ x:{grid, ticks:{maxTicksLimit:7,font:{size:11}}}, y:{grid, ticks:{font:{size:11}}}}}
});
const doughnut = (id, labels, values, colors) => new Chart(document.getElementById(id), {
  type:'doughnut',
  data:{ labels, datasets:[{ data:values, backgroundColor:colors, borderColor:'#06070c', borderWidth:2 }]},
  options:{ responsive:false, maintainAspectRatio:false, cutout:'58%',
    plugins:{legend:{position:'bottom',labels:{boxWidth:11,padding:9,font:{size:11}}}}}
});
doughnut('cModel', BOND.modelTokens.map(m=>m.model), BOND.modelTokens.map(m=>m.out),
  ['#a78bfa','#7dd3fc','#f472b6','#fbbf24','#34d399','#60a5fa']);
doughnut('cClass', BOND.classDist.map(c=>c.klass.replace(/^\d+-/,'')), BOND.classDist.map(c=>c.count),
  BOND.classDist.map(c=>c.color));

/* ===== cockpit ops (bond-ops.json) + digital clock ===== */
const clockTime=document.getElementById('clock-time'), clockDate=document.getElementById('clock-date');
function tickClock(){ const d=new Date();
  clockTime.textContent=d.toLocaleTimeString([], {hour12:false});
  clockDate.textContent=d.toLocaleDateString([], {weekday:'long', day:'numeric', month:'short'}); }
setInterval(tickClock,1000); tickClock();

const mechOs=document.getElementById('mech-os'), mechHw=document.getElementById('mech-hw');
const healthEl=document.getElementById('health'), serversEl=document.getElementById('servers'),
      sitesEl=document.getElementById('sites'), curiosityEl=document.getElementById('curiosity-list'),
      cronEl=document.getElementById('cronlist');
function bar(label,val,pct,warn,crit){ let cls=''; if(crit&&pct>=crit)cls='crit'; else if(warn&&pct>=warn)cls='warn';
  return '<div class="metric"><div class="lab"><span>'+label+'</span><b>'+val+'</b></div><div class="bar '+cls+'"><span style="width:'+Math.max(2,Math.min(100,pct))+'%"></span></div></div>'; }
let cOps=null;
function renderOps(o){
  if(o.mech){ mechOs.textContent=o.mech.os||'?'; mechHw.textContent=((o.mech.gpu||'').replace('NVIDIA GeForce ','')||o.mech.cpu||''); }
  const L=o.laptop||{}; let h='';
  if(L.cpu!=null) h+=bar('CPU', L.cpu+'%', L.cpu, 70, 90);
  if(L.ram&&L.ram.totalMB) h+=bar('RAM', (L.ram.usedMB/1024).toFixed(1)+' / '+(L.ram.totalMB/1024).toFixed(0)+'G', 100*L.ram.usedMB/L.ram.totalMB, 75, 92);
  if(L.gpu&&L.gpu.ok){ h+=bar('GPU', L.gpu.util+'%', L.gpu.util, 70, 88);
    h+=bar('GPU '+Math.round(L.gpu.watts)+'W · '+Math.round(L.gpu.temp)+'°C', (L.gpu.memUsed/1024).toFixed(1)+' / '+(L.gpu.memTotal/1024).toFixed(0)+'G VRAM', 100*L.gpu.memUsed/L.gpu.memTotal, 80, 95); }
  if(L.battery&&L.battery.pct!=null) h+=bar('Battery'+(L.battery.charging?' ⚡':''), L.battery.pct+'%', L.battery.pct, 0, 0);
  healthEl.innerHTML=h||'<div class="ok">n/a</div>';
  serversEl.innerHTML=(o.servers||[]).map(s=>'<div class="srv"><span class="dot '+(s.up?'up':'down')+'"></span>'+s.name+
    '<span class="meta">'+(s.up?(s.days+'d · '+(s.ram&&s.ram.totalMB?Math.round(100*s.ram.usedMB/s.ram.totalMB)+'% ram':'')+' · load '+(s.load!=null?s.load:'?')):'down')+'</span></div>').join('')||'<div class="ok">n/a</div>';
  sitesEl.innerHTML=(o.sites||[]).map(s=>'<div class="site"><span class="dot '+(s.up?'up':'down')+'"></span>'+s.name+
    '<span class="meta">'+(s.up?s.ms+'ms':'HTTP '+s.code)+'</span></div>').join('')||'<div class="ok">n/a</div>';
  const cur=o.curiosity||[];
  curiosityEl.innerHTML=cur.length?cur.map(c=>'<div class="c">⚠ '+c+'</div>').join(''):'<div class="ok">all quiet — nothing unusual</div>';
  cronEl.innerHTML=(o.crons||[]).map(c=>'<div class="srv"><span class="dot '+(c.stale?'down':'up')+'"></span>'+String(c.name).slice(0,26)+
    '<span class="meta">'+(c.last==='never'?'never':c.ageDays+'d')+'</span></div>').join('')||'<div class="ok">no tasks</div>';
  if(o.history&&o.history.length){
    const labels=o.history.map(p=>p.t), g=o.history.map(p=>p.gpu), c=o.history.map(p=>p.cpu), r=o.history.map(p=>p.ram);
    if(!cOps){ cOps=new Chart(document.getElementById('cOps'),{ type:'line',
      data:{labels, datasets:[
        {label:'GPU%',data:g,borderColor:'#34d399',backgroundColor:'rgba(52,211,153,.12)',fill:true,tension:.35,pointRadius:0,borderWidth:2},
        {label:'CPU%',data:c,borderColor:'#7dd3fc',fill:false,tension:.35,pointRadius:0,borderWidth:2},
        {label:'RAM%',data:r,borderColor:'#fbbf24',fill:false,tension:.35,pointRadius:0,borderWidth:2}]},
      options:{responsive:false,maintainAspectRatio:false,animation:false,
        plugins:{legend:{labels:{boxWidth:12,font:{size:11}}}},
        scales:{x:{grid,ticks:{maxTicksLimit:6,font:{size:10}}},y:{grid,min:0,max:100,ticks:{font:{size:10}}}}}}); }
    else { cOps.data.labels=labels; cOps.data.datasets[0].data=g; cOps.data.datasets[1].data=c; cOps.data.datasets[2].data=r; cOps.update('none'); }
  }
}
async function pollOps(){ try{ const r=await fetch('bond-ops.json?t='+Date.now(),{cache:'no-store'}); if(r.ok) renderOps(await r.json()); }catch(e){} }
setInterval(pollOps, 5000); pollOps();

/* ---------- the colourful neural brain ---------- */
const host = document.getElementById('brain');
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(58, 1, 0.1, 5000);
camera.position.set(0, 26, 520);
const renderer = new THREE.WebGLRenderer({ antialias:true, alpha:true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
host.appendChild(renderer.domElement);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true; controls.dampingFactor = .06;
controls.autoRotate = true; controls.autoRotateSpeed = .55; controls.enablePan = false;

function resize(){ const w=host.clientWidth,h=host.clientHeight;
  renderer.setSize(w,h); camera.aspect=w/h; camera.updateProjectionMatrix(); }
new ResizeObserver(resize).observe(host); resize();

// soft round sprite for glow
function disc(){ const c=document.createElement('canvas'); c.width=c.height=64;
  const g=c.getContext('2d').createRadialGradient(32,32,0,32,32,32);
  g.addColorStop(0,'rgba(255,255,255,1)'); g.addColorStop(.25,'rgba(255,255,255,.85)');
  g.addColorStop(1,'rgba(255,255,255,0)'); const x=c.getContext('2d');
  x.fillStyle=g; x.fillRect(0,0,64,64); return new THREE.CanvasTexture(c); }
const SPRITE = disc();

// place nodes: two lobes (±x) + a central core
const anchor = { left:[-205,0,0], right:[205,0,0], core:[0,0,0] };
const nodes = BOND.nodes;
nodes.forEach(n=>{
  const a = anchor[n.region] || anchor.core;
  const lobe = n.region==='core' ? 96 : 140;
  const u=Math.random(), v=Math.random(), th=Math.acos(2*u-1), ph=2*Math.PI*v;
  // bias toward the shell so lobes read as volumes, not dense centres
  const r = lobe * (0.45 + 0.55*Math.cbrt(Math.random()));
  n.x=a[0]+r*Math.sin(th)*Math.cos(ph);
  n.y=a[1]+r*Math.sin(th)*Math.sin(ph)*0.82;
  n.z=a[2]+r*Math.cos(th)*0.82;
});

// node points (additive glow, coloured by class)
const npos=new Float32Array(nodes.length*3), ncol=new Float32Array(nodes.length*3);
const col=new THREE.Color();
nodes.forEach((n,i)=>{ npos[i*3]=n.x; npos[i*3+1]=n.y; npos[i*3+2]=n.z;
  col.set(n.color); ncol[i*3]=col.r; ncol[i*3+1]=col.g; ncol[i*3+2]=col.b; });
const ng=new THREE.BufferGeometry();
ng.setAttribute('position', new THREE.BufferAttribute(npos,3));
ng.setAttribute('color', new THREE.BufferAttribute(ncol,3));
const nodePoints = new THREE.Points(ng, new THREE.PointsMaterial({ size:4.4, map:SPRITE,
  vertexColors:true, transparent:true, opacity:.92, depthWrite:false, blending:THREE.AdditiveBlending,
  sizeAttenuation:true }));
scene.add(nodePoints);

// dense synapse web = k nearest neighbours (visual), plus real wikilinks
function synapses(k){
  const seg=[], seen=new Set();
  for(let i=0;i<nodes.length;i++){ const a=nodes[i], d=[];
    for(let j=0;j<nodes.length;j++){ if(i===j)continue; const b=nodes[j];
      const dx=a.x-b.x,dy=a.y-b.y,dz=a.z-b.z; d.push([dx*dx+dy*dy+dz*dz,j]); }
    d.sort((p,q)=>p[0]-q[0]);
    for(let m=0;m<k;m++){ const j=d[m][1], key=i<j?i+'_'+j:j+'_'+i;
      if(seen.has(key))continue; seen.add(key); seg.push([i,j]); } }
  return seg;
}
const edges = synapses(3);
const idOf = {}; nodes.forEach((n,i)=>idOf[n.id]=i);
BOND.links.forEach(l=>{ const s=idOf[l.source], t=idOf[l.target];
  if(s!=null&&t!=null){ const key=s<t?s+'_'+t:t+'_'+s; edges.push([s,t]); } });

const lpos=new Float32Array(edges.length*6), lcol=new Float32Array(edges.length*6);
edges.forEach((e,i)=>{ const a=nodes[e[0]], b=nodes[e[1]];
  lpos.set([a.x,a.y,a.z,b.x,b.y,b.z], i*6);
  const ca=new THREE.Color(a.color), cb=new THREE.Color(b.color);
  lcol.set([ca.r,ca.g,ca.b,cb.r,cb.g,cb.b], i*6); });
const lg=new THREE.BufferGeometry();
lg.setAttribute('position', new THREE.BufferAttribute(lpos,3));
lg.setAttribute('color', new THREE.BufferAttribute(lcol,3));
scene.add(new THREE.LineSegments(lg, new THREE.LineBasicMaterial({ vertexColors:true,
  transparent:true, opacity:.17, blending:THREE.AdditiveBlending, depthWrite:false })));

// edges incident to each node — so a thought can fire along what it touched
const edgesByNode = Array.from({length:nodes.length}, ()=>[]);
edges.forEach((e,i)=>{ edgesByNode[e[0]].push(i); edgesByNode[e[1]].push(i); });

// active thought: the nodes the current tool call lit up
let activeSet = [], activeGlow = 0;

// highlight overlay — gold halos on the lit nodes
const HL = 24; const hpos=new Float32Array(HL*3);
const hg=new THREE.BufferGeometry();
hg.setAttribute('position', new THREE.BufferAttribute(hpos,3)); hg.setDrawRange(0,0);
const hmat=new THREE.PointsMaterial({ size:20, map:SPRITE, color:0xffe08a, transparent:true,
  opacity:0, depthWrite:false, blending:THREE.AdditiveBlending, sizeAttenuation:true });
scene.add(new THREE.Points(hg, hmat));
function rebuildHighlight(){ const n=Math.min(activeSet.length, HL);
  for(let i=0;i<n;i++){ const nd=nodes[activeSet[i]]; hpos[i*3]=nd.x; hpos[i*3+1]=nd.y; hpos[i*3+2]=nd.z; }
  hg.setDrawRange(0,n); hg.attributes.position.needsUpdate=true; }

// pulse-packets firing along edges (always alive = a healthy brain)
const NP=300, pulses=[];
const ppos=new Float32Array(NP*3), pcol=new Float32Array(NP*3);
function seed(p, biased){
  let e;
  if(biased && activeSet.length && Math.random()<0.75){
    const src = activeSet[(Math.random()*activeSet.length)|0];
    const inc = edgesByNode[src];
    e = inc.length ? edges[inc[(Math.random()*inc.length)|0]] : edges[(Math.random()*edges.length)|0];
  } else { e = edges[(Math.random()*edges.length)|0]; }
  p.a=e[0]; p.b=e[1]; p.t=Math.random(); p.sp=0.004+Math.random()*0.010;
  const c=new THREE.Color(nodes[e[0]].color); p.r=c.r; p.g=c.g; p.bb=c.b;
}
for(let i=0;i<NP;i++){ const p={}; seed(p,false); pulses.push(p); }
const pg=new THREE.BufferGeometry();
pg.setAttribute('position', new THREE.BufferAttribute(ppos,3));
pg.setAttribute('color', new THREE.BufferAttribute(pcol,3));
scene.add(new THREE.Points(pg, new THREE.PointsMaterial({ size:9, map:SPRITE, vertexColors:true,
  transparent:true, depthWrite:false, blending:THREE.AdditiveBlending, sizeAttenuation:true })));

const thinkEl=document.getElementById('think'); thinkEl.innerHTML='resting &mdash; brain healthy';
let mood=0; // 0 rest .. 1 firing
let asleep=true, lastActive=0;   // Bond naps until a clap or real activity wakes him

// find memory nodes whose label matches what the tool touched, and light them
function lightMatch(text){
  const toks=(text||'').toLowerCase().replace(/[^a-z0-9]+/g,' ').split(' ').filter(w=>w.length>3);
  const hits=[];
  for(let i=0;i<nodes.length && hits.length<HL;i++){
    const lab=nodes[i].label.toLowerCase();
    if(toks.some(w=>lab.includes(w))) hits.push(i);
  }
  if(!hits.length){ for(let k=0;k<4;k++) hits.push((Math.random()*nodes.length)|0); }
  activeSet=hits; activeGlow=1; rebuildHighlight();
}

// LIVE: poll the activity file the PostToolUse hook writes → fire on real tool calls
let lastSeq=-1, restT=null;
const TOOL_ICON={Read:'👁',Edit:'✎',Write:'✎',Bash:'⌘',PowerShell:'⌘',Grep:'⌕',Glob:'⌕',
  WebSearch:'🌐',WebFetch:'🌐',Task:'⚙',TaskUpdate:'⚙',mcp:'◇'};
async function pollActivity(){
  try{
    const r=await fetch('bond-activity.json?t='+Date.now(),{cache:'no-store'});
    if(!r.ok) return; const a=await r.json();
    if(a.seq!=null && a.seq!==lastSeq){
      lastSeq=a.seq; mood=1;
      const ic=TOOL_ICON[(a.tool||'').split('__')[0]]||'⚡';
      thinkEl.innerHTML=`<b>${ic} ${a.tool||'thinking'}</b>`+(a.target?`<br>${a.target}`:'');
      lightMatch(a.target||a.tool);
      avatarSpeak(a); wake(); pushThought(a);
      clearTimeout(restT);
      restT=setTimeout(()=>{ mood=0; thinkEl.innerHTML='resting &mdash; brain healthy'; }, 2600);
    } else if(a.state==='listening' && a.seq===lastSeq){
      thinkEl.innerHTML='<b>listening&hellip;</b>'; avatarListen();
    }
    renderMoogles(a.agents||[]);
  }catch(e){}
}
const moogleHost=document.getElementById('moogles');
const MOOGLE_SVG=`<svg width="44" height="46" viewBox="0 0 44 46" xmlns="http://www.w3.org/2000/svg">
<path d="M12 25 Q2 21 6 31 Q10 31 15 28 Z" fill="#b8a6e6" opacity=".9"/>
<path d="M32 25 Q42 21 38 31 Q34 31 29 28 Z" fill="#b8a6e6" opacity=".9"/>
<ellipse cx="22" cy="30" rx="10" ry="9" fill="#fdfdff"/>
<circle cx="22" cy="17" r="10" fill="#fdfdff"/>
<path d="M14 10 L12 4 L18 9 Z" fill="#fdfdff"/><path d="M30 10 L32 4 L26 9 Z" fill="#fdfdff"/>
<line x1="22" y1="8" x2="22" y2="3" stroke="#e6e6ee" stroke-width="1.4"/>
<circle cx="22" cy="2.6" r="3.4" fill="#ff5a7a"/>
<circle cx="18" cy="17" r="1.5" fill="#33343c"/><circle cx="26" cy="17" r="1.5" fill="#33343c"/>
<circle cx="15" cy="20" r="1.7" fill="#ffc0d3" opacity=".85"/><circle cx="29" cy="20" r="1.7" fill="#ffc0d3" opacity=".85"/>
</svg>`;
let mooShown='';
function renderMoogles(labels){
  const key=labels.join('|'); if(key===mooShown) return; mooShown=key;
  moogleHost.innerHTML='';
  labels.forEach((lab,i)=>{ const d=document.createElement('div'); d.className='moogle';
    d.style.animationDelay=(i*0.35)+'s';
    d.innerHTML=`<div class="kupo">kupo!</div>${MOOGLE_SVG}<div>${lab||'agent'}</div>`;
    moogleHost.appendChild(d); });
}
/* node picking — click a node to open its (scrubbed) note, Obsidian-style */
const raycaster=new THREE.Raycaster(); raycaster.params.Points.threshold=6;
const ptr=new THREE.Vector2(); let downXY=null, downT=0;
const rdT=document.getElementById('reader-title'), rdS=document.getElementById('reader-sub'), rdB=document.getElementById('reader-body');
function mdLite(t){ return t
  .replace(/^---[\s\S]*?---\s*/,'')
  .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
  .replace(/`([^`]+)`/g,'<code>$1</code>')
  .replace(/\*\*([^*]+)\*\*/g,'<b>$1</b>')
  .replace(/\[\[([^\]|#]+)[^\]]*\]\]/g,'<span class="wl">$1</span>')
  .replace(/^#{1,6}\s*(.+)$/gm,'<h4>$1</h4>').trim(); }
async function openNote(idx){ const n=nodes[idx]; if(!n) return;
  activeSet=[idx]; activeGlow=1; rebuildHighlight();
  rdT.textContent=n.label; rdS.innerHTML='<span class="chip" style="border-color:'+n.color+';color:'+n.color+'">'+n.klass+'</span>';
  rdB.innerHTML='loading&hellip;';
  try{ const r=await fetch('notes/'+n.slug+'.md?t='+Date.now(),{cache:'no-store'});
    rdB.innerHTML = r.ok ? mdLite(await r.text()) : (n.summary||'(no note body)'); }
  catch(e){ rdB.textContent = n.summary||'(unavailable)'; } }
renderer.domElement.addEventListener('pointerdown', e=>{ downXY=[e.clientX,e.clientY]; downT=performance.now(); });
renderer.domElement.addEventListener('pointerup', e=>{ if(!downXY) return;
  const moved=Math.hypot(e.clientX-downXY[0], e.clientY-downXY[1]), dt=performance.now()-downT; downXY=null;
  if(moved>6 || dt>350) return;
  const rect=renderer.domElement.getBoundingClientRect();
  ptr.x=((e.clientX-rect.left)/rect.width)*2-1; ptr.y=-((e.clientY-rect.top)/rect.height)*2+1;
  raycaster.setFromCamera(ptr, camera);
  const hits=raycaster.intersectObject(nodePoints);
  if(hits.length) openNote(hits[0].index);
});
setInterval(pollActivity, 600); pollActivity();

// gentle ambient thought so the brain dreams even when no tools run (never dark)
setInterval(()=>{ if(mood===0 && Math.random()<0.5) lightMatch(nodes[(Math.random()*nodes.length)|0].label); }, 6500);

function animate(){
  requestAnimationFrame(animate);
  const fire = (mood + activeGlow*0.4) * (asleep?0.32:1);   // dim while napping, full when awake
  for(let i=0;i<NP;i++){ const p=pulses[i]; p.t += p.sp*(1 + fire*1.6);
    if(p.t>=1){ seed(p, activeGlow>0.15); }
    const a=nodes[p.a], b=nodes[p.b], t=p.t;
    ppos[i*3]=a.x+(b.x-a.x)*t; ppos[i*3+1]=a.y+(b.y-a.y)*t; ppos[i*3+2]=a.z+(b.z-a.z)*t;
    const k=0.72+fire*0.28;
    pcol[i*3]=p.r*k+fire*0.28; pcol[i*3+1]=p.g*k+fire*0.2; pcol[i*3+2]=p.bb*k+fire*0.1;
  }
  pg.attributes.position.needsUpdate=true; pg.attributes.color.needsUpdate=true;
  if(activeGlow>0){ activeGlow=Math.max(0, activeGlow-0.006); hmat.opacity=activeGlow*0.9; }
  controls.update(); renderer.render(scene,camera);
}
animate();

/* ===== VRM avatar — the face, reacting to the same activity stream ===== */
const aHost=document.getElementById('avatar');
const aFace=document.getElementById('face'); if(aFace) aFace.style.display='none';
const aCap=aHost.querySelector('.cap'); if(aCap){ aCap.textContent='BOND · loading…'; aCap.style.zIndex='2'; }
const aScene=new THREE.Scene();
const aCam=new THREE.PerspectiveCamera(22, 1, 0.08, 20);
aCam.position.set(0, 1.38, 0.82); aCam.lookAt(0, 1.36, 0);
const aRenderer=new THREE.WebGLRenderer({antialias:true, alpha:true});
aRenderer.setPixelRatio(Math.min(devicePixelRatio,2));
aRenderer.outputColorSpace = THREE.SRGBColorSpace;
aRenderer.domElement.style.cssText='position:absolute;inset:0;width:100%;height:100%;z-index:0';
aHost.appendChild(aRenderer.domElement);
const aKey=new THREE.DirectionalLight(0xffffff,2.4); aKey.position.set(0.5,1.6,1.4); aScene.add(aKey);
aScene.add(new THREE.AmbientLight(0x99aaff,1.7));
function aResize(){ const w=aHost.clientWidth,h=aHost.clientHeight; if(!w||!h)return;
  aRenderer.setSize(w,h); aCam.aspect=w/h; aCam.updateProjectionMatrix(); }
new ResizeObserver(aResize).observe(aHost); aResize();

let vrm=null; const aClock=new THREE.Clock();
let talk=0, gesture=null, gT=0, happy=0, blinkT=2+Math.random()*3;
let sCtx=null, sAudio=null, sAnalyser=null, sData=null, lastSpeech=-1, speaking=false, mouthAmp=0;
const vLoader=new GLTFLoader(); vLoader.register(p=>new VRMLoaderPlugin(p));
vLoader.load('vendor/avatar-alt.vrm', (gltf)=>{
  vrm=gltf.userData.vrm;
  try{ if(vrm.meta && vrm.meta.metaVersion==='0') VRMUtils.rotateVRM0(vrm); }catch(e){}
  aScene.add(vrm.scene);
  if(aCap) aCap.textContent='BOND · online';
}, undefined, (e)=>{ if(aCap) aCap.textContent='avatar load failed'; console.log('vrm error', e); });

function setX(name,v){ if(vrm){ try{ vrm.expressionManager.setValue(name, v); }catch(e){} } }
function avatarSpeak(a){ gesture='nod'; gT=0.8; happy=Math.min(1, happy+0.5); }  // nod+smile only; the MOUTH moves solely to real speech audio
function avatarListen(){ talk=0; }
function avatarNo(){ gesture='shake'; gT=0.9; }   // reserved: "no"

function avatarAnimate(){
  requestAnimationFrame(avatarAnimate);
  const dt=Math.min(aClock.getDelta(), 0.05);
  if(vrm){
    const t=performance.now()/1000;
    const head=vrm.humanoid.getNormalizedBoneNode('head');
    const spine=vrm.humanoid.getNormalizedBoneNode('spine');
    if(asleep){   // napping peacefully: chin down, eyes closed, slow breathing
      if(head) head.rotation.set(0.36, 0.12, Math.sin(t*0.5)*0.02);
      if(spine) spine.rotation.x=0.09+Math.sin(t*0.4)*0.015;
      setX('blink',1); setX('aa',0); setX('happy',0); setX('relaxed',0.45);
      vrm.update(dt); aRenderer.render(aScene, aCam); return;
    }
    if(spine) spine.rotation.y=Math.sin(t*0.6)*0.03;
    if(head){ head.rotation.set(0,0,Math.sin(t*0.9)*0.02);
      if(gesture && gT>0){ gT-=dt; const s=Math.sin((0.8-gT)/0.8*Math.PI*2)*Math.max(0,gT);
        if(gesture==='nod') head.rotation.x=s*0.6; else head.rotation.y=s*0.7;
        if(gT<=0) gesture=null; } }
    blinkT-=dt; let blink=0;
    if(blinkT<0.14) blink=1-Math.min(1,Math.abs(blinkT)/0.14);
    if(blinkT<0) blinkT=2.4+Math.random()*3.4;
    setX('blink', Math.max(0,blink));
    // lipsync: ONLY to Bond's real speech audio (RMS of the playing waveform)
    if(speaking && sAnalyser){ sAnalyser.getByteTimeDomainData(sData); let s=0;
      for(let i=0;i<sData.length;i++){ const v=(sData[i]-128)/128; s+=v*v; }
      const amp=Math.min(1, Math.sqrt(s/sData.length)*5.2);
      mouthAmp += (amp - mouthAmp)*0.55; happy=Math.max(happy,0.2); }
    else { mouthAmp += (0 - mouthAmp)*0.4; }
    setX('aa', mouthAmp*0.92); setX('ih', mouthAmp*0.22);
    happy=Math.max(0, happy-dt*0.14); setX('happy', happy*0.7); setX('relaxed', 0.15);
    vrm.update(dt);
  }
  aRenderer.render(aScene, aCam);
}

/* Bond talks back — play the edge-tts reply + lipsync from real audio amplitude */
function playSpeech(){ try{
  if(!sCtx) sCtx=new (window.AudioContext||window.webkitAudioContext)();
  sAudio=new Audio('bond-speech.mp3?t='+Date.now());
  const src=sCtx.createMediaElementSource(sAudio);
  sAnalyser=sCtx.createAnalyser(); sAnalyser.fftSize=256; sData=new Uint8Array(sAnalyser.fftSize);
  src.connect(sAnalyser); sAnalyser.connect(sCtx.destination);
  speaking=true; if(aCap) aCap.textContent='BOND · speaking';
  sAudio.onended=()=>{ speaking=false; if(aCap) aCap.textContent='BOND · online'; };
  sCtx.resume(); sAudio.play().catch(()=>{ speaking=false; console.log('autoplay blocked — clap to enable voice'); });
}catch(e){ console.log('speech err', e); } }
async function pollSpeech(){ try{
  const r=await fetch('bond-speech.json?t='+Date.now(),{cache:'no-store'}); if(!r.ok) return;
  const s=await r.json(); if(s.id && s.id!==lastSpeech){ lastSpeech=s.id; playSpeech(); }
}catch(e){} }
setInterval(pollSpeech, 900);

/* double-clap wake — no push-to-talk. Two claps within 650ms wakes Bond. */
let wakeArmed=true, lastClap=0;
async function initWake(){ try{
  const stream=await navigator.mediaDevices.getUserMedia({audio:true});
  const wctx=new (window.AudioContext||window.webkitAudioContext)();
  const src=wctx.createMediaStreamSource(stream); const an=wctx.createAnalyser(); an.fftSize=512;
  src.connect(an); const buf=new Uint8Array(an.fftSize);
  (function tick(){ requestAnimationFrame(tick); an.getByteTimeDomainData(buf);
    let peak=0; for(let i=0;i<buf.length;i++){ const v=Math.abs(buf[i]-128); if(v>peak) peak=v; }
    if(peak>74 && wakeArmed && !speaking){ wakeArmed=false; setTimeout(()=>wakeArmed=true,150);  // ignore Bond's own voice (half-duplex)
      const now=performance.now(); if(now-lastClap<650) wake(); lastClap=now; }
  })();
}catch(e){ if(aCap) aCap.textContent='BOND · allow mic to clap-wake'; } }
function wake(){ lastActive=performance.now(); if(!asleep) return;
  asleep=false; aHost.classList.remove('asleep'); happy=0.95; gesture='nod'; gT=0.85;
  if(aCap) aCap.textContent='BOND · awake'; thinkEl.innerHTML='<b>awake</b>';
  try{ if(sCtx) sCtx.resume(); }catch(e){} }
function nap(){ if(asleep) return; asleep=true; aHost.classList.add('asleep');
  if(aCap) aCap.textContent='BOND · asleep'; thinkEl.innerHTML='&#128564; asleep &mdash; double-clap to wake'; }
setInterval(()=>{ if(!asleep && !speaking && performance.now()-lastActive>45000) nap(); }, 4000);
// start asleep — napping peacefully until a clap or activity
aHost.classList.add('asleep'); if(aCap) aCap.textContent='BOND · asleep';
thinkEl.innerHTML='&#128564; asleep &mdash; double-clap to wake';
initWake();

avatarAnimate();
</script>
</body></html>
"""
