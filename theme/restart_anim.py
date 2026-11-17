"""Animated IEC single-line "restart player" -- self-contained HTML/SVG + JS.

The static ``single_line_svg`` draws one instant; this replays the whole
restart. Every frame is a *real computed minute* of a trial: per-phase load
comes straight from ``phase_load_pu`` and each phase trips at its real fuse
blow minute (``blow_minute_phase``). Nothing is interpolated or canned -- it is
the engine's own result, drawn as an IEC single-line and stepped in time.

Rendered through ``st.components.v1.html`` (an iframe), so it is handed explicit
theme hex colours instead of CSS ``var(--...)``; the app rebuilds it on a theme
toggle. The three modes are baked in and switched client-side (no rerun).
"""

from __future__ import annotations

import json

# Phase drop x-positions on the 760-wide canvas, and the phase letters.
_XS = [190, 380, 570]
_PHASES = "ABC"
_GAUGE_MAX = 2.2  # pu ceiling for the load gauge (covers the ~2x lockstep surge)


def restart_feeder_html(modes, homes_per_phase, fuse_a, nameplate_kva, v_ln,
                        restore_minute, outage_start, window_start, colors,
                        melt_pu: float = 1.45, height: int = 560) -> str:
    """Return a self-contained HTML document for the animated feeder.

    ``modes``: list (Baseline, PACER only, PACER+Beacon order) of
      ``{"label": str, "loads": [[a,b,c], ...], "online": [...], "blow": [r,r,r]}``
      indexed over frames ``f = 0..W-1``. Real minute = ``window_start + f``;
      minute-since-restore = ``window_start + f - restore_minute``. ``blow[i]`` is
      the phase's blow minute *since restoration* (int) or ``null`` if it held.
    """
    data = {
        "modes": modes,
        "homesPhase": [int(h) for h in homes_per_phase],
        "meltPu": float(melt_pu),
        "gaugeMax": _GAUGE_MAX,
        "restore": int(restore_minute),
        "outage": int(outage_start),
        "t0": int(window_start),
        "fuseA": float(fuse_a),
        "kva": float(nameplate_kva),
        "vln": float(v_ln),
        "xs": _XS,
        "colors": colors,
    }
    return _TEMPLATE.replace("/*__PAYLOAD__*/0", json.dumps(data)).replace("__HEIGHT__", str(int(height)))


# Static SVG skeleton (grid -> Dyn transformer -> LV busbar -> three fused
# feeders -> home blocks) with id'd elements the JS updates each frame. Colours
# are placeholders set by JS from the theme payload.
_TEMPLATE = r"""<!doctype html>
<html><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
* { box-sizing: border-box; }
html,body { margin:0; padding:0; }
#root { font-family:'Inter',system-ui,sans-serif; padding:4px 2px 0; }
.svgwrap { width:100%; }
svg { width:100%; height:auto; display:block; }
.mono { font-family:'JetBrains Mono',monospace; }
.tabs { display:flex; gap:6px; margin:2px 0 8px; flex-wrap:wrap; }
.tab { font:600 12px 'Inter',sans-serif; padding:5px 12px; border-radius:999px; cursor:pointer;
       border:1px solid; background:transparent; transition:all .12s ease; }
.bar { display:flex; align-items:center; gap:10px; margin-top:8px; flex-wrap:wrap; }
.play { font:600 12px 'Inter',sans-serif; padding:6px 14px; border-radius:999px; cursor:pointer; border:1px solid; min-width:74px; }
input[type=range]{ flex:1; min-width:140px; accent-color:currentColor; height:4px; cursor:pointer; }
.read { display:flex; gap:16px; align-items:baseline; margin:6px 2px 0; flex-wrap:wrap; }
.read .big { font:700 15px 'JetBrains Mono',monospace; }
.read .lab { font:500 11px 'Inter',sans-serif; }
#statusLbl { font:600 12.5px 'Inter',sans-serif; margin:8px 2px 2px; min-height:18px; }
</style></head>
<body><div id="root">
  <div class="tabs" id="tabs"></div>
  <div class="svgwrap">
  <svg viewBox="0 0 760 392" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Animated IEC single-line restart">
    <!-- grid source -->
    <circle id="gridC" cx="380" cy="34" r="19" fill="none" stroke-width="2"/>
    <path id="gridW" d="M372 34 q4 -8 8 0 q4 8 8 0" fill="none" stroke-width="2"/>
    <text id="gridT" x="406" y="38" font-size="12">11 kV grid</text>
    <line id="l1" x1="380" y1="53" x2="380" y2="85" stroke-width="2"/>
    <!-- Dyn transformer -->
    <circle id="txA" cx="380" cy="103" r="18" fill="none" stroke-width="2.2"/>
    <circle id="txB" cx="380" cy="124" r="18" fill="none" stroke-width="2.2"/>
    <text id="txT1" class="mono" x="408" y="108" font-size="12"></text>
    <text id="txT2" x="408" y="124" font-size="11"></text>
    <line id="l2" x1="380" y1="142" x2="380" y2="170" stroke-width="2"/>
    <!-- LV busbar -->
    <line id="bus" x1="150" y1="170" x2="610" y2="170" stroke-width="4"/>
    <text id="busT" class="mono" x="150" y="163" font-size="11">LV busbar</text>
    <!-- phase groups injected by JS -->
    <g id="phases"></g>
  </svg>
  </div>
  <div id="statusLbl"></div>
  <div class="read">
    <div><span class="big" id="minLbl"></span> <span class="lab" id="minSub"></span></div>
    <div><span class="big" id="onlineLbl"></span> <span class="lab">homes online</span></div>
    <div><span class="big" id="darkLbl"></span> <span class="lab">homes dark</span></div>
  </div>
  <div class="bar">
    <button class="play" id="playBtn">Pause</button>
    <input type="range" id="scrub" min="0" value="0"/>
  </div>
</div>
<script>
var D = /*__PAYLOAD__*/0;
var C = D.colors, XS = D.xs, NF = D.modes[0].loads.length;
var TOTAL = D.homesPhase.reduce(function(a,b){return a+b;},0);
var mode = 0, f = 0, playing = true, timer = null;

function el(id){ return document.getElementById(id); }
function col(load){ return load >= D.meltPu ? C.danger : (load >= 1.0 ? C.caution : C.ok); }

// ---- static theme paint ----
function paintStatic(){
  el('root').style.background = C.surface; el('root').style.color = C.text;
  [['gridC',C.muted],['gridW',C.muted],['l1',C.text],['txA',C.accent],['txB',C.accent],
   ['l2',C.text],['bus',C.text]].forEach(function(p){ el(p[0]).setAttribute('stroke',p[1]); });
  el('gridT').setAttribute('fill',C.muted); el('txT1').setAttribute('fill',C.text);
  el('txT2').setAttribute('fill',C.muted); el('busT').setAttribute('fill',C.muted);
  el('txT1').textContent = D.kva.toFixed(0)+' kVA';
  el('txT2').textContent = 'Dyn11, '+D.vln.toFixed(0)+' V L-N';
  // build phase groups
  var g = el('phases'), melt = D.meltPu, GM = D.gaugeMax, ns = 'http://www.w3.org/2000/svg';
  var ph = '';
  for (var i=0;i<3;i++){
    var x = XS[i], L = 'ABC'[i];
    var gy = 234, gh = 64, gy0 = gy-gh;                       // gauge track top..bottom
    var ty = gy - (melt/GM)*gh;                               // melt threshold y
    ph += '<g>';
    ph += '<text id="load'+i+'" class="mono" x="'+x+'" y="192" text-anchor="middle" font-size="12.5"></text>';
    ph += '<line x1="'+x+'" y1="170" x2="'+x+'" y2="200" stroke="'+C.muted+'" stroke-width="2"/>';
    ph += '<rect id="fuse'+i+'" x="'+(x-13)+'" y="200" width="26" height="34" rx="2" fill="'+C.surface+'" stroke-width="2.4"/>';
    ph += '<text class="mono" x="'+(x-20)+'" y="221" text-anchor="end" font-size="10.5" fill="'+C.muted+'">'+D.fuseA.toFixed(0)+'A</text>';
    // load gauge
    ph += '<rect x="'+(x+20)+'" y="'+gy0+'" width="9" height="'+gh+'" rx="2" fill="none" stroke="'+C.border+'" stroke-width="1"/>';
    ph += '<rect id="gauge'+i+'" x="'+(x+20)+'" y="'+gy+'" width="9" height="0" rx="2"/>';
    ph += '<line x1="'+(x+17)+'" y1="'+ty+'" x2="'+(x+32)+'" y2="'+ty+'" stroke="'+C.danger+'" stroke-width="1.4" stroke-dasharray="3 2"/>';
    ph += '<text class="mono" x="'+(x+35)+'" y="'+(ty+3)+'" font-size="8.5" fill="'+C.danger+'">melt</text>';
    // feeder + home block
    ph += '<line id="feeder'+i+'" x1="'+x+'" y1="234" x2="'+x+'" y2="300" stroke-width="2.4"/>';
    ph += '<rect id="block'+i+'" x="'+(x-56)+'" y="306" width="112" height="60" rx="8" stroke-width="1.6"/>';
    ph += '<text x="'+x+'" y="325" text-anchor="middle" font-size="12" font-weight="600" fill="'+C.text+'">Phase '+L+'</text>';
    ph += '<text class="mono" x="'+x+'" y="341" text-anchor="middle" font-size="11" fill="'+C.muted+'">'+D.homesPhase[i]+' homes</text>';
    ph += '<text id="stat'+i+'" class="mono" x="'+x+'" y="358" text-anchor="middle" font-size="10.5" font-weight="600"></text>';
    ph += '</g>';
  }
  g.innerHTML = ph;
}

// ---- per-frame render ----
function render(){
  var m = D.t0 + f, rel = m - D.restore, M = D.modes[mode];
  var duringOutage = (m >= D.outage && m < D.restore);
  var darkHomes = 0, worst = 0, worstLoad = -1, blewNow = -1;
  for (var i=0;i<3;i++){
    var load = M.loads[f][i], bl = M.blow[i];
    var blown = (bl !== null && rel >= bl);
    var live = !duringOutage && !blown;
    if (blown) darkHomes += D.homesPhase[i];
    if (duringOutage) darkHomes += 0;          // outage counted separately via online
    if (load > worstLoad){ worstLoad = load; worst = i; }
    if (bl !== null && rel === bl) blewNow = i;
    // load text
    var lt = el('load'+i); lt.textContent = String.fromCharCode(966)+'ABC'[i]+' '+load.toFixed(2)+String.fromCharCode(215);
    lt.setAttribute('fill', duringOutage ? C.muted : col(load));
    // gauge
    var gh = 64, gy = 234, h = Math.max(0, Math.min(1, load/D.gaugeMax))*gh;
    var gg = el('gauge'+i); gg.setAttribute('y', gy-h); gg.setAttribute('height', h);
    gg.setAttribute('fill', duringOutage ? C.muted : col(load));
    // fuse + feeder
    var state = blown ? C.danger : (live ? C.ok : C.muted);
    el('fuse'+i).setAttribute('stroke', state);
    el('feeder'+i).setAttribute('stroke', state);
    // home block
    var b = el('block'+i), st = el('stat'+i);
    if (blown){ b.setAttribute('fill', C.danger+'22'); b.setAttribute('stroke', C.danger);
                st.setAttribute('fill', C.danger); st.textContent = 'DARK'; }
    else if (duringOutage){ b.setAttribute('fill', C.muted+'18'); b.setAttribute('stroke', C.border);
                st.setAttribute('fill', C.muted); st.textContent = 'OUT'; }
    else { b.setAttribute('fill', C.ok+'1f'); b.setAttribute('stroke', C.ok);
                st.setAttribute('fill', C.ok); st.textContent = 'LIVE'; }
  }
  // readouts
  var online = duringOutage ? 0 : Math.round(M.online[f]);
  el('minLbl').textContent = (rel>=0?'+':'')+rel+' min';
  el('minSub').textContent = rel>=0 ? 'since restoration' : 'blackout';
  el('onlineLbl').textContent = online+' / '+TOTAL;
  el('darkLbl').textContent = String(darkHomes);
  el('darkLbl').style.color = darkHomes>0 ? C.danger : C.muted;
  // status headline
  var s = el('statusLbl');
  if (duringOutage){ s.textContent = 'Blackout - supply off, all '+TOTAL+' homes dark'; s.style.color = C.muted; }
  else if (blewNow >= 0){ s.textContent = String.fromCharCode(966)+'ABC'[blewNow]+' fuse melts at +'+M.blow[blewNow]+' min -> '+D.homesPhase[blewNow]+' homes dropped'; s.style.color = C.danger; }
  else if (darkHomes>0){ s.textContent = darkHomes+' homes dark on blown phase(s) - '+(3-blownCount(M,rel))+' phases still live'; s.style.color = C.danger; }
  else { s.textContent = 'Restart holding - worst '+String.fromCharCode(966)+'ABC'[worst]+' at '+worstLoad.toFixed(2)+String.fromCharCode(215)+' rating, fuses intact'; s.style.color = C.ok; }
  // scrub cursor
  el('scrub').value = f;
}
function blownCount(M, rel){ var n=0; for(var i=0;i<3;i++){ if(M.blow[i]!==null && rel>=M.blow[i]) n++; } return n; }

// ---- controls ----
function step(){ f = (f+1) % NF; render(); }
function play(){ playing=true; el('playBtn').textContent='Pause'; clearInterval(timer); timer=setInterval(step,150); }
function pause(){ playing=false; el('playBtn').textContent='Play'; clearInterval(timer); }
el('playBtn').onclick = function(){ playing ? pause() : play(); };
el('scrub').oninput = function(){ pause(); f = +this.value; render(); };
el('scrub').max = NF-1;

function buildTabs(){
  var t = el('tabs'); t.innerHTML='';
  D.modes.forEach(function(md, i){
    var btn = document.createElement('button'); btn.className='tab'; btn.textContent = md.label;
    btn.onclick = function(){ mode=i; paintTabs(); render(); };
    t.appendChild(btn);
  });
  paintTabs();
}
function paintTabs(){
  [].forEach.call(el('tabs').children, function(btn, i){
    var on = (i===mode);
    btn.style.background = on ? C.accent : 'transparent';
    btn.style.color = on ? '#fff' : C.muted;
    btn.style.borderColor = on ? C.accent : C.border;
  });
}

paintStatic(); buildTabs();
el('playBtn').style.borderColor=C.border; el('playBtn').style.color=C.text;
el('scrub').style.color=C.accent;
render(); play();
</script></body></html>
"""
