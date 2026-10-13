"""Hand-built, theme-aware SVG diagrams for the PACER showcase.

Every diagram is a pure function returning an SVG string. Colours reference the
injected CSS variables (``var(--accent)`` etc.) through inline ``style`` so the
drawings flip with the dark/light toggle automatically. The style is deliberately
engineering-grade: thin strokes, muted fills, no gradients or shadows.
"""

from __future__ import annotations

_FS = "font-family:'IBM Plex Sans',sans-serif"
_FM = "font-family:'IBM Plex Mono',monospace"


# --- small SVG builders ---------------------------------------------------------
def _wrap(view_w: int, view_h: int, body: str, max_w: int = 960) -> str:
    return (
        f'<div style="width:100%;max-width:{max_w}px;margin:0.25rem 0;">'
        f'<svg viewBox="0 0 {view_w} {view_h}" width="100%" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" '
        f'style="height:auto;display:block">{body}</svg></div>'
    )


def _box(x, y, w, h, title, sub="", accent="var(--accent)", rx=6, title_size=15, fill="var(--surface)"):
    out = (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
        f'style="fill:{fill};stroke:{accent};stroke-width:1.5"/>'
        f'<rect x="{x}" y="{y}" width="4" height="{h}" rx="2" style="fill:{accent}"/>'
    )
    ty = y + (22 if sub else h / 2 + 5)
    out += (
        f'<text x="{x + 16}" y="{ty}" style="{_FS};font-size:{title_size}px;'
        f'font-weight:600;fill:var(--text)">{title}</text>'
    )
    if sub:
        for i, line in enumerate(sub.split("\n")):
            out += (
                f'<text x="{x + 16}" y="{y + 44 + i * 17}" '
                f'style="{_FS};font-size:12px;fill:var(--muted)">{line}</text>'
            )
    return out


def _arrow(x1, y1, x2, y2, label="", color="var(--muted)", dashed=False, lx=None, ly=None, label_mono=True):
    dash = 'stroke-dasharray="5 4"' if dashed else ""
    out = (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'style="stroke:{color};stroke-width:1.5" {dash} marker-end="url(#arrowhead)"/>'
    )
    if label:
        lx = lx if lx is not None else (x1 + x2) / 2
        ly = ly if ly is not None else (y1 + y2) / 2 - 6
        font = _FM if label_mono else _FS
        out += (
            f'<text x="{lx}" y="{ly}" text-anchor="middle" '
            f'style="{font};font-size:10.5px;fill:{color}">{label}</text>'
        )
    return out


def _defs(color="var(--muted)") -> str:
    return (
        '<defs><marker id="arrowhead" markerWidth="9" markerHeight="7" refX="8" refY="3.5" '
        f'orient="auto"><polygon points="0 0, 9 3.5, 0 7" style="fill:{color}"/></marker></defs>'
    )


def _chip(x, y, text, color="var(--ok)"):
    w = 10 + len(text) * 6.4
    return (
        f'<rect x="{x}" y="{y}" width="{w:.0f}" height="20" rx="3" '
        f'style="fill:none;stroke:{color};stroke-width:1"/>'
        f'<text x="{x + w/2:.0f}" y="{y + 14}" text-anchor="middle" '
        f'style="{_FM};font-size:10.5px;fill:{color}">{text}</text>'
    )


# -------------------------------------------------------------------------------
# 1. System architecture -- the three layers
# -------------------------------------------------------------------------------
def system_architecture() -> str:
    b = _defs()
    # DISCOM / Orchestrator-lite
    b += _box(40, 30, 470, 92, "Orchestrator-lite",
              "DISCOM web app. In: RDSS meter data, complaint logs.\nOut: target transformers, phase-rebalancing orders, keys, results.",
              accent="var(--accent)")
    b += _box(560, 30, 360, 92, "DISCOM control room",
              "Target list - restoration view - season report.\nLinks to an ADMS later.", accent="var(--muted)")
    b += _arrow(510, 76, 560, 76, "cellular", lx=535, ly=70)

    # Beacon
    b += _box(40, 170, 470, 100, "PACER Beacon  (per targeted transformer)",
              "Live IEC 60076-7 per-phase thermal model.\nHolds each phase below 85% of its fuse-melting load.\nSigned guidance, rate-limited, per-Beacon key.",
              accent="var(--caution)")
    b += _chip(355, 178, "Rs 15k-40k", "var(--muted)")
    b += _arrow(275, 122, 275, 170, "down: targets, keys", lx=360, ly=150)
    b += _arrow(230, 170, 230, 122, "up: results", lx=150, ly=150, color="var(--muted)")

    # transformer + phases on the right
    b += _box(620, 170, 300, 100, "Transformer + LV feeder",
              "Three phases R / Y / B.\nA fuse on each phase; long, unbalanced lines.", accent="var(--muted)")
    b += _arrow(510, 220, 620, 220, "LoRa broadcast", lx=565, ly=214, color="var(--caution)")

    # PACER Core devices
    b += _box(40, 320, 880, 110, "PACER Core  (inside the devices that cause the surge)",
              "Plug-in Module for any stabiliser (Rs 1,350-2,300)  -  inverter-charger firmware  -  water pumps  -  e-rickshaw chargers.\nSeven local rules, zero communication needed. Works on its own; sharper with the Beacon.",
              accent="var(--ok)")
    b += _arrow(275, 270, 275, 320, "signed guidance to phases R/Y/B", lx=430, ly=300, color="var(--caution)")
    b += _chip(720, 328, "Rs 0 to households", "var(--ok)")
    return _wrap(960, 450, b)


# -------------------------------------------------------------------------------
# 2. The surge mechanism -- the problem cascade
# -------------------------------------------------------------------------------
def surge_mechanism() -> str:
    b = _defs("var(--danger)")
    steps = [
        ("Dusk", "Solar output fades", "var(--muted)"),
        ("Load-shedding", "DISCOM cuts the block", "var(--muted)"),
        ("Restore", "All stabilisers wait the\nsame fixed 3 min", "var(--accent)"),
        ("Lockstep restart", "ACs, chargers, pumps,\ne-rickshaws all at once", "var(--caution)"),
        ("~2x rating", "Transformer overloaded", "var(--danger)"),
        ("Fuse blows", "2-hour cut becomes\na 5-hour blackout", "var(--danger)"),
    ]
    x = 20
    w = 142
    gap = 10
    y = 40
    for i, (t, s, c) in enumerate(steps):
        b += _box(x, y, w, 96, t, s, accent=c, title_size=13)
        if i < len(steps) - 1:
            b += _arrow(x + w, y + 48, x + w + gap, y + 48, color="var(--muted)")
        x += w + gap
    # outcome stats
    b += (
        f'<text x="20" y="180" style="{_FM};font-size:12px;fill:var(--danger)">'
        f'200 / 200 restorations blow the fuse  -  ~197 of 200 homes left dark  -  '
        f'146 h insulation life lost (if over-fused)</text>'
    )
    return _wrap(940, 200, b)


# -------------------------------------------------------------------------------
# 3. The seven-rule control loop
# -------------------------------------------------------------------------------
def seven_rules_flow() -> str:
    b = _defs()
    # a horizontal pipeline with a stress branch
    nodes = [
        (30, 70, "Normal", "grid present", "var(--muted)"),
        (190, 70, "1  Outage timer", "ignore blips < 60 s", "var(--accent)"),
        (360, 70, "2  Random wait", "window grows with\noutage length", "var(--accent)"),
        (530, 70, "3  Soft start", "55% cooling,\n30% charging", "var(--accent)"),
        (700, 70, "4  Stress sensing", "V vs learned normal\nover own impedance", "var(--accent)"),
    ]
    for (x, y, t, s, c) in nodes:
        b += _box(x, y, 150, 80, t, s, accent=c, title_size=13)
    b += _arrow(180, 110, 190, 110)
    b += _arrow(340, 110, 360, 110)
    b += _arrow(510, 110, 530, 110)
    b += _arrow(680, 110, 700, 110)

    # stress decision down to back-off; else stepped return
    b += _box(700, 210, 150, 76, "5  Back-off", "prob. rises with stress,\nhold 6-12 min", accent="var(--caution)", title_size=13)
    b += _arrow(775, 150, 775, 210, color="var(--caution)", label="stressed", lx=815, ly=185)
    b += _box(360, 210, 150, 76, "6  Stepped return", "small random steps,\nno rebound peak", accent="var(--ok)", title_size=13)
    b += _arrow(700, 248, 510, 248, color="var(--muted)", label="hold expires", lx=605, ly=242)
    b += _box(30, 210, 150, 76, "Back to normal", "flat, coordinated\nrecovery", accent="var(--ok)", title_size=13)
    b += _arrow(360, 248, 180, 248, color="var(--ok)")
    b += _arrow(105, 210, 105, 150, color="var(--ok)")
    b += _arrow(700, 130, 775, 130)  # into sensing continues
    b += _arrow(775, 150, 775, 150)
    # not-stressed path from sensing to stepped return
    b += _arrow(700, 130, 435, 130, color="var(--muted)", dashed=True, label="not stressed", lx=560, ly=124)
    b += _arrow(435, 150, 435, 210, color="var(--muted)", dashed=True)

    # health-first + fail-safe band
    b += _box(30, 310, 540, 64, "7  Health first (always wins)",
              "A room above 32 C gets a cooling floor that rises to full power in ~25 min\n(faster for registered-vulnerable homes); its randomised start is kept.",
              accent="var(--danger)", title_size=13)
    b += _box(590, 310, 320, 64, "Fail-safe",
              "Any fault returns the device to normal\nbehaviour. No command can switch a load ON.",
              accent="var(--muted)", title_size=13)
    return _wrap(940, 395, b)


# -------------------------------------------------------------------------------
# 4. LV feeder topology (technical drawing)
# -------------------------------------------------------------------------------
def feeder_topology() -> str:
    b = _defs()
    # transformer on the left
    b += _box(20, 150, 150, 110, "Distribution\ntransformer", "11 kV / 415 V\noverloaded, near rating", accent="var(--accent)", title_size=13)
    b += _chip(28, 232, "Beacon", "var(--caution)")
    phases = [("R", 60, "var(--cat1)"), ("Y", 150, "var(--cat2)"), ("B", 240, "var(--cat3)")]
    # busbars + fuses
    for name, yy, col in phases:
        # fuse box near transformer
        b += (f'<rect x="185" y="{yy-12}" width="26" height="24" rx="3" '
              f'style="fill:var(--surface);stroke:var(--danger);stroke-width:1.4"/>'
              f'<text x="198" y="{yy+4}" text-anchor="middle" style="{_FM};font-size:10px;fill:var(--danger)">F</text>')
        b += _arrow(170, yy, 185, yy, color=col)
        # feeder line
        b += f'<line x1="211" y1="{yy}" x2="900" y2="{yy}" style="stroke:{col};stroke-width:2"/>'
        b += f'<text x="225" y="{yy-8}" style="{_FM};font-size:11px;fill:{col}">Phase {name}</text>'
        # homes tapped along the feeder
        for hx in range(260, 880, 90):
            b += (f'<line x1="{hx}" y1="{yy}" x2="{hx}" y2="{yy+22}" style="stroke:var(--border);stroke-width:1"/>'
                  f'<rect x="{hx-9}" y="{yy+22}" width="18" height="14" rx="2" '
                  f'style="fill:var(--surface);stroke:{col};stroke-width:1"/>')
    b += (f'<text x="20" y="330" style="{_FS};font-size:12px;fill:var(--muted)">'
          f'Homes sit behind a short series impedance, so each home\'s voltage sag is produced by the aggregate load '
          f'(what Rule 4 senses). The worst phase runs 10-20% above average.</text>')
    b += (f'<text x="20" y="352" style="{_FS};font-size:12px;fill:var(--muted)">'
          f'One fuse per phase: when it melts, every home on that phase goes dark - AC or not.</text>')
    b += _chip(760, 150, "Module in each home", "var(--ok)")
    return _wrap(940, 370, b)


# -------------------------------------------------------------------------------
# 5. Module hardware block diagram
# -------------------------------------------------------------------------------
def module_hardware() -> str:
    b = _defs()
    b += _box(30, 30, 880, 36, "Plug-in Module  -  parts Rs 760-1,465  -  retail Rs 1,350-2,300", "", accent="var(--ok)", title_size=14)
    cards = [
        (30, 90, "Voltage + current\nsensing", "learns normal V,\nestimates line impedance", "var(--accent)"),
        (250, 90, "PACER Core MCU", "the seven rules;\noutage-scaled timing", "var(--accent)"),
        (470, 90, "30 A AC-3 relay", "switches the stabiliser /\ncompressor start", "var(--caution)"),
        (690, 90, "IR blaster /\nhard-wired", "soft-starts inverter ACs;\nhard-wires others", "var(--muted)"),
    ]
    for (x, y, t, s, c) in cards:
        b += _box(x, y, 200, 92, t, s, accent=c, title_size=13)
    b += _arrow(230, 136, 250, 136)
    b += _arrow(450, 136, 470, 136)
    b += _arrow(670, 136, 690, 136)
    b += _box(30, 212, 880, 56, "LoRa receiver (optional)",
              "Listens for the Beacon's signed, rate-limited guidance and lowers the phase cap. If it hears nothing, PACER Core runs on its own.",
              accent="var(--caution)", title_size=13)
    return _wrap(940, 285, b)


# -------------------------------------------------------------------------------
# 6. Beacon hardware block diagram
# -------------------------------------------------------------------------------
def beacon_hardware() -> str:
    b = _defs()
    b += _box(30, 30, 880, 36, "PACER Beacon  -  Rs 15,000-40,000  -  one per targeted transformer", "", accent="var(--caution)", title_size=14)
    cards = [
        (30, 90, "Per-phase current\n+ temperature", "three phases R / Y / B", "var(--accent)"),
        (250, 90, "IEC 60076-7\nthermal model", "top-oil + hot-spot,\nper phase, live", "var(--accent)"),
        (470, 90, "Fuse-heat tracker", "keeps each phase < 85%\nof its melting load", "var(--danger)"),
        (690, 90, "Signed LoRa\nbroadcast", "per-Beacon key,\nrate-limited, expires", "var(--caution)"),
    ]
    for (x, y, t, s, c) in cards:
        b += _box(x, y, 200, 92, t, s, accent=c, title_size=13)
    b += _arrow(230, 136, 250, 136)
    b += _arrow(450, 136, 470, 136)
    b += _arrow(670, 136, 690, 136)
    b += _box(30, 212, 880, 52, "Guidance can only ever REDUCE load, and always expires",
              "Devices infer their phase by correlating their own voltage against the Beacon's per-phase reference; if unlocked, they assume the worst phase.",
              accent="var(--ok)", title_size=13)
    return _wrap(940, 282, b)


# -------------------------------------------------------------------------------
# 7. Roadmap timeline
# -------------------------------------------------------------------------------
def roadmap_timeline() -> str:
    b = _defs()
    b += f'<line x1="40" y1="60" x2="920" y2="60" style="stroke:var(--border);stroke-width:2"/>'
    phases = [
        (40, "Prototype", "Oct-Nov 2026", "Firmware vs the simulation,\nBeacon thermal model, dashboard", "var(--accent)"),
        (265, "Approvals", "Dec 2026-Apr 2027", "BIS + WPC (3-5 mo, Rs 3.5-10 L);\nDISCOM letter of intent", "var(--caution)"),
        (490, "Pilot", "Apr-Sep 2027", "2 overloaded + 2 control\ntransformers (Rs 7-17 L)", "var(--ok)"),
        (715, "Scale", "2028 onwards", "BEE 'grid-friendly restart' label,\nmanufacturer firmware, export", "var(--accent)"),
    ]
    for (x, t, when, s, c) in phases:
        b += f'<circle cx="{x+10}" cy="60" r="7" style="fill:{c};stroke:var(--surface);stroke-width:2"/>'
        b += _box(x, 84, 205, 96, t, s, accent=c, title_size=14)
        b += f'<text x="{x+16}" y="104" style="{_FM};font-size:11px;fill:{c}">{when}</text>'
    return _wrap(960, 195, b)
