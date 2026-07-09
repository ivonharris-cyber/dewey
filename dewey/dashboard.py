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
from collections import Counter
from pathlib import Path

from . import brain3d

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
         grid-template-columns:340px 1fr; grid-template-rows:1fr 236px; gap:14px; padding:14px; }
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
                 letter-spacing:.22em; color:var(--dim); }
  /* stats */
  #stats { display:grid; grid-template-columns:1fr 1fr; gap:10px; overflow:auto; }
  .stat { background:rgba(255,255,255,.03); border:1px solid var(--edge); border-radius:12px; padding:11px 12px; }
  .stat .n { font-size:22px; font-weight:600; line-height:1.1; }
  .stat .k { font-size:10px; letter-spacing:.14em; color:var(--dim); text-transform:uppercase; margin-top:3px; }
  .stat .n.g { color:var(--gold); }
  #tasks { margin-top:auto; }
  #tasks h3 { font-size:11px; letter-spacing:.2em; color:var(--dim); margin:4px 0 8px; }
  .task { display:flex; align-items:center; gap:8px; font-size:12px; padding:4px 0; color:#cdd2e0; }
  .task i { width:8px; height:8px; border-radius:50%; background:var(--gold); box-shadow:0 0 8px var(--gold); flex:0 0 auto; }
  /* centre brain */
  #brainwrap { grid-row:1; grid-column:2; position:relative; overflow:hidden; }
  #brain { position:absolute; inset:0; }
  #think { position:absolute; top:16px; right:18px; text-align:right; font-size:12px; color:var(--dim); }
  #think b { color:var(--gold); }
  #brainlabel { position:absolute; left:18px; top:16px; font-size:11px; letter-spacing:.26em; color:var(--dim); }
  /* bottom charts */
  #charts { grid-row:2; grid-column:1 / -1; display:grid; grid-template-columns:2fr 1fr 1fr; gap:14px; padding:14px; }
  .chartbox { position:relative; min-width:0; }
  .chartbox h4 { margin:0 0 6px; font-size:10px; letter-spacing:.2em; color:var(--dim); text-transform:uppercase; }
  .chartbox canvas { width:100% !important; height:170px !important; }
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
      <div class="cap">AVATAR · VRM SLOT</div>
    </div>
    <div id="stats"></div>
    <div id="tasks"><h3>ACTIVE THOUGHTS</h3><div id="tasklist"></div></div>
  </div>

  <div id="brainwrap" class="panel">
    <div id="brain"></div>
    <div id="brainlabel">THE BRAIN · LEFT LOGIC · RIGHT CREATIVE · CORE LIMBIC</div>
    <div id="think">waking&hellip;</div>
  </div>

  <div id="charts" class="panel">
    <div class="chartbox"><h4>Activity — last 30 active days</h4><canvas id="cTrend"></canvas></div>
    <div class="chartbox"><h4>Output tokens by model</h4><canvas id="cModel"></canvas></div>
    <div class="chartbox"><h4>Memory by class</h4><canvas id="cClass"></canvas></div>
  </div>
</div>

<script src="vendor/three.min.js"></script>
<script src="vendor/OrbitControls.js"></script>
<script src="vendor/chart.umd.min.js"></script>
<script>
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
(BOND.tasks.length ? BOND.tasks : [{title:'idle — dreaming'}]).slice(0,6).forEach(t=>{
  const d=document.createElement('div'); d.className='task';
  d.innerHTML=`<i></i>${(t.title||t.subject||'task').slice(0,42)}`; tl.appendChild(d);
});

/* ---------- charts ---------- */
Chart.defaults.color = '#8b90a4'; Chart.defaults.font.family = "'Segoe UI',system-ui,sans-serif";
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
  options:{ responsive:false, plugins:{legend:{labels:{boxWidth:10,font:{size:9}}}},
    scales:{ x:{grid, ticks:{maxTicksLimit:8,font:{size:8}}}, y:{grid, ticks:{font:{size:8}}}}}
});
const doughnut = (id, labels, values, colors) => new Chart(document.getElementById(id), {
  type:'doughnut',
  data:{ labels, datasets:[{ data:values, backgroundColor:colors, borderColor:'#06070c', borderWidth:2 }]},
  options:{ responsive:false, cutout:'60%',
    plugins:{legend:{position:'bottom',labels:{boxWidth:8,padding:7,font:{size:9}}}}}
});
doughnut('cModel', BOND.modelTokens.map(m=>m.model), BOND.modelTokens.map(m=>m.out),
  ['#a78bfa','#7dd3fc','#f472b6','#fbbf24','#34d399','#60a5fa']);
doughnut('cClass', BOND.classDist.map(c=>c.klass.replace(/^\d+-/,'')), BOND.classDist.map(c=>c.count),
  BOND.classDist.map(c=>c.color));

/* ---------- the colourful neural brain ---------- */
const host = document.getElementById('brain');
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(58, 1, 0.1, 5000);
camera.position.set(0, 26, 520);
const renderer = new THREE.WebGLRenderer({ antialias:true, alpha:true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
host.appendChild(renderer.domElement);
const controls = new THREE.OrbitControls(camera, renderer.domElement);
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
  x.fillStyle=g; x.fillRect(0,0,64,64); const t=new THREE.Texture(c); t.needsUpdate=true; return t; }
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
scene.add(new THREE.Points(ng, new THREE.PointsMaterial({ size:4.4, map:SPRITE,
  vertexColors:true, transparent:true, opacity:.92, depthWrite:false, blending:THREE.AdditiveBlending,
  sizeAttenuation:true })));

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

// pulse-packets firing along edges
const NP=280, pulses=[];
const ppos=new Float32Array(NP*3), pcol=new Float32Array(NP*3);
function seed(p){ const e=edges[(Math.random()*edges.length)|0]; p.a=e[0]; p.b=e[1];
  p.t=Math.random(); p.sp=0.004+Math.random()*0.010; const c=new THREE.Color(nodes[e[0]].color);
  p.r=c.r; p.g=c.g; p.bb=c.b; }
for(let i=0;i<NP;i++){ const p={}; seed(p); pulses.push(p); }
const pg=new THREE.BufferGeometry();
pg.setAttribute('position', new THREE.BufferAttribute(ppos,3));
pg.setAttribute('color', new THREE.BufferAttribute(pcol,3));
scene.add(new THREE.Points(pg, new THREE.PointsMaterial({ size:9, map:SPRITE, vertexColors:true,
  transparent:true, depthWrite:false, blending:THREE.AdditiveBlending, sizeAttenuation:true })));

const thinkEl=document.getElementById('think'); thinkEl.innerHTML='resting &mdash; runners idle';
let mood=0; // 0 rest .. 1 firing
function fireThought(){ mood=1; thinkEl.innerHTML='<b>hatching an idea&hellip;</b><br>synapses firing';
  setTimeout(()=>{ mood=0; thinkEl.innerHTML='resting &mdash; the brain idles'; }, 4200); }
setInterval(fireThought, 8000); setTimeout(fireThought, 2500);

function animate(){
  requestAnimationFrame(animate);
  for(let i=0;i<NP;i++){ const p=pulses[i]; p.t+=p.sp*(mood?2.4:1);
    if(p.t>=1){ seed(p); }
    const a=nodes[p.a], b=nodes[p.b], t=p.t;
    ppos[i*3]=a.x+(b.x-a.x)*t; ppos[i*3+1]=a.y+(b.y-a.y)*t; ppos[i*3+2]=a.z+(b.z-a.z)*t;
    const k=mood?1:0.7; pcol[i*3]=p.r*k+ (mood?0.3:0); pcol[i*3+1]=p.g*k+(mood?0.2:0); pcol[i*3+2]=p.bb*k+(mood?0.1:0);
  }
  pg.attributes.position.needsUpdate=true; pg.attributes.color.needsUpdate=true;
  controls.update(); renderer.render(scene,camera);
}
animate();
</script>
</body></html>
"""
