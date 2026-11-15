"""Hand-built, theme-aware technical drawings (SVG) with live values.

An IEC-style single-line diagram of the modelled network and a three-phase +
neutral phasor diagram. Both use CSS ``var(--...)`` colours so they flip with the
app theme, and both are labelled with numbers from the current run -- technical
drawings, not slide art.
"""

from __future__ import annotations

import math

_FS = "font-family:Inter,sans-serif"
_FM = "font-family:'JetBrains Mono',monospace"


def single_line_svg(nameplate_kva, fuse_a, phase_load_pu, phase_blown, v_ln=240.0,
                    homes_per_phase=None) -> str:
    """IEC single-line: grid -> Dyn transformer -> LV busbar -> three fused phase
    feeders -> loads, labelled with live per-phase load and blow status."""
    xs = [170, 360, 550]
    phases = "ABC"
    b = ['<svg viewBox="0 0 720 430" xmlns="http://www.w3.org/2000/svg" width="100%">']
    acc, mut, txt, dng, ok = "var(--accent)", "var(--muted)", "var(--text)", "var(--danger)", "var(--ok)"

    # grid source + HV drop
    b.append(f'<circle cx="360" cy="34" r="20" style="fill:none;stroke:{mut};stroke-width:2"/>')
    b.append(f'<path d="M352 34 q4 -8 8 0 q4 8 8 0" style="fill:none;stroke:{mut};stroke-width:2"/>')
    b.append(f'<text x="390" y="38" style="{_FS};font-size:12px;fill:{mut}">11 kV grid</text>')
    b.append(f'<line x1="360" y1="54" x2="360" y2="86" style="stroke:{txt};stroke-width:2"/>')

    # transformer (Dyn) -- two circles
    b.append(f'<circle cx="360" cy="104" r="19" style="fill:none;stroke:{acc};stroke-width:2.2"/>')
    b.append(f'<circle cx="360" cy="126" r="19" style="fill:none;stroke:{acc};stroke-width:2.2"/>')
    b.append(f'<text x="392" y="112" style="{_FM};font-size:12px;fill:{txt}">{nameplate_kva:.0f} kVA</text>')
    b.append(f'<text x="392" y="128" style="{_FS};font-size:11px;fill:{mut}">Dyn11, {v_ln:.0f} V L-N</text>')
    b.append(f'<line x1="360" y1="145" x2="360" y2="176" style="stroke:{txt};stroke-width:2"/>')

    # LV busbar
    b.append(f'<line x1="150" y1="176" x2="570" y2="176" style="stroke:{txt};stroke-width:4"/>')
    b.append(f'<text x="150" y="168" style="{_FM};font-size:11px;fill:{mut}">LV busbar</text>')

    for i, x in enumerate(xs):
        blown = bool(phase_blown[i]) if phase_blown is not None else False
        col = dng if blown else ok
        pu = float(phase_load_pu[i]) if phase_load_pu is not None else 0.0
        # drop + fuse
        b.append(f'<line x1="{x}" y1="176" x2="{x}" y2="210" style="stroke:{txt};stroke-width:2"/>')
        b.append(f'<rect x="{x-11}" y="210" width="22" height="34" rx="2" '
                 f'style="fill:var(--surface);stroke:{col};stroke-width:2"/>')
        b.append(f'<text x="{x+18}" y="232" style="{_FM};font-size:11px;fill:{col}">{fuse_a:.0f} A</text>')
        # feeder + load
        b.append(f'<line x1="{x}" y1="244" x2="{x}" y2="330" style="stroke:{col};stroke-width:2"/>')
        b.append(f'<path d="M{x-12} 330 L{x+12} 330 L{x} 352 Z" style="fill:none;stroke:{txt};stroke-width:2"/>')
        hp = f"~{int(homes_per_phase[i])} homes" if homes_per_phase is not None else "homes"
        b.append(f'<text x="{x}" y="372" text-anchor="middle" style="{_FS};font-size:11px;fill:{mut}">{hp}</text>')
        b.append(f'<text x="{x}" y="200" text-anchor="middle" style="{_FM};font-size:12px;fill:{col}">'
                 f'&#966;{phases[i]} {pu:.2f}x</text>')
        b.append(f'<text x="{x}" y="392" text-anchor="middle" style="{_FM};font-size:11px;fill:{col}">'
                 f'{"BLOWN" if blown else "intact"}</text>')
    b.append("</svg>")
    return "".join(b)


def phasor_svg(phase_mag, theme_unused=None, title="Three-phase + neutral") -> str:
    """Three current phasors at 0/-120/+120 scaled by per-phase load, and the
    neutral phasor = their vector sum. A balanced set sums to ~0; imbalance grows it."""
    cx, cy, scale = 150.0, 150.0, 95.0
    mags = [max(float(m), 1e-6) for m in phase_mag]
    norm = max(mags)
    acc, mut, txt, dng = "var(--accent)", "var(--muted)", "var(--text)", "var(--danger)"
    cols = ["var(--cat1)", "var(--cat2)", "var(--cat3)"]
    labs = "ABC"
    angles = [90.0, -30.0, 210.0]  # A up, then -120, +120
    b = [f'<svg viewBox="0 0 300 300" xmlns="http://www.w3.org/2000/svg" width="100%">']
    b.append(f'<circle cx="{cx}" cy="{cy}" r="{scale}" style="fill:none;stroke:var(--border);stroke-width:1"/>')
    nx = ny = 0.0
    for m, ang, col, lab in zip(mags, angles, cols, labs):
        r = scale * m / norm
        ex = cx + r * math.cos(math.radians(ang))
        ey = cy - r * math.sin(math.radians(ang))
        nx += r * math.cos(math.radians(ang))
        ny += r * math.sin(math.radians(ang))
        b.append(f'<line x1="{cx}" y1="{cy}" x2="{ex:.1f}" y2="{ey:.1f}" style="stroke:{col};stroke-width:2.4"/>')
        b.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="3" style="fill:{col}"/>')
        b.append(f'<text x="{ex:.1f}" y="{ey-6:.1f}" text-anchor="middle" style="{_FM};font-size:11px;fill:{col}">{lab}</text>')
    # neutral = vector sum
    nex, ney = cx + nx, cy - ny
    nmag = math.hypot(nx, ny)
    b.append(f'<line x1="{cx}" y1="{cy}" x2="{nex:.1f}" y2="{ney:.1f}" style="stroke:{dng};stroke-width:2.6;stroke-dasharray:4 3"/>')
    b.append(f'<circle cx="{cx}" cy="{cy}" r="3" style="fill:{txt}"/>')
    b.append(f'<text x="{cx}" y="22" text-anchor="middle" style="{_FS};font-size:12px;fill:{mut}">{title}</text>')
    b.append(f'<text x="{cx}" y="290" text-anchor="middle" style="{_FM};font-size:11px;fill:{dng}">'
             f'neutral |I_n| &#8776; {nmag/scale*norm:.2f} (rel)</text>')
    b.append("</svg>")
    return "".join(b)
