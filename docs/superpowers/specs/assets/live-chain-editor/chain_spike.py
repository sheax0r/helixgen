#!/usr/bin/env python3
"""THROWAWAY spike: live signal-chain knob editor for the Helix Stadium.

Reads the device's live edit buffer, renders every block in every path as
knobs/switches/toggles, and writes each tweak straight to the device
(/ParamValueSet, force=True) so you can twist-and-hear. Bypass toggles too.

Not shippable: no SSE live-tracking, splits shown as inline markers (not
2-col lanes), per-block param reads at load. Point: does live writing feel
instant on real hardware, and do the writes land right.

Run:  PYTHONPATH=<core>/src python3 chain_spike.py
"""
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from helixgen.device import discovery, HelixClient, defs
from helixgen.device.client import _grid_slot

# a live write only needs its ack — skip the 0.4s settle-drain that _rpc does
# by default (measured: 614ms -> 10ms per write on the XL).
FAST = dict(first_wait=0.25, settle=0.0)

PORT = 8777

# control-type overlay: param name -> enum labels (list params)
try:
    _pui = json.loads((Path(__file__).resolve().parent / "_param_ui.json").read_text())
    LABELS = {k: v["labels"] for k, v in _pui.get("controls", {}).items() if "labels" in v}
    UNITS = {k: v["unit"] for k, v in _pui.get("controls", {}).items() if "unit" in v}
except Exception:
    LABELS, UNITS = {}, {}

PREFIXES = ("P35_", "HD2_", "HX2_", "Agoura_", "Catena_")


def pretty(model: str) -> str:
    for p in PREFIXES:
        if model.startswith(p):
            model = model[len(p):]
            break
    return model


def role_of(model: str) -> str:
    m = model.lower()
    if "split" in m:
        return "split"
    if "join" in m:
        return "join"
    if "input" in m:
        return "input"
    if "output" in m:
        return "output"
    if "amp" in m:
        return "amp"
    if "cab" in m or "impulse" in m:
        return "cab"
    if "reverb" in m:
        return "reverb"
    if "delay" in m:
        return "delay"
    return "fx"


def control_for(name, ptype, pmin, pmax):
    """-> ('toggle'|'select'|'knob', labels_or_None)"""
    if ptype == "b":
        return "toggle", None
    if name in LABELS:
        return "select", LABELS[name]
    if ptype == "i":
        # small int range with no labels -> stepped knob
        return "knob", None
    return "knob", None


def _raw_params(mid, m0):
    """Params for one block parsed from the already-read edit buffer — the same
    merge edit_buffer_params does (model defs + stored values), but with NO
    device read. Avoids 1 round-trip per block."""
    stored = {}
    for p in (m0.get("parm") or []):
        if isinstance(p, dict) and isinstance(p.get("pid_"), int):
            stored[p["pid_"]] = p.get("valu")
    rows = {}
    for name, meta in defs.model_params_for(mid).items():
        pid = meta.get("id")
        if not isinstance(pid, int):
            continue
        rows[pid] = {"pid": pid, "name": name, "value": stored.get(pid),
                     "type": meta.get("type"), "min": meta.get("min"),
                     "max": meta.get("max"), "default": meta.get("def")}
    for pid, valu in stored.items():
        rows.setdefault(pid, {"pid": pid, "name": None, "value": valu,
                              "type": None, "min": None, "max": None, "default": None})
    return [rows[k] for k in sorted(rows)]


def build_state(h):
    eb = h.read_edit_buffer()  # ONE device read for the whole rig (~1s), not 1/block
    flow = (eb.get("sfg_") or {}).get("flow") or []
    paths = {}
    for pi, dsp in enumerate(flow):
        if not isinstance(dsp, dict):
            continue
        for slot, b in HelixClient._blks_pairs(dsp):
            mdls = b.get("mdls") if isinstance(b, dict) else None
            m0 = mdls[0] if isinstance(mdls, list) and mdls else None
            mid = m0.get("id__") if isinstance(m0, dict) else None
            if not isinstance(mid, int):
                continue
            params = []
            for p in _raw_params(mid, m0):
                if p.get("name") is None:
                    continue
                v = p["value"]
                if v is None:
                    v = p.get("default")
                if isinstance(v, bool):
                    v = 1.0 if v else 0.0
                if v is None:
                    continue
                ctl, labels = control_for(p["name"], p["type"], p["min"], p["max"])
                lo, hi = p["min"], p["max"]
                if isinstance(lo, bool):
                    lo = 0
                if isinstance(hi, bool):
                    hi = 1
                params.append({
                    "pid": p["pid"], "name": p["name"], "value": float(v),
                    "min": lo, "max": hi, "type": p["type"], "ctl": ctl,
                    "labels": labels, "unit": UNITS.get(p["name"], ""),
                })
            model = defs.model_name_for(mid) or str(mid)
            paths.setdefault(pi, []).append({
                "path": pi, "block": slot, "model": pretty(model),
                "role": role_of(model), "enabled": bool(b.get("enbl", 1)),
                "params": params,
            })
    return {"paths": [{"path": k, "blocks": paths[k]} for k in sorted(paths)]}


class App(BaseHTTPRequestHandler):
    client = None
    lock = threading.Lock()

    def log_message(self, *a):  # quiet
        pass

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            body = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/state":
            try:
                with self.lock:
                    st = build_state(self.client)
                self._json(200, st)
            except Exception as e:  # noqa: BLE001
                self._json(500, {"error": str(e)})
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(n) or b"{}")
        try:
            with self.lock:
                if self.path == "/param":
                    lo, hi = req.get("min"), req.get("max")
                    v = float(req["value"])
                    if lo is not None:
                        v = max(float(lo), v)
                    if hi is not None:
                        v = min(float(hi), v)
                    p, slot = int(req["path"]), _grid_slot(int(req["block"]))
                    self.client._rpc("/ParamValueSet",
                                     [("i", p), ("i", slot), ("i", 0),
                                      ("i", int(req["pid"])), ("f", v), ("i", -1)],
                                     **FAST)
                elif self.path == "/bypass":
                    p, slot = int(req["path"]), _grid_slot(int(req["block"]))
                    self.client._rpc("/BlockEnableSet",
                                     [("i", p), ("i", slot),
                                      ("i", 1 if req["enable"] else 0)], **FAST)
                else:
                    self._json(404, {"error": "no"})
                    return
            self._json(200, {"ok": True})
        except Exception as e:  # noqa: BLE001
            self._json(500, {"error": str(e)})


PAGE = r"""<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Helix live chain</title>
<style>
:root{color-scheme:dark}
body{margin:0;background:#0f1117;color:#e7eaf0;font:14px/1.4 -apple-system,Segoe UI,Roboto,sans-serif}
header{padding:12px 18px;border-bottom:1px solid #222838;display:flex;align-items:center;gap:12px}
header b{font-size:15px}
.dot{width:9px;height:9px;border-radius:50%;background:#36d399;display:inline-block}
.err{color:#ff6b6b;font-size:12px}
main{padding:16px;max-width:980px;margin:0 auto}
.path{margin-bottom:26px}
.path-hd{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:#7f8aa6;margin:0 2px 10px}
.rig{display:flex;flex-direction:column}
.blk{background:#1b1e27;border:1px solid #2c313f;border-radius:14px;padding:12px 14px 14px}
.blk.off{opacity:.42}
.blk.structural{background:#171a22;border-style:dashed;border-color:#3a4664;align-self:center;padding:6px 16px;border-radius:999px}
.hd{display:flex;align-items:center;gap:9px;margin-bottom:10px}
.blk.structural .hd{margin-bottom:0}
.role{font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:#8a90a2}
.name{font-weight:650;color:#eef1f7}
.sp{flex:1}
.byp{font-size:10px;font-weight:650;letter-spacing:.04em;padding:4px 11px;border-radius:999px;border:1px solid #3a4152;cursor:pointer;user-select:none;color:#9aa0b2;background:#222634}
.byp.on{background:#1f3a2b;border-color:#36d399;color:#4ade9a}
.params{display:flex;flex-wrap:wrap;gap:14px 18px;align-items:flex-start}
.knob{width:72px;text-align:center}
.knob .dial{cursor:ns-resize;touch-action:none}
.pn{font-size:9px;color:#8a90a2;text-transform:uppercase;letter-spacing:.04em;margin-top:2px}
.pv{font-size:11px;color:#dfe3ec;font-weight:600}
.sw{min-width:120px}
.sw .pn{margin-bottom:4px}
.sw select{width:100%;background:#222634;color:#dfe3ec;border:1px solid #3a4152;border-radius:7px;padding:5px 7px;font-size:12px}
.tog{display:flex;flex-direction:column;align-items:center;width:72px}
.pill{width:46px;height:24px;border-radius:999px;background:#39414f;position:relative;cursor:pointer;margin-bottom:3px}
.pill.on{background:#2b7a52}
.pill i{position:absolute;top:2px;left:2px;width:20px;height:20px;border-radius:50%;background:#e7eaf0;transition:left .12s}
.pill.on i{left:24px}
.arrow{align-self:center;color:#3a4152;font-size:15px;padding:2px 0}
</style></head><body>
<header><span class=dot></span><b>Helix live chain</b>
<span style="color:#7f8aa6;font-size:12px">live edit buffer — tweaks write to the device</span>
<span class=sp></span><span id=msg class=err></span>
<button id=reload style="background:#222634;color:#ccd;border:1px solid #3a4152;border-radius:8px;padding:5px 11px;cursor:pointer">Re-read device</button>
</header>
<main id=root><p style="color:#7f8aa6">Loading live chain…</p></main>
<script>
let STATE=null;
const msg=(t)=>{document.getElementById('msg').textContent=t||''};
async function load(){
  try{const r=await fetch('/state');const j=await r.json();
    if(j.error){msg('load: '+j.error);return}
    STATE=j;render();msg('')}catch(e){msg('load failed: '+e)}
}
function dialSVG(p){
  const f=(p.value-p.min)/((p.max-p.min)||1),a0=135,a1=405;
  const ang=(a0+f*(a1-a0))*Math.PI/180,cx=24,cy=24,r=18;
  const px=cx+r*Math.cos(ang),py=cy+r*Math.sin(ang);
  const s=a0*Math.PI/180,sx=cx+r*Math.cos(s),sy=cy+r*Math.sin(s);
  const lg=f*(a1-a0)>180?1:0;
  return `<svg class="dial" width="48" height="48" viewBox="0 0 48 48">
    <circle cx="24" cy="24" r="18" fill="none" stroke="#2c313f" stroke-width="5" />
    <path d="M ${sx.toFixed(1)} ${sy.toFixed(1)} A 18 18 0 ${lg} 1 ${px.toFixed(1)} ${py.toFixed(1)}" fill="none" stroke="#5b8cff" stroke-width="5" stroke-linecap="round" />
    <circle cx="24" cy="24" r="11" fill="#262b38" />
    <line x1="24" y1="24" x2="${px.toFixed(1)}" y2="${py.toFixed(1)}" stroke="#eef1f7" stroke-width="2" /></svg>`;
}
function fmtVal(p){
  let v=p.value;
  if(p.labels){const i=Math.round(v);return p.labels[i]!==undefined?p.labels[i]:i}
  if(p.type==='i')return Math.round(v)+(p.unit?' '+p.unit:'');
  if(Math.abs(v)>=1000)return (v/1000).toFixed(2)+'k';
  return (Number.isInteger(v)?v:v.toFixed(2))+(p.unit?' '+p.unit:'');
}
// Coalesce: at most ONE write in flight; while it runs, newer moves just
// overwrite the pending entry (keyed by block+pid), so a fast drag collapses
// to its latest value instead of queueing every sample. Body reads p.value at
// SEND time, so whatever's pending is always the newest position.
let _inflight=false; const _pending=new Map();
function postParam(p,b){ _pending.set(b.path+'/'+b.block+'/'+p.pid,{p,b}); pump(); }
async function pump(){
  if(_inflight)return;
  const it=_pending.entries().next(); if(it.done)return;
  const [k,e]=it.value; _pending.delete(k); _inflight=true;
  try{
    const r=await fetch('/param',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({path:e.b.path,block:e.b.block,pid:e.p.pid,value:e.p.value,min:e.p.min,max:e.p.max})});
    const j=await r.json(); if(j&&j.error)msg('write: '+j.error);
  }catch(err){msg('write: '+err)}
  _inflight=false; pump();
}
function postBypass(b){
  fetch('/bypass',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({path:b.path,block:b.block,enable:b.enabled})})
    .then(r=>r.json()).then(j=>{if(j.error)msg('bypass: '+j.error)}).catch(e=>msg('bypass: '+e));
}
// ---- undo/redo: ONE entry per committed change (a knob drag commits on
// release, not per live sample). Entries hold the STATE param/block objects,
// which survive render(), so undo just rewrites the value and re-pushes.
const undoS=[], redoS=[];
function record(kind,p,b,before,after){ if(before===after)return;
  undoS.push({kind,p,b,before,after}); redoS.length=0; }
function applyEntry(e,val){
  if(e.kind==='bypass'){ e.b.enabled=!!val; postBypass(e.b); }
  else { e.p.value=val; postParam(e.p,e.b); }
  render();
}
function undo(){ const e=undoS.pop(); if(!e)return; redoS.push(e); applyEntry(e,e.before); }
function redo(){ const e=redoS.pop(); if(!e)return; undoS.push(e); applyEntry(e,e.after); }
window.addEventListener('keydown',(ev)=>{
  const mod=ev.metaKey||ev.ctrlKey; if(!mod)return;
  const k=ev.key.toLowerCase();
  if(k==='z'){ ev.preventDefault(); ev.shiftKey?redo():undo(); }
  else if(k==='y'){ ev.preventDefault(); redo(); }
});

function paramEl(p,b){
  const wrap=document.createElement('div');
  if(p.ctl==='toggle'){
    wrap.className='tog';
    wrap.innerHTML=`<div class="pill ${p.value>=0.5?'on':''}"><i></i></div><div class=pn>${p.name}</div>`;
    wrap.querySelector('.pill').onclick=()=>{const before=p.value;p.value=p.value>=0.5?0:1;
      wrap.querySelector('.pill').classList.toggle('on',p.value>=0.5);postParam(p,b);record('param',p,b,before,p.value)};
    return wrap;
  }
  if(p.ctl==='select'){
    wrap.className='sw';
    const opts=p.labels.map((o,i)=>`<option value=${i} ${Math.round(p.value)===i?'selected':''}>${o}</option>`).join('');
    wrap.innerHTML=`<div class=pn>${p.name}</div><select>${opts}</select>`;
    wrap.querySelector('select').onchange=(e)=>{const before=p.value;p.value=+e.target.value;postParam(p,b);record('param',p,b,before,p.value)};
    return wrap;
  }
  wrap.className='knob';
  const dh=document.createElement('div');dh.innerHTML=dialSVG(p);
  const pv=document.createElement('div');pv.className='pv';pv.textContent=fmtVal(p);
  const pn=document.createElement('div');pn.className='pn';pn.textContent=p.name;
  wrap.append(dh,pv,pn);
  const down=(e)=>{const sy=(e.touches?e.touches[0].clientY:e.clientY),sv=p.value;
    const span=(p.max-p.min)||1;
    const mv=(e2)=>{const y=(e2.touches?e2.touches[0].clientY:e2.clientY);
      let nv=sv+(sy-y)/160*span;nv=Math.max(p.min,Math.min(p.max,nv));
      if(p.type==='i'||p.labels)nv=Math.round(nv);
      else nv=Math.round(nv*1000)/1000;
      if(nv!==p.value){p.value=nv;dh.innerHTML=dialSVG(p);pv.textContent=fmtVal(p);postParam(p,b)}
      e2.preventDefault&&e2.preventDefault();};
    const up=()=>{postParam(p,b);record('param',p,b,sv,p.value);
      document.removeEventListener('mousemove',mv);document.removeEventListener('mouseup',up);
      document.removeEventListener('touchmove',mv);document.removeEventListener('touchend',up)};
    document.addEventListener('mousemove',mv);document.addEventListener('mouseup',up);
    document.addEventListener('touchmove',mv,{passive:false});document.addEventListener('touchend',up);
    e.preventDefault();};
  dh.addEventListener('mousedown',down);dh.addEventListener('touchstart',down,{passive:false});
  return wrap;
}
function blockEl(b){
  const structural=(b.role==='split'||b.role==='join');
  const el=document.createElement('div');
  el.className='blk'+(b.enabled?'':' off')+(structural?' structural':'');
  const hd=document.createElement('div');hd.className='hd';
  hd.innerHTML=`<span class=role>${b.role}</span><span class=name>${b.model}</span><span class=sp></span>`;
  if(!structural){
    const by=document.createElement('span');by.className='byp'+(b.enabled?' on':'');
    by.textContent=b.enabled?'ON':'BYP';
    by.onclick=()=>{const before=b.enabled;b.enabled=!b.enabled;by.classList.toggle('on',b.enabled);by.textContent=b.enabled?'ON':'BYP';
      el.classList.toggle('off',!b.enabled);postBypass(b);record('bypass',null,b,before,b.enabled)};
    hd.append(by);
  }
  el.append(hd);
  if(b.params.length){const pc=document.createElement('div');pc.className='params';
    b.params.forEach(p=>pc.append(paramEl(p,b)));el.append(pc)}
  return el;
}
function render(){
  const root=document.getElementById('root');root.innerHTML='';
  STATE.paths.forEach(pt=>{
    const sec=document.createElement('div');sec.className='path';
    sec.innerHTML=`<div class=path-hd>DSP path ${pt.path}</div>`;
    const rig=document.createElement('div');rig.className='rig';
    pt.blocks.forEach((b,i)=>{
      if(i>0){const a=document.createElement('div');a.className='arrow';a.textContent='↓';rig.append(a)}
      rig.append(blockEl(b));
    });
    sec.append(rig);root.append(sec);
  });
}
document.getElementById('reload').onclick=load;
load();
</script></body></html>"""


def main():
    ip = discovery.resolve_ip(None)
    port = discovery.resolve_port(ip)
    print(f"device: {ip}:{port}")
    with HelixClient(ip, port) as h:
        App.client = h
        srv = HTTPServer(("127.0.0.1", PORT), App)
        url = f"http://127.0.0.1:{PORT}/"
        print(f"serving {url}  (Ctrl-C to stop)")
        threading.Timer(0.6, webbrowser.open, args=(url,)).start()
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\nbye")


if __name__ == "__main__":
    main()
