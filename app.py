"""PACER-Sim -- Streamlit showcase + simulator.

This module is UI only. All physics and statistics live in the (Streamlit-free)
``engine`` package; this file drives the engine and presents the whole PACER
project: the problem, the architecture, the control design, the live simulator,
the impact case, and the team.

Run:  streamlit run app.py
"""

from __future__ import annotations

import datetime as _dt
import hashlib

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from engine.config import Config, ControllerMode, HeatwavePreset
from engine.montecarlo import (
    SWEEP_VARIABLES,
    MonteCarloResult,
    SweepResult,
    run_monte_carlo,
    run_sweep,
)
from engine.simulation import TrialResult, run_trial, scenario_structure
from theme import diagrams, phase_colors, semantic, theme_css, themed_figure

APP_VERSION = "0.4.0"
BUILD_DATE = "2026-10-13"

TEAM = [
    ("Sreerag M R", "Team lead", "Indian Maritime University",
     "Naval Architecture & Ship Building", "sreeragmr03@gmail.com"),
    ("Navami S", "Team member", "Rajagiri School of Engineering & Technology",
     "Electrical & Electronics Engineering", "navamisuthesh015@gmail.com"),
    ("Amarnath Suresh", "Team member", "Rajagiri School of Engineering & Technology",
     "Electrical & Electronics Engineering", "amarnathsuresh10@gmail.com"),
]

# Published scenario matrix from the project deck (slide 9). Reference figures;
# the live engine in this app reproduces the baseline exactly and gives
# PACER/PACER+Beacon in the same order -- see the Results tab for the honest note.
DECK_SCENARIOS = [
    ("Tight fuse, 33-38 C evening", 200, 25, 1),
    ("Tight fuse, 42 C heatwave", 200, 19, 1),
    ("Tight fuse, 45 C heatwave", 200, 33, 0),
    ("Tight fuse, slower room model", 200, 85, 50),
    ("Correctly sized fuse", 200, 0, 0),
]

# One-click scenario presets -> scenario widget state overrides.
PRESETS: dict[str, dict] = {
    "Default (hot evening)": dict(tight=1.00, ambient="Hot (42 C)", custom=42, outage=120, nameplate=160.0, ac=60),
    "Tight fuse, 38 C": dict(tight=1.00, ambient="Custom", custom=38, outage=120, nameplate=160.0, ac=60),
    "45 C heatwave": dict(tight=1.00, ambient="Custom", custom=45, outage=150, nameplate=160.0, ac=70),
    "Correctly sized fuse": dict(tight=1.25, ambient="Hot (42 C)", custom=42, outage=120, nameplate=160.0, ac=60),
    "Over-fused site": dict(tight=1.40, ambient="Hot (42 C)", custom=42, outage=120, nameplate=160.0, ac=60),
    "Long cut, high AC": dict(tight=1.00, ambient="Hot (42 C)", custom=42, outage=240, nameplate=160.0, ac=85),
}

# Sensitivity-sweep ranges per Config field.
SWEEP_RANGES: dict[str, list[float]] = {
    "ambient_peak_c": [34.0, 36.0, 38.0, 40.0, 42.0, 44.0, 46.0],
    "fuse_tightness": [0.80, 0.90, 1.00, 1.10, 1.20, 1.30],
    "ac_penetration": [0.20, 0.40, 0.60, 0.80, 1.00],
    "outage_minutes": [30, 60, 90, 120, 180, 240],
    "nameplate_kva": [120.0, 140.0, 160.0, 180.0, 200.0, 240.0],
    "vulnerable_fraction": [0.00, 0.05, 0.10, 0.20, 0.30],
}

st.set_page_config(page_title="PACER-Sim", layout="wide", initial_sidebar_state="expanded")


# ---------------------------------------------------------------------------
# Cached compute + small helpers
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False, hash_funcs={Config: lambda c: c.key()})
def _compute_trial(config: Config, mode: str, trial_index: int) -> TrialResult:
    return run_trial(config.with_mode(ControllerMode(mode)), trial_index)


@st.cache_data(show_spinner=False, hash_funcs={Config: lambda c: c.key()})
def _compute_modes(config: Config, trial_index: int) -> dict[str, TrialResult]:
    """One trial per controller mode on the identical scenario (for comparison)."""
    return {m.value: run_trial(config.with_mode(m), trial_index) for m in ControllerMode}


@st.cache_data(show_spinner=False, hash_funcs={Config: lambda c: c.key()})
def _compute_structure(config: Config) -> dict:
    return scenario_structure(config)


def _config_hash(config: Config) -> str:
    return hashlib.sha1(repr(config.key()).encode()).hexdigest()[:8]


_MODE_ORDER = ["baseline", "pacer", "pacer_beacon"]
_MODE_LABEL = {"baseline": "Baseline", "pacer": "PACER only", "pacer_beacon": "PACER + Beacon"}


def _mode_colors(theme: str) -> dict[str, str]:
    sem = semantic(theme)
    return {"baseline": sem["danger"], "pacer": sem["accent"], "pacer_beacon": sem["ok"]}


def _svg(html: str) -> None:
    st.markdown(html, unsafe_allow_html=True)


def _kicker(kicker: str, lead: str | None = None) -> None:
    st.markdown(f'<div class="pacer-kicker">{kicker}</div>', unsafe_allow_html=True)
    if lead:
        st.markdown(f'<div class="pacer-lead">{lead}</div>', unsafe_allow_html=True)


def _stat_tiles(items: list[tuple[str, str, str]]) -> None:
    cols = st.columns(len(items))
    for col, (n, label, kind) in zip(cols, items):
        cls = f"pacer-stat {kind}".strip()
        col.markdown(f'<div class="{cls}"><div class="n">{n}</div><div class="l">{label}</div></div>',
                     unsafe_allow_html=True)


def _card(title: str, bullets: list[str], kind: str = "accent") -> str:
    items = "".join(f"<li>{b}</li>" for b in bullets)
    return f'<div class="pacer-card {kind}"><h4>{title}</h4><ul>{items}</ul></div>'


def _cards_row(cards: list[str]) -> None:
    cols = st.columns(len(cards))
    for col, c in zip(cols, cards):
        col.markdown(c, unsafe_allow_html=True)


def _back_to_top() -> None:
    st.markdown('<a class="pacer-top-link" href="#top">Back to top</a>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session state + header
# ---------------------------------------------------------------------------
_SCENARIO_DEFAULTS = dict(
    sc_mode="Baseline", sc_homes=200, sc_ac=60, sc_vuln=8, sc_nameplate=160.0, sc_tight=1.00,
    sc_outage=120, sc_ambient="Hot (42 C)", sc_custom=42, sc_runs=200, sc_seed=7,
    sc_invshare=45, sc_charger=40, sc_erick=12, sc_pump=35, sc_baseload=0.18, sc_faultprob=0,
)


def _init_state() -> None:
    st.session_state.setdefault("theme", "light")
    st.session_state.setdefault("active", None)
    st.session_state.setdefault("confirm_reset", False)
    st.session_state.setdefault("section", "Simulator")
    st.session_state.setdefault("ledger", [])
    st.session_state.setdefault("sim_trial", 0)
    st.session_state.setdefault("sweep", None)
    for k, v in _SCENARIO_DEFAULTS.items():
        st.session_state.setdefault(k, v)


def _apply_preset(name: str) -> None:
    p = PRESETS[name]
    st.session_state.sc_tight = p["tight"]
    st.session_state.sc_ambient = p["ambient"]
    st.session_state.sc_custom = p["custom"]
    st.session_state.sc_outage = p["outage"]
    st.session_state.sc_nameplate = p["nameplate"]
    st.session_state.sc_ac = p["ac"]


def _toggle_theme() -> None:
    st.session_state.theme = "dark" if st.session_state.theme == "light" else "light"


def _render_header(config: Config, theme: str) -> None:
    st.markdown('<a class="pacer-skip" href="#main-content">Skip to content</a><span id="top"></span>',
                unsafe_allow_html=True)
    with st.container():
        st.markdown('<span class="pacer-header-marker"></span>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns([6, 3, 2], vertical_alignment="center")
        with c1:
            st.markdown(
                '<div class="pacer-title">PACER<span class="dot">-</span>Sim</div>'
                '<div class="pacer-subtitle">Phase-Aware Coordinated Energisation &amp; Recovery '
                '-- stopping the blackout after the blackout</div>',
                unsafe_allow_html=True)
        with c2:
            st.markdown(
                f'<div class="pacer-build">seed <b>{config.seed}</b> &middot; cfg <b>{_config_hash(config)}</b>'
                f'<br>build {BUILD_DATE} &middot; v{APP_VERSION}</div>', unsafe_allow_html=True)
        with c3:
            label = "Switch to dark" if theme == "light" else "Switch to light"
            st.button(label, on_click=_toggle_theme, width='stretch', key="theme_btn")


def _footer(active: dict | None) -> None:
    ran = active["ts"].strftime("%Y-%m-%d %H:%M:%S") if active else "no simulation run yet"
    st.markdown(
        f'<div class="pacer-foot">PACER-Sim v{APP_VERSION} &middot; build {BUILD_DATE} &middot; '
        f'Team PACERS &middot; Challenge 03 (Grid Reliability) &middot; last simulation {ran} &middot; '
        f'simulated results, openly reproducible.</div>', unsafe_allow_html=True)


# ===========================================================================
# SHOWCASE PAGES
# ===========================================================================
def _hero() -> None:
    st.markdown(
        '<div class="pacer-hero">'
        '<div class="eyebrow">Challenge 03 &middot; Grid Reliability &amp; Renewable Intermittency</div>'
        '<h1>Stopping the blackout after the blackout.</h1>'
        '<p>When a load-shedding block ends, every AC, inverter charger, pump and e-rickshaw charger '
        'restarts in lockstep and hits the transformer at ~2x its rating -- the fuse blows and a 2-hour '
        'cut becomes a 5-hour blackout. PACER puts a seven-rule, communication-free protocol inside the '
        'devices so they stagger and soften their own restart; an optional per-transformer Beacon makes '
        'it fuse-aware.</p>'
        '<div class="tags"><span class="tag">200 &rarr; 1 fuse blow-outs</span>'
        '<span class="tag">Rs 0 to households</span><span class="tag">8 new mechanisms</span>'
        '<span class="tag">IEC 60076-7 grounded</span></div></div>',
        unsafe_allow_html=True)


def _page_overview() -> None:
    _hero()
    _stat_tiles([
        ("200 -> 1", "fuse blow-outs per 200 restorations (deck: Today -> PACER+Beacon)", "ok"),
        ("2,400-3,600", "customer-hours of outage avoided per transformer per summer", "ok"),
        ("Rs 0", "cost to households -- Modules fitted free", "ok"),
        ("0.35-1.5 t", "CO2e avoided per transformer per year", "ok"),
    ])
    st.markdown("#### System at a glance")
    _svg(diagrams.system_architecture())
    _cards_row([
        _card("PACER Core (in the devices)", [
            "Plug-in Module for any stabiliser (Rs 1,350-2,300), charger firmware, pumps, e-rickshaws",
            "Seven local rules, zero communication needed",
            "Can only ever make a device more cautious",
        ], "ok"),
        _card("PACER Beacon (per transformer)", [
            "Live IEC 60076-7 per-phase thermal model",
            "Holds each phase below 85% of its fuse-melting load",
            "Signed guidance over licence-exempt LoRa",
        ], "caution"),
        _card("Orchestrator-lite (DISCOM)", [
            "Uses RDSS meter data + complaint logs",
            "Picks target transformers, issues phase-rebalancing orders",
            "Measures reliability against a baseline",
        ], "accent"),
    ])
    _back_to_top()


def _page_problem() -> None:
    _kicker("The problem - when power returns, the street goes dark again")
    _svg(diagrams.surge_mechanism())
    st.markdown("#### Why it matters, and at scale")
    _stat_tiles([
        ("~1.3 million", "distribution transformers fail each year in India (~10% of the fleet)", "danger"),
        ("22.6 h", "average daily supply in rural India, 2025 (urban 23.4 h) -- restorations are daily", "caution"),
        ("24%", "RDSS transformer meters installed by Feb 2026 (1.26 of 5.25 million)", "caution"),
        ("10-20%", "the worst phase runs above the transformer average (imbalance)", "danger"),
    ])
    _cards_row([
        _card("Who is affected", [
            "Overloaded, unbalanced transformers take the hit first",
            "Homes without AC share the same fuse, so they go dark too",
            "Over-fused sites: thick wire replaces the fuse, so insulation cooks instead",
        ], "danger"),
        _card("Why today's fixes fail", [
            "Every stabiliser waits the same fixed 3 minutes -- loads restart in lockstep",
            "Section-by-section restoration does not help inside one transformer",
            "Transformer upgrades take months",
        ], "caution"),
    ])
    st.caption("Sources: CEA Standardization Cell (29 Oct 2025, via SolarQuarter/Mercom India); Ministry of "
               "Power / PIB (21 Feb 2025); PIB RDSS progress (2 Feb 2026). Headline collapse figures are "
               "simulated (PACER-Sim): overloaded transformer, 200 homes, 2-hour evening cut, 200 runs.")
    _back_to_top()


def _page_solution() -> None:
    _kicker("The proposed solution - works with zero communication, sharper with the Beacon",
            "Like the internet's traffic rules applied to electricity: when millions of computers share "
            "one network they do not all transmit at once and collide -- each waits a slightly different, "
            "randomised time and backs off when it senses congestion. PACER applies exactly that discipline "
            "to the restart. It needs no internet, no central server and no permission to act.")
    _svg(diagrams.system_architecture())
    _cards_row([
        _card("PACER Core - Module", [
            "Fits any stabiliser; 30 A AC-3 relay for compressor starts; IR blaster or hard-wired",
            "Parts Rs 760-1,465; retail Rs 1,350-2,300",
            "Also ships as inverter-charger firmware, pump and e-rickshaw control",
        ], "ok"),
        _card("PACER Beacon", [
            "Per-phase IEC 60076-7 thermal model; tracks each fuse's heating",
            "Keeps each phase below 85% of its melting load",
            "Rs 15,000-40,000; signed LoRa guidance, per-Beacon key",
        ], "caution"),
        _card("Orchestrator-lite", [
            "Standalone DISCOM web app; links to an ADMS later",
            "In: RDSS meter data, complaint logs",
            "Out: target transformers, phase-rebalancing orders, keys, measured results",
        ], "accent"),
    ])
    st.markdown("#### Safety by design")
    _cards_row([
        _card("No ON command anywhere", ["The signalling can only ever reduce load, never switch one on"], "ok"),
        _card("Everything is randomised + rate-limited", ["Each device randomises its own timing; releases are rate-limited"], "ok"),
        _card("Keyed + fail-safe", ["Each Beacon has its own key; any fault returns the device to normal behaviour"], "ok"),
    ])
    _back_to_top()


def _page_how_it_works() -> None:
    _kicker("Technical approach - seven local rules flatten the restart; the Beacon makes them fuse-aware")
    _svg(diagrams.seven_rules_flow())
    rules = [
        ("1  Outage timer", "Ignore supply blips under 60 s; only real outages count."),
        ("2  Random wait", "Each device draws a uniform random start inside a window that grows with the outage length (min(2 + 8 x hours, 25) min)."),
        ("3  Soft start", "Ramp up from a fraction of full power over 30 min: 55% for cooling, 30% for charging."),
        ("4  Stress sensing", "(learned-normal voltage - present voltage) / self-measured line impedance. Relative to a learned normal, never absolute voltage -- so it works even on a weak feeder sagging to ~190 V."),
        ("5  Back-off", "When stressed, cut the cap (AC x0.75 floor 0.35; charger x0.5 floor 0), then latch and hold for a random 6-12 min."),
        ("6  Stepped return", "Climb back in small random additive steps, so there is no synchronised rebound peak."),
        ("7  Health first (always wins)", "A room above 32 C gets a cooling floor that rises to full power in about 25 min (faster for registered-vulnerable homes), keeping its randomised start."),
    ]
    for t, d in rules:
        st.markdown(f"**{t}** &nbsp; {d}")
    st.markdown("#### Phase detection, with no wiring survey")
    st.markdown(
        "Devices work out which phase they are on by correlating their own voltage pattern against the "
        "Beacon's per-phase reference. If a device cannot lock onto a phase it assumes the worst (most "
        "constrained) phase, so an unlocked device is never less cautious. Hard safety rails sit under "
        "everything: a minimum off-time of 3 minutes, at most 6 starts per hour, and the absolute "
        "guarantee that no command can switch a load on.")
    _back_to_top()


def _page_architecture() -> None:
    _kicker("Architecture & hardware")
    st.markdown("#### Low-voltage feeder -- where PACER sits")
    _svg(diagrams.feeder_topology())
    st.markdown("#### Plug-in Module (PACER Core)")
    _svg(diagrams.module_hardware())
    st.markdown("#### PACER Beacon")
    _svg(diagrams.beacon_hardware())
    st.caption("Terms: AC-3 = IEC motor-switching duty for the relay; LoRa = licence-exempt long-range "
               "low-power radio; IEC 60076-7 = international loading guide for oil-immersed transformers.")
    _back_to_top()


def _impact_bar(theme: str) -> go.Figure:
    sem = semantic(theme)
    sev = {0: sem["danger"], 1: sem["caution"], 2: sem["ok"]}
    labels = [s[0] for s in DECK_SCENARIOS]
    fig = themed_figure(theme, height=360)
    for idx, (name, color_name) in enumerate([("Today", 0), ("PACER", 1), ("PACER + Beacon", 2)]):
        fig.add_trace(go.Bar(
            name=name, y=labels, x=[s[idx + 1] for s in DECK_SCENARIOS],
            orientation="h", marker_color=sev[color_name],
        ))
    fig.update_layout(title="Fuse blow-outs out of 200 restorations (project deck)",
                      barmode="group", xaxis_title="blow-outs / 200", legend_title_text="")
    return fig


def _page_impact() -> None:
    _kicker("Expected impact - each targeted transformer avoids 2,400-3,600 customer-hours of outage every summer")
    _stat_tiles([
        ("2,400-3,600", "customer-hours avoided / transformer / summer (12-18 h per household)", "ok"),
        ("-83 to -99%", "insulation ageing per restoration vs a rewired fuse", "ok"),
        ("Rs 0", "for households; homes without AC gain the most", "ok"),
    ])
    _stat_tiles([
        ("Rs 1.6-3.1 lakh", "per transformer + Rs 4,500-10,000 / yr; payback 9 months to 5.5 yr (central 1.8 yr)", "accent"),
        ("0.35-1.5 t", "CO2e avoided / transformer / yr (mostly transformers not replaced)", "ok"),
        ("Rs 7-20", "DISCOM cost per customer-hour of outage avoided", "accent"),
    ])
    st.plotly_chart(_impact_bar(st.session_state.theme), width='stretch',
                    theme=None, config={"displaylogo": False, "displayModeBar": False})
    st.markdown("#### At 1,000 protected transformers")
    _stat_tiles([
        ("2.4-3.6 million", "customer-hours of outage avoided every summer", "ok"),
        ("350-1,500 t", "CO2e avoided per year", "ok"),
    ])
    st.caption("Simulated (PACER-Sim) plus stated assumptions: ~40 evening restorations a summer, ~30% "
               "blowing the fuse today, 3-hour repairs; only a third to a half of the simulated benefit is "
               "counted. DISCOMs own Beacons and the Orchestrator; households own Modules, taken back under "
               "the E-Waste (Management) Rules, 2022. PACER saves almost no energy directly.")
    _back_to_top()


def _page_innovation() -> None:
    _kicker("Innovation - builds on known restart methods and adds eight new mechanisms")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(_card("Already exists elsewhere", [
            "Fixed and random restart delays",
            "Demand-response modes",
            "Frequency-responsive appliances",
            "AIMD EV-charging control (Studli et al., 2012)",
        ], "accent"), unsafe_allow_html=True)
    with c2:
        st.markdown(_card("New in PACER (8 mechanisms)", [
            "1. Outage-scaled waiting windows",
            "2. Phase lock by voltage matching",
            "3. Self-measured impedance sensing (works on 190-205 V feeders)",
            "4. Random latched back-off",
            "5. Rebound-free stepped release",
            "6. Heat-dose health rule",
            "7. Fuse-aware thermal Beacon",
            "8. Signalling that cannot switch loads on",
        ], "ok"), unsafe_allow_html=True)
    st.markdown("**Intellectual property.** Three hardware-anchored draft claims; provisional filing planned.")
    st.caption("Reference: Studli S, Crisostomi E, Middleton R, Shorten R. A flexible distributed framework "
               "for realising electric and plug-in hybrid vehicle charging policies. Int. J. Control 85(8), "
               "2012. doi:10.1080/00207179.2012.679970")
    _back_to_top()


def _page_alignment() -> None:
    _kicker("Alignment to Challenge 03 - PACER meets every goal at the transformer, where failures happen")
    df = pd.DataFrame([
        ("Bridge intermittency gaps", "Prevents re-outages after evening cuts"),
        ("Stay local", "Works at transformer level, no wide-area comms"),
        ("Affordable for low-income areas", "Rs 0 for households; Modules fitted free"),
        ("Support DISCOMs", "Data, forecasting, phase map and over-fusing alerts"),
        ("Reduce technical losses", "Flatter recovery and phase rebalancing"),
    ], columns=["Challenge 03 goal", "What PACER does"])
    st.table(df)
    st.markdown("#### Why it fits Indian grids")
    _cards_row([
        _card("The conditions already exist", [
            "Daily scheduled cuts make restorations frequent",
            "Stabilisers and home inverters already sit next to every AC",
            "LV lines are long, unbalanced and often over-fused",
        ], "accent"),
        _card("Fits the Schneider ecosystem", [
            "Luminous -- home inverters",
            "EcoStruxure -- grid software",
            "TeSys -- motor starters; Altivar -- variable-speed drives",
        ], "ok"),
    ])
    _back_to_top()


def _page_delivery() -> None:
    tabs = st.tabs(["User journey", "Roadmap", "Methodology"])
    with tabs[0]:
        _kicker("Key features & user journey - a simple journey for each user, and households pay nothing")
        _cards_row([
            _card("Household", [
                "Module fitted free; an LED shows 'pacing'",
                "Hot rooms get full cooling power within about 25 min",
                "An exemption button with a monthly quota",
                "Monthly SMS: '3 blackouts avoided'",
            ], "ok"),
            _card("Lineman / junior engineer", [
                "Beacon install and pairing; phase-lock check",
                "Phase-rebalancing work orders",
                "Fuse audit (find and replace rewired fuses)",
            ], "caution"),
            _card("DISCOM", [
                "Target list of transformers to protect first",
                "Restoration view",
                "Season report",
            ], "accent"),
        ])
        st.markdown("#### Who runs it")
        st.markdown(
            "- Women energy agents (Uttar Pradesh's Vidyut Sakhi model) and ITI electricians enrol homes and fit Modules.\n"
            "- The existing RDSS metering contractor maintains Beacons.\n"
            "- Linemen rebalance phases and replace rewired fuses.\n"
            "- A daily LoRa heartbeat flags removed Modules; seasonal credit is paid only while a Module is fitted.")
    with tabs[1]:
        _kicker("Implementation roadmap - a controlled pilot in summer 2027, then scale through labels and firmware")
        _svg(diagrams.roadmap_timeline())
        st.markdown(
            "- **Prototype (Oct-Nov 2026):** device firmware tested against the simulation, the Beacon thermal model, the dashboard.\n"
            "- **Approvals & partnership (Dec 2026-Apr 2027):** BIS and WPC approvals (3-5 months, Rs 3.5-10 lakh); a DISCOM letter of intent; a small batch.\n"
            "- **Pilot & measurement (Apr-Sep 2027):** two overloaded transformers plus two control transformers; budget ~Rs 7-17 lakh.\n"
            "- **Scale (2028 onwards):** a BEE 'grid-friendly restart' label and manufacturer firmware, then factories, farm pumps, soft load-shedding, export.")
        st.caption("Protection becomes strong only near full coverage, so we fit every AC home on a targeted "
                   "transformer first and add charger firmware next. Terms: BIS = Bureau of Indian Standards; "
                   "WPC = Wireless Planning & Coordination; BEE = Bureau of Energy Efficiency.")
    with tabs[2]:
        _tab_methodology(st.session_state.theme)
    _back_to_top()


def _page_team() -> None:
    _kicker("Team PACERS - power systems, electronics and systems design, working as one grid-reliability team")
    cards = []
    for name, role, college, field, email in TEAM:
        cards.append(_card(name, [role, college, field, email],
                           "accent" if role == "Team lead" else "ok"))
    _cards_row(cards)
    st.markdown("#### Project summary")
    st.markdown(
        "PACER (Phase-Aware Coordinated Energisation & Recovery) fixes the restart itself. A tiny protocol "
        "in the devices that create the spike waits a short outage-proportional delay, starts slowly, senses "
        "grid stress and backs off, while keeping overheated rooms cooled within about 25 minutes. No "
        "networking is required and it embeds for free in a Rs 1,350-2,300 plug-in Module or charger "
        "firmware. Each targeted transformer optionally carries a Beacon that tracks each phase's temperature "
        "and broadcasts radio guidance to hold every phase below 85% of its fuse-melting load. A web app "
        "helps DISCOMs target transformers and rebalance phases. In 200 simulated restorations of an "
        "overloaded transformer, today's uncoordinated restart burns a tight fuse every time; with PACER it "
        "drops sharply, and with the Beacon further still. Each targeted transformer saves 2,400-3,600 "
        "customer-hours of outage per summer and 0.35-1.5 t CO2e a year; households pay nothing.")
    st.caption("Submission: Schneider Electric challenge, Challenge 03 - Grid Reliability. "
               "Contact: sreeragmr03@gmail.com.")
    _back_to_top()


# ===========================================================================
# SIMULATOR (sidebar config + tabs)
# ===========================================================================
def _scenario_desc(config: Config) -> str:
    amb = config.peak_ambient_c
    return (f"{config.homes} homes, {config.nameplate_kva:.0f} kVA, fuse x{config.fuse_tightness:.2f}, "
            f"AC {config.ac_penetration*100:.0f}%, outage {config.outage_minutes} min, {amb:.0f} C")


def _build_config_from_state() -> tuple[Config, HeatwavePreset, float | None]:
    ss = st.session_state
    heatwave, custom_peak = HeatwavePreset.HOT, None
    amb = ss.sc_ambient
    if amb.startswith("Mild"):
        heatwave = HeatwavePreset.MILD
    elif amb.startswith("Heatwave"):
        heatwave = HeatwavePreset.HEATWAVE
    elif amb.startswith("Custom"):
        custom_peak = float(ss.sc_custom)
    mode = {m.label: m for m in ControllerMode}[ss.sc_mode]
    config = Config(
        mode=mode, homes=int(ss.sc_homes), ac_penetration=ss.sc_ac / 100.0,
        inverter_ac_share=ss.sc_invshare / 100.0, charger_penetration=ss.sc_charger / 100.0,
        erickshaw_penetration=ss.sc_erick / 100.0, pump_penetration=ss.sc_pump / 100.0,
        vulnerable_fraction=ss.sc_vuln / 100.0, base_load_kw_per_home=float(ss.sc_baseload),
        fault_probability=ss.sc_faultprob / 100.0, nameplate_kva=float(ss.sc_nameplate),
        fuse_tightness=float(ss.sc_tight), outage_minutes=int(ss.sc_outage), heatwave=heatwave,
        ambient_peak_c=custom_peak, mc_runs=int(ss.sc_runs), seed=int(ss.sc_seed))
    return config, heatwave, custom_peak


def _sidebar_scenario(sb) -> tuple[Config, bool]:
    ss = st.session_state
    sb.markdown("### Scenario presets")
    pcols = sb.columns(2)
    for i, name in enumerate(PRESETS):
        if pcols[i % 2].button(name, key=f"preset_{i}", width='stretch'):
            _apply_preset(name)
            st.rerun()

    sb.markdown("### Scenario")
    sb.selectbox("Controller mode", [m.label for m in ControllerMode], key="sc_mode",
                 help="The mode shown first on single-trial views; every view still compares all three.")
    sb.markdown("###### Population")
    sb.number_input("Homes on the transformer", 50, 500, step=10, key="sc_homes")
    sb.slider("AC penetration (%)", 0, 100, key="sc_ac")
    sb.slider("Registered-vulnerable homes (%)", 0, 30, key="sc_vuln")
    sb.markdown("###### Transformer and fuse")
    sb.number_input("Nameplate rating (kVA)", 50.0, 400.0, step=10.0, key="sc_nameplate")
    sb.slider("Fuse rating (x rated current)", 0.80, 1.40, step=0.05, key="sc_tight",
              help="1.0 = a tight fuse rated at the transformer's own rated current.")
    rated_i = (ss.sc_nameplate * 1000.0 / 3.0) / 240.0
    sb.caption(f"Fuse: {ss.sc_tight * rated_i:.0f} A/phase (rated current {rated_i:.0f} A/phase)")
    sb.markdown("###### Event and weather")
    sb.slider("Outage duration (min)", 0, 360, step=10, key="sc_outage")
    sb.selectbox("Ambient", ["Hot (42 C)", "Mild (34 C)", "Heatwave (46 C)", "Custom"], key="sc_ambient")
    if ss.sc_ambient.startswith("Custom"):
        sb.slider("Peak ambient (C)", 28, 48, key="sc_custom")
    with sb.expander("Advanced parameters"):
        st.slider("Inverter-AC share of ACs (%)", 0, 100, key="sc_invshare")
        st.slider("Inverter-charger penetration (%)", 0, 100, key="sc_charger")
        st.slider("E-rickshaw penetration (%)", 0, 100, key="sc_erick")
        st.slider("Water-pump penetration (%)", 0, 100, key="sc_pump")
        st.slider("Base load per home (kW)", 0.05, 0.50, step=0.01, key="sc_baseload")
        st.slider("Device fault probability (%)", 0, 20, key="sc_faultprob",
                  help="Faulted devices fall back to pass-through, as if PACER were absent.")
    sb.markdown("###### Monte Carlo")
    sb.slider("Trials per mode", 10, 500, step=10, key="sc_runs")
    sb.number_input("Random seed", 0, 1_000_000, step=1, key="sc_seed")

    config, _, _ = _build_config_from_state()
    problems = config.validate()
    if problems:
        for p in problems:
            sb.error(p)
    else:
        sb.markdown(f'<span class="pacer-chip ok">configuration valid</span> '
                    f'<span class="pacer-chip accent">deterministic &middot; seed {config.seed}</span>',
                    unsafe_allow_html=True)
    run_clicked = sb.button("Run simulation", type="primary", width='stretch', disabled=bool(problems))
    if not st.session_state.confirm_reset:
        if sb.button("Reset results", width='stretch'):
            st.session_state.confirm_reset = True
            st.rerun()
    else:
        sb.warning("Clear the current run and caches?")
        cc1, cc2 = sb.columns(2)
        if cc1.button("Confirm", width='stretch'):
            st.session_state.active = None
            st.session_state.sweep = None
            _compute_trial.clear()
            _compute_modes.clear()
            _compute_structure.clear()
            st.session_state.confirm_reset = False
            st.rerun()
        if cc2.button("Cancel", width='stretch'):
            st.session_state.confirm_reset = False
            st.rerun()
    return config, run_clicked


def _do_run(config: Config) -> None:
    holder = st.empty()
    with holder.container():
        st.markdown("Running Monte Carlo across all three modes...")
        bar = st.progress(0.0, text="Starting")
        last = {"bucket": -1}

        def cb(frac: float, msg: str) -> None:
            frac = min(max(frac, 0.0), 1.0)
            bucket = int(frac * 200)
            if bucket != last["bucket"]:
                last["bucket"] = bucket
                bar.progress(frac, text=msg)

        mc = run_monte_carlo(config, progress=cb)
    holder.empty()
    structure = _compute_structure(config)
    st.session_state.active = {"key": config.key(), "config": config, "mc": mc,
                               "structure": structure, "ts": _dt.datetime.now()}
    st.session_state.sim_trial = 0
    st.session_state.sweep = None
    rec = {"Time": _dt.datetime.now().strftime("%H:%M:%S"), "Config": _config_hash(config),
           "Seed": config.seed, "Runs": config.mc_runs, "Scenario": _scenario_desc(config)}
    for m in mc.modes:
        s = mc.stats[m]
        rec[m.label] = f"{s.blowout_runs}/{s.n_runs}"
    st.session_state.ledger.insert(0, rec)
    st.session_state.ledger = st.session_state.ledger[:30]


def _chart_config() -> dict:
    return {"displaylogo": False, "displayModeBar": False, "responsive": True}


def _add_event_markers(fig, tr, theme, mark_blow=True) -> None:
    sem = semantic(theme)
    x0 = tr.outage_start - tr.restore_minute
    fig.add_vrect(x0=x0, x1=0, fillcolor=sem["outage"], line_width=0, layer="below")
    fig.add_vline(x=0, line=dict(color=sem["muted"], width=1, dash="dot"))
    if mark_blow and tr.blew and tr.blow_minute_since_restore >= 0:
        fig.add_vline(x=tr.blow_minute_since_restore, line=dict(color=sem["danger"], width=1.5, dash="dash"))
        fig.add_annotation(x=tr.blow_minute_since_restore, yref="paper", y=1.0, text="fuse blow",
                           showarrow=False, font=dict(color=sem["danger"], size=10), xanchor="left",
                           bgcolor=sem["surface"])


def _time_axis(tr):
    return np.arange(tr.total_minutes) - tr.restore_minute


def _fig_load(tr, config, theme):
    sem = semantic(theme); t = _time_axis(tr)
    fig = themed_figure(theme, height=300)
    fig.add_trace(go.Scatter(x=t, y=tr.load_pu, mode="lines", name="Load", line=dict(color=sem["accent"], width=1.6)))
    fig.add_hline(y=1.0, line=dict(color=sem["muted"], width=1, dash="dot"), annotation_text="rating",
                  annotation_position="top left", annotation_font=dict(color=sem["muted"], size=10))
    _add_event_markers(fig, tr, theme)
    fig.update_layout(title="Aggregate load vs rating", yaxis_title="x rating", xaxis_title="minutes from restoration")
    return fig


def _fig_fuse(tr, config, theme):
    sem = semantic(theme); cols = phase_colors(theme); t = _time_axis(tr)
    fig = themed_figure(theme, height=300)
    for ph in range(config.phases):
        fig.add_trace(go.Scatter(x=t, y=tr.phase_heat_pct[:, ph], mode="lines",
                                 name=f"Phase {chr(65 + ph)}", line=dict(color=cols[ph], width=1.4)))
    fig.add_hline(y=100.0, line=dict(color=sem["danger"], width=1, dash="dash"), annotation_text="melt",
                  annotation_position="top left", annotation_font=dict(color=sem["danger"], size=10))
    _add_event_markers(fig, tr, theme)
    fig.update_layout(title="Per-phase fuse-heat", yaxis_title="% of melting", xaxis_title="minutes from restoration")
    return fig


def _fig_hotspot(tr, config, theme):
    sem = semantic(theme); t = _time_axis(tr)
    fig = themed_figure(theme, height=300)
    fig.add_trace(go.Scatter(x=t, y=tr.hot_spot_c, mode="lines", name="Hot-spot", line=dict(color=sem["accent"], width=1.6)))
    fig.add_trace(go.Scatter(x=t, y=tr.top_oil_c, mode="lines", name="Top-oil", line=dict(color=sem["muted"], width=1.2, dash="dot")))
    fig.add_hline(y=98.0, line=dict(color=sem["caution"], width=1, dash="dot"), annotation_text="98 C rated",
                  annotation_position="top left", annotation_font=dict(color=sem["caution"], size=10))
    _add_event_markers(fig, tr, theme, mark_blow=False)
    fig.update_layout(title="Transformer hot-spot (IEC 60076-7)", yaxis_title="C", xaxis_title="minutes from restoration")
    return fig


def _fig_voltage(tr, config, theme):
    sem = semantic(theme); t = _time_axis(tr)
    fig = themed_figure(theme, height=300)
    fig.add_trace(go.Scatter(x=t, y=tr.rep_voltage, mode="lines", name="Representative home", line=dict(color=sem["accent"], width=1.6)))
    fig.add_trace(go.Scatter(x=t, y=tr.min_voltage, mode="lines", name="Weakest home", line=dict(color=sem["caution"], width=1.2)))
    fig.add_hline(y=config.v_ln, line=dict(color=sem["muted"], width=1, dash="dot"), annotation_text="nominal",
                  annotation_position="top left", annotation_font=dict(color=sem["muted"], size=10))
    _add_event_markers(fig, tr, theme, mark_blow=False)
    fig.update_layout(title="Home voltage", yaxis_title="V (L-N)", xaxis_title="minutes from restoration")
    return fig


def _fig_online(tr, config, theme):
    sem = semantic(theme); t = _time_axis(tr)
    fig = themed_figure(theme, height=260)
    fig.add_trace(go.Scatter(x=t, y=tr.homes_online, mode="lines", name="Homes online",
                             line=dict(color=sem["ok"], width=1.6, shape="hv")))
    _add_event_markers(fig, tr, theme, mark_blow=True)
    fig.update_layout(title="Homes online", yaxis_title="homes", xaxis_title="minutes from restoration")
    return fig


def _tab_simulation(active, theme):
    config = active["config"]
    st.markdown("#### Single trial")
    c1, c2, _ = st.columns([2, 2, 4], vertical_alignment="bottom")
    with c1:
        mode_label = st.selectbox("Mode", [m.label for m in ControllerMode],
                                  index=[m for m in ControllerMode].index(config.mode), key="sim_mode")
        mode = {m.label: m for m in ControllerMode}[mode_label]
    with c2:
        trial_idx = st.number_input("Representative trial", 0, config.mc_runs - 1, 0, 1, key="sim_trial")
    tr = _compute_trial(config, mode.value, int(trial_idx))
    m1, m2, m3, m4, m5 = st.columns(5)
    blow_chip = '<span class="pacer-chip danger">blow-out</span>' if tr.blew else '<span class="pacer-chip ok">held</span>'
    m1.markdown("Outcome"); m1.markdown(blow_chip, unsafe_allow_html=True)
    m2.metric("Peak load", f"{tr.peak_pu:.2f} x")
    m3.metric("Homes dark", f"{tr.homes_dark}")
    m4.metric("Weakest voltage", f"{np.min(tr.min_voltage[tr.restore_minute:]):.0f} V")
    m5.metric("Blow-out at", f"{tr.blow_minute_since_restore} min" if tr.blew else "--")
    r1c1, r1c2 = st.columns(2)
    r1c1.plotly_chart(_fig_load(tr, config, theme), width='stretch', theme=None, config=_chart_config())
    r1c2.plotly_chart(_fig_fuse(tr, config, theme), width='stretch', theme=None, config=_chart_config())
    r2c1, r2c2 = st.columns(2)
    r2c1.plotly_chart(_fig_hotspot(tr, config, theme), width='stretch', theme=None, config=_chart_config())
    r2c2.plotly_chart(_fig_voltage(tr, config, theme), width='stretch', theme=None, config=_chart_config())
    st.plotly_chart(_fig_online(tr, config, theme), width='stretch', theme=None, config=_chart_config())
    _back_to_top()


def _tab_montecarlo(active, theme):
    mc = active["mc"]; sem = semantic(theme)
    st.markdown(f"#### {mc.n_runs} trials per mode")
    cols = st.columns(len(mc.modes))
    for col, m in zip(cols, mc.modes):
        s = mc.stats[m]
        col.metric(m.label, f"{s.blowout_runs / s.n_runs * 100:.1f}%", help="Blow-out rate")
        col.caption(f"{s.blowout_runs}/{s.n_runs} runs, 95% CI [{s.blowout_ci.low*100:.1f}, {s.blowout_ci.high*100:.1f}]%")
    sev = {ControllerMode.BASELINE: sem["danger"], ControllerMode.PACER: sem["caution"], ControllerMode.PACER_BEACON: sem["ok"]}
    labels = [m.label for m in mc.modes]
    rates = [mc.stats[m].blowout_runs / mc.stats[m].n_runs * 100 for m in mc.modes]
    lo = [mc.stats[m].blowout_ci.low * 100 for m in mc.modes]
    hi = [mc.stats[m].blowout_ci.high * 100 for m in mc.modes]
    fig = themed_figure(theme, height=320)
    fig.add_trace(go.Bar(x=labels, y=rates, marker_color=[sev[m] for m in mc.modes],
                         error_y=dict(type="data", symmetric=False, array=[h - r for h, r in zip(hi, rates)],
                                      arrayminus=[r - l for l, r in zip(lo, rates)], color=sem["muted"], thickness=1),
                         width=0.5))
    fig.update_layout(title="Blow-out rate with 95% confidence interval", yaxis_title="% of runs", showlegend=False)
    st.plotly_chart(fig, width='stretch', theme=None, config=_chart_config())
    d1, d2 = st.columns(2)
    with d1:
        fig = themed_figure(theme, height=320)
        for m in mc.modes:
            fig.add_trace(go.Box(y=mc.stats[m].homes_dark, name=m.label, marker_color=sev[m], boxpoints=False, line=dict(width=1.2)))
        fig.update_layout(title="Homes dark per restoration", yaxis_title="homes", showlegend=False)
        st.plotly_chart(fig, width='stretch', theme=None, config=_chart_config())
    with d2:
        fig = themed_figure(theme, height=320)
        for m in mc.modes:
            fig.add_trace(go.Box(y=mc.stats[m].peak_pu, name=m.label, marker_color=sev[m], boxpoints=False, line=dict(width=1.2)))
        fig.add_hline(y=1.0, line=dict(color=sem["muted"], width=1, dash="dot"))
        fig.update_layout(title="Peak load vs rating", yaxis_title="x rating", showlegend=False)
        st.plotly_chart(fig, width='stretch', theme=None, config=_chart_config())
    _back_to_top()


def _df_to_markdown(df):
    cols = list(df.columns)
    head = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    body = ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join([head, sep, *body])


def _headline_dataframe(mc):
    rows = []
    for m in mc.modes:
        s = mc.stats[m]
        rows.append({"Mode": m.label, "Blow-outs": f"{s.blowout_runs}/{s.n_runs}",
                     "Rate": f"{s.blowout_runs / s.n_runs * 100:.1f}%",
                     "95% CI": f"[{s.blowout_ci.low*100:.1f}, {s.blowout_ci.high*100:.1f}]%",
                     "Homes dark": f"{s.mean_homes_dark:.1f}", "Peak x rating": f"{s.mean_peak_pu:.2f}",
                     "Min >32 C": f"{s.mean_minutes_above_32:.1f}", "Ageing (h)": f"{s.mean_ageing_hours:.2f}"})
    return pd.DataFrame(rows)


def _config_text(config):
    return "\n".join([
        f"seed              {config.seed}", f"mc_runs           {config.mc_runs}",
        f"homes             {config.homes}", f"ac_penetration    {config.ac_penetration*100:.0f}%",
        f"vulnerable        {config.vulnerable_fraction*100:.0f}%", f"nameplate_kva     {config.nameplate_kva:.0f}",
        f"fuse_current_a    {config.fuse_current_a:.0f} (x{config.fuse_tightness:.2f} rated)",
        f"outage_minutes    {config.outage_minutes}", f"peak_ambient_c    {config.peak_ambient_c:.0f}",
        f"config_hash       {_config_hash(config)}"])


def _tab_results(active, theme):
    mc = active["mc"]; config = active["config"]
    df = _headline_dataframe(mc)
    st.markdown("#### Headline comparison (live engine)")
    st.table(df)
    st.markdown("#### Statistical tests (two-proportion, blow-out rate)")
    for tt in mc.pairwise_tests:
        verdict = "significant" if tt.p_value < 0.05 else "not significant at 0.05"
        st.markdown(f'<span class="pacer-mono">{tt.label_a} vs {tt.label_b}: {tt.prop_a*100:.1f}% vs '
                    f'{tt.prop_b*100:.1f}%, z = {tt.z:+.3f}, p = {tt.p_value:.3g}</span> &mdash; {verdict}',
                    unsafe_allow_html=True)
    st.markdown("#### Reproducibility")
    st.markdown(f'<span class="pacer-chip accent">deterministic</span> <span class="pacer-chip">seed {config.seed}</span> '
                f'<span class="pacer-chip">config {_config_hash(config)}</span> '
                f'<span class="pacer-chip">{mc.n_runs} runs/mode</span>', unsafe_allow_html=True)
    st.caption("Same seed + same configuration reproduce these figures byte-for-byte.")
    with st.expander("Project deck -- published scenario matrix (reference)"):
        deck = pd.DataFrame(DECK_SCENARIOS, columns=["Scenario", "Today", "PACER", "PACER + Beacon"])
        st.table(deck)
        st.caption("These are the project deck's published figures (slide 9). This app's live engine "
                   "reproduces the baseline exactly (200/200) and gives PACER / PACER+Beacon in the same "
                   "order; it does not reproduce the Beacon reaching <=1 (see the honest note in the README). "
                   "The published 200/25/1 were used as a sanity check, never as a fit target.")
    c1, c2 = st.columns(2)
    with c1:
        st.caption("Results table (Markdown) -- use the copy button")
        st.code(_df_to_markdown(df), language="markdown")
        st.download_button("Download CSV", df.to_csv(index=False).encode(),
                           file_name=f"pacer_results_seed{config.seed}.csv", mime="text/csv")
    with c2:
        st.caption("Scenario configuration -- use the copy button")
        st.code(_config_text(config), language="text")
    _back_to_top()


def _tab_methodology(theme):
    st.markdown("#### How PACER-Sim works")
    st.markdown("PACER-Sim advances one overloaded LV distribution transformer serving ~200 homes minute by "
                "minute through warm-up, a load-shedding outage, and recovery. Three controller modes are "
                "compared on identical scenarios. Every number shown is computed by a run performed here.")
    with st.expander("The seven PACER rules"):
        st.markdown(
            "1. **Outage timer** -- ignore supply blips under 60 s.\n"
            "2. **Random wait** -- window = min(2 + 8 x outage_hours, 25) min; uniform draw.\n"
            "3. **Soft start** -- cap ramps from the per-appliance value (inverter AC 55%, chargers 30%, fixed AC 55%) to 100% over 30 min.\n"
            "4. **Stress sensing** -- (learned normal V - present V) / self-measured impedance; relative, never absolute.\n"
            "5. **Back-off** -- AC x0.75 (floor 0.35); charger x0.5 (floor 0); latch 6-12 min.\n"
            "6. **Stepped return** -- small random additive upward steps; no rebound.\n"
            "7. **Heat-dose floor (always wins)** -- above 32 C, start 55% and add 10 points every 5 min (20 for vulnerable) to 100%.")
        st.markdown("Rails: minimum off-time 3 min; at most 6 starts/hour; no command can switch a load on; any fault -> pass-through.")
    with st.expander("Standards and models"):
        st.markdown(
            "- **Transformer thermal:** IEC 60076-7 top-oil + hot-spot at 1-min steps, with insulation ageing "
            "V = 2^((hot-spot - 98)/6). Swappable interface; a second conforming implementation (IEEE C57.91) is exercised by the tests.\n"
            "- **Fuse:** first-order element-heating surrogate for the fuse's I2t curve; never melts at rated, blows at 100% fuse-heat.\n"
            "- **Electrical:** radial LV feeder with per-home series impedance; aggregate load produces each home's voltage sag.\n"
            "- **Rooms:** two-node (air + mass) thermal model driven by a diurnal ambient.\n"
            "- **Statistics:** Clopper-Pearson intervals and a pooled two-proportion z-test between modes.")
    with st.expander("Assumptions"):
        st.markdown(
            "- Appliance penetrations and ratings are typical for an Indian LV network; not every home has every appliance.\n"
            "- The transformer runs near its rating under normal diversified load (an overloaded unit).\n"
            "- Phase assignment is independent per home, giving realistic phase imbalance.\n"
            "- Voltages use a resistive LV feeder approximation; sensing lags action by one minute.")
    with st.expander("Limitations"):
        st.markdown(
            "- One-minute resolution averages out sub-minute transients such as motor inrush.\n"
            "- A single transformer is modelled; upstream (HV) dynamics are summarised by a source impedance.\n"
            "- The published 200/25/1 figures are a sanity check, not a fit target; results are reported honestly (see README).\n"
            "- In this engine the Beacon shows no statistically significant benefit over PACER-only: PACER's local "
            "throttling already clears the fuse in cool conditions, and under heat the health-first Rule 7 overrides the Beacon.\n"
            "- Rule 4's voltage learner keeps per-time-of-day bins, but a single simulated day only trains the afternoon "
            "bins; the evening recovery uses the learned all-day normal.")


# ===========================================================================
# MAIN
# ===========================================================================
# ===========================================================================
# SIMULATOR -- nine-view instrument panel
# ===========================================================================
_KPI_KIND = {"baseline": "danger", "pacer": "caution", "pacer_beacon": "ok"}
_FUSE_MELT_PU = 1.45  # fusing factor: per-phase load (vs rating) that melts a tight fuse


def _mode_trials(config: Config) -> dict[str, TrialResult]:
    return _compute_modes(config, int(st.session_state.sim_trial))


def _overlay(theme, trials, gety, title, ytitle, height=320, hlines=None):
    sem = semantic(theme)
    mcl = _mode_colors(theme)
    ref = trials["baseline"]
    t = _time_axis(ref)
    fig = themed_figure(theme, height=height)
    for mv in _MODE_ORDER:
        fig.add_trace(go.Scatter(x=t, y=gety(trials[mv]), mode="lines", name=_MODE_LABEL[mv],
                                 line=dict(color=mcl[mv], width=1.8)))
    for (y, lab, col) in (hlines or []):
        fig.add_hline(y=y, line=dict(color=col, width=1, dash="dot"), annotation_text=lab,
                      annotation_position="top left", annotation_font=dict(color=col, size=10))
    x0 = ref.outage_start - ref.restore_minute
    fig.add_vrect(x0=x0, x1=0, fillcolor=sem["outage"], line_width=0, layer="below")
    fig.add_vline(x=0, line=dict(color=sem["muted"], width=1, dash="dot"))
    fig.update_layout(title=title, yaxis_title=ytitle, xaxis_title="minutes from restoration")
    return fig


def _blowbar(mc, theme, height=300):
    sem = semantic(theme)
    mcl = _mode_colors(theme)
    labels = [_MODE_LABEL[mv] for mv in _MODE_ORDER]
    rates, lo, hi = [], [], []
    for mv in _MODE_ORDER:
        s = mc.stats[ControllerMode(mv)]
        rates.append(s.blowout_runs / s.n_runs * 100)
        lo.append(s.blowout_ci.low * 100)
        hi.append(s.blowout_ci.high * 100)
    fig = themed_figure(theme, height=height)
    fig.add_trace(go.Bar(x=labels, y=rates, marker_color=[mcl[mv] for mv in _MODE_ORDER], width=0.5,
                         error_y=dict(type="data", symmetric=False, array=[h - r for h, r in zip(hi, rates)],
                                      arrayminus=[r - l for l, r in zip(lo, rates)], color=sem["muted"], thickness=1)))
    fig.update_layout(title="Fuse blow-out rate (95% CI)", yaxis_title="% of runs", showlegend=False)
    return fig


def _mode_bar(theme, valuef, title, ytitle, height=300):
    mcl = _mode_colors(theme)
    labels = [_MODE_LABEL[mv] for mv in _MODE_ORDER]
    fig = themed_figure(theme, height=height)
    fig.add_trace(go.Bar(x=labels, y=[valuef(mv) for mv in _MODE_ORDER],
                         marker_color=[mcl[mv] for mv in _MODE_ORDER], width=0.5))
    fig.update_layout(title=title, yaxis_title=ytitle, showlegend=False)
    return fig


def _sim_overview(active, theme):
    mc = active["mc"]
    config = active["config"]
    _kicker("Command centre - one scenario, three controllers, head to head")
    _stat_tiles([(f"{mc.stats[ControllerMode(mv)].blowout_runs / mc.stats[ControllerMode(mv)].n_runs * 100:.1f}%",
                  f"{_MODE_LABEL[mv]} fuse blow-outs ({mc.stats[ControllerMode(mv)].blowout_runs}/{mc.n_runs})",
                  _KPI_KIND[mv]) for mv in _MODE_ORDER])
    b = mc.stats[ControllerMode.BASELINE]
    be = mc.stats[ControllerMode.PACER_BEACON]
    _stat_tiles([
        (f"{b.mean_homes_dark - be.mean_homes_dark:.0f}", "homes kept online per restoration (Baseline - Beacon)", "ok"),
        (f"{b.mean_peak_pu:.2f}x -> {be.mean_peak_pu:.2f}x", "peak load, Baseline -> Beacon", "ok"),
        (f"{mc.n_runs}", "Monte Carlo trials per mode", "accent"),
    ])
    c1, c2 = st.columns([5, 6])
    with c1:
        st.plotly_chart(_blowbar(mc, theme), width='stretch', theme=None, config=_chart_config())
    with c2:
        trials = _mode_trials(config)
        sem = semantic(theme)
        st.plotly_chart(_overlay(theme, trials, lambda tr: tr.phase_load_pu.max(axis=1),
                                 "Worst-phase load, one restoration", "x rating",
                                 hlines=[(1.0, "rating", sem["muted"]), (_FUSE_MELT_PU, "fuse melts", sem["danger"])]),
                        width='stretch', theme=None, config=_chart_config())
    st.caption("Baseline restarts in lockstep (~2x). PACER staggers and softens the surge; the Beacon adds a "
               "per-phase fuse ceiling. Every view below dissects the same scenario.")
    _back_to_top()


def _sim_structure(active, theme):
    s = active["structure"]
    sem = semantic(theme)
    _kicker("Structure - the network this run simulates")
    _stat_tiles([
        (f"{s['n_homes']}", "homes on the transformer", "accent"),
        (f"{s['n_devices']}", "controllable devices", "accent"),
        (f"{s['n_ac_homes']}", "air-conditioned homes", "accent"),
        (f"{s['n_vulnerable']}", "registered-vulnerable homes", "caution"),
    ])
    _svg(diagrams.feeder_topology())
    c1, c2 = st.columns(2)
    with c1:
        fig = themed_figure(theme, height=300)
        fig.add_trace(go.Bar(x=s["appliance_labels"], y=s["kind_counts"], marker_color=sem["accent"]))
        fig.update_layout(title="Device population by type", yaxis_title="count", showlegend=False)
        st.plotly_chart(fig, width='stretch', theme=None, config=_chart_config())
    with c2:
        ph = [f"Phase {chr(65 + i)}" for i in range(len(s["homes_per_phase"]))]
        fig = themed_figure(theme, height=300)
        fig.add_trace(go.Bar(x=ph, y=s["homes_per_phase"], name="homes", marker_color=sem["muted"]))
        fig.add_trace(go.Bar(x=ph, y=s["connected_kw_per_phase"], name="connected kW",
                             marker_color=sem["accent"], yaxis="y2"))
        fig.update_layout(title="Per-phase split (imbalance)", barmode="group", yaxis_title="homes",
                          yaxis2=dict(title="kW", overlaying="y", side="right", showgrid=False))
        st.plotly_chart(fig, width='stretch', theme=None, config=_chart_config())
    st.caption(f"Connected load {s['total_connected_kw']:.0f} kW across {s['n_devices']} devices. Per-phase rated "
               f"current {s['rated_phase_current_a']:.0f} A; fuse {s['fuse_current_a']:.0f} A/phase. The worst phase "
               "carries more than the others -- the imbalance the Beacon targets.")
    _back_to_top()


def _sim_environment(active, theme):
    config = active["config"]
    mc = active["mc"]
    trials = _mode_trials(config)
    sem = semantic(theme)
    mcl = _mode_colors(theme)
    ref = trials["baseline"]
    _kicker("Environment - heat, rooms and transformer thermals")
    c1, c2 = st.columns(2)
    with c1:
        t = _time_axis(ref)
        fig = themed_figure(theme, height=320)
        fig.add_trace(go.Scatter(x=t, y=ref.ambient_c, name="Ambient", line=dict(color=sem["muted"], width=1.4, dash="dot")))
        for mv in _MODE_ORDER:
            fig.add_trace(go.Scatter(x=t, y=trials[mv].mean_indoor_c, name=_MODE_LABEL[mv], line=dict(color=mcl[mv], width=1.6)))
        fig.add_hline(y=32, line=dict(color=sem["danger"], width=1, dash="dot"), annotation_text="32 C heat line",
                      annotation_position="top left", annotation_font=dict(color=sem["danger"], size=10))
        x0 = ref.outage_start - ref.restore_minute
        fig.add_vrect(x0=x0, x1=0, fillcolor=sem["outage"], line_width=0, layer="below")
        fig.add_vline(x=0, line=dict(color=sem["muted"], width=1, dash="dot"))
        fig.update_layout(title="Mean indoor temperature", yaxis_title="C", xaxis_title="minutes from restoration")
        st.plotly_chart(fig, width='stretch', theme=None, config=_chart_config())
    with c2:
        st.plotly_chart(_overlay(theme, trials, lambda tr: tr.hot_spot_c, "Transformer hot-spot (IEC 60076-7)", "C",
                                 hlines=[(98, "98 C rated", sem["caution"])]), width='stretch', theme=None, config=_chart_config())
    c3, c4 = st.columns(2)
    with c3:
        st.plotly_chart(_mode_bar(theme, lambda mv: mc.stats[ControllerMode(mv)].mean_minutes_above_32,
                                  "Minutes above 32 C per AC home", "minutes"), width='stretch', theme=None, config=_chart_config())
    with c4:
        st.plotly_chart(_mode_bar(theme, lambda mv: mc.stats[ControllerMode(mv)].mean_ageing_hours,
                                  "Insulation ageing per restoration", "equivalent hours"), width='stretch', theme=None, config=_chart_config())
    st.caption("A hot room drives Rule 7: a cooling floor that always wins, so overheated homes reach full power "
               "within ~25 minutes even while the controller paces the rest.")
    _back_to_top()


def _sim_sensing(active, theme):
    config = active["config"]
    trials = _mode_trials(config)
    sem = semantic(theme)
    pac = trials["pacer"]
    _kicker("Sensing - Rule 4: grid stress from voltage, relative to a learned normal")
    _stat_tiles([
        (f"{pac.learned_normal_v_mean:.0f} V", "learned normal voltage (per time-of-day)", "accent"),
        (f"{pac.z_estimate_median * 1000:.0f} m-ohm", "median self-measured line impedance", "accent"),
        (f"{pac.stress_signal.max():.0f} A", "peak sensed stress (PACER)", "caution"),
    ])
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(_overlay(theme, trials, lambda tr: tr.rep_voltage, "Representative home voltage", "V (L-N)",
                                 hlines=[(config.v_ln, "nominal", sem["muted"])]), width='stretch', theme=None, config=_chart_config())
    with c2:
        st.plotly_chart(_overlay(theme, trials, lambda tr: tr.stress_signal,
                                 "Stress the controller senses", "A (impedance-normalised)"),
                        width='stretch', theme=None, config=_chart_config())
    st.plotly_chart(_overlay(theme, trials, lambda tr: tr.min_voltage, "Weakest-home voltage (worst sag)", "V (L-N)",
                             hlines=[(config.v_ln, "nominal", sem["muted"]), (config.v_ln * 0.9, "-10%", sem["caution"])]),
                    width='stretch', theme=None, config=_chart_config())
    st.caption("Baseline has no sensing (flat). PACER turns the voltage sag into an impedance-normalised stress, so "
               "it works on weak feeders sagging to ~190 V, and backs off when stress runs high.")
    _back_to_top()


def _sim_detection(active, theme):
    config = active["config"]
    trials = _mode_trials(config)
    sem = semantic(theme)
    cols = phase_colors(theme)
    _kicker("Detection - per-phase fuse heating and the blow-out")
    st.plotly_chart(_overlay(theme, trials, lambda tr: tr.phase_heat_pct.max(axis=1),
                             "Worst-phase fuse-heat, three controllers", "% of melting",
                             hlines=[(100, "melt", sem["danger"]), (72, "beacon ceiling (85% level)", sem["caution"])]),
                    width='stretch', theme=None, config=_chart_config())
    sel = st.selectbox("Per-phase detail for mode", [_MODE_LABEL[mv] for mv in _MODE_ORDER], key="det_mode")
    mv = {v: k for k, v in _MODE_LABEL.items()}[sel]
    tr = trials[mv]
    t = _time_axis(tr)
    c1, c2 = st.columns(2)
    with c1:
        fig = themed_figure(theme, height=300)
        for ph in range(config.phases):
            fig.add_trace(go.Scatter(x=t, y=tr.phase_heat_pct[:, ph], name=f"Phase {chr(65 + ph)}", line=dict(color=cols[ph], width=1.4)))
        fig.add_hline(y=100, line=dict(color=sem["danger"], width=1, dash="dash"))
        _add_event_markers(fig, tr, theme)
        fig.update_layout(title=f"Per-phase fuse-heat ({sel})", yaxis_title="% of melting", xaxis_title="minutes from restoration")
        st.plotly_chart(fig, width='stretch', theme=None, config=_chart_config())
    with c2:
        fig = themed_figure(theme, height=300)
        for ph in range(config.phases):
            fig.add_trace(go.Scatter(x=t, y=tr.phase_load_pu[:, ph], name=f"Phase {chr(65 + ph)}", line=dict(color=cols[ph], width=1.4)))
        fig.add_hline(y=_FUSE_MELT_PU, line=dict(color=sem["danger"], width=1, dash="dot"), annotation_text="fuse melts",
                      annotation_position="top left", annotation_font=dict(color=sem["danger"], size=10))
        _add_event_markers(fig, tr, theme, mark_blow=False)
        fig.update_layout(title=f"Per-phase load ({sel})", yaxis_title="x rating", xaxis_title="minutes from restoration")
        st.plotly_chart(fig, width='stretch', theme=None, config=_chart_config())
    chips = []
    for mvv in _MODE_ORDER:
        tt = trials[mvv]
        state = f"blow at {tt.blow_minute_since_restore} min" if tt.blew else "held"
        chips.append(f'<span class="pacer-chip {"danger" if tt.blew else "ok"}">{_MODE_LABEL[mvv]}: {state}</span>')
    st.markdown(" ".join(chips), unsafe_allow_html=True)
    _back_to_top()


def _sim_assimilation(active, theme):
    mc = active["mc"]
    config = active["config"]
    mcl = _mode_colors(theme)
    _kicker(f"Assimilation - aggregating {mc.n_runs} randomised trials per mode, and sweeping conditions")
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(_blowbar(mc, theme, height=320), width='stretch', theme=None, config=_chart_config())
    with c2:
        fig = themed_figure(theme, height=320)
        for mv in _MODE_ORDER:
            fig.add_trace(go.Box(y=mc.stats[ControllerMode(mv)].homes_dark, name=_MODE_LABEL[mv],
                                 marker_color=mcl[mv], boxpoints=False, line=dict(width=1.2)))
        fig.update_layout(title="Homes dark per restoration", yaxis_title="homes", showlegend=False)
        st.plotly_chart(fig, width='stretch', theme=None, config=_chart_config())
    st.markdown("###### Statistical tests (two-proportion, blow-out rate)")
    for tt in mc.pairwise_tests:
        verdict = "significant" if tt.p_value < 0.05 else "not significant at 0.05"
        st.markdown(f'<span class="pacer-mono">{tt.label_a} vs {tt.label_b}: {tt.prop_a*100:.1f}% vs '
                    f'{tt.prop_b*100:.1f}%, z = {tt.z:+.2f}, p = {tt.p_value:.3g}</span> &mdash; {verdict}',
                    unsafe_allow_html=True)
    st.markdown("#### Sensitivity sweep")
    sc1, sc2 = st.columns([3, 1])
    var_label = sc1.selectbox("Sweep variable", list(SWEEP_VARIABLES.keys()), key="sweep_var")
    if sc2.button("Run sweep", width='stretch'):
        from dataclasses import replace
        field = SWEEP_VARIABLES[var_label]
        values = SWEEP_RANGES[field]
        base = replace(config, mc_runs=min(config.mc_runs, 40))
        holder = st.empty()
        with holder.container():
            st.markdown(f"Sweeping {var_label}: {len(values)} points x 3 modes x {base.mc_runs} runs...")
            bar = st.progress(0.0, text="Starting")
            last = {"b": -1}

            def cb(frac, msg):
                fr = min(max(frac, 0.0), 1.0)
                bk = int(fr * 100)
                if bk != last["b"]:
                    last["b"] = bk
                    bar.progress(fr, text=msg)

            sweep = run_sweep(base, field, values, progress=cb)
        holder.empty()
        st.session_state.sweep = {"var_label": var_label, "sweep": sweep}
    sw = st.session_state.sweep
    if sw and sw["var_label"] == var_label:
        sweep = sw["sweep"]
        fig = themed_figure(theme, height=340)
        for mv in _MODE_ORDER:
            m = ControllerMode(mv)
            fig.add_trace(go.Scatter(x=sweep.values, y=sweep.rate_pct[m], mode="lines+markers",
                                     name=_MODE_LABEL[mv], line=dict(color=mcl[mv], width=1.9), marker=dict(size=6)))
        fig.update_layout(title=f"Blow-out rate vs {var_label}  ({sweep.n_runs} runs/point)",
                          xaxis_title=var_label, yaxis_title="% of runs")
        st.plotly_chart(fig, width='stretch', theme=None, config=_chart_config())
    else:
        st.caption("Pick a variable and press Run sweep to trace how blow-outs respond as it changes, holding "
                   "everything else fixed -- a clean, un-rigged sensitivity curve.")
    _back_to_top()


def _sim_economics(active, theme):
    mc = active["mc"]
    config = active["config"]
    _kicker("Economics - translating THIS run into customer-hours, carbon and payback")
    ec = st.columns(3)
    restorations = ec[0].slider("Restorations per summer", 10, 80, 40, key="eco_rest")
    repair_h = ec[1].slider("Repair hours per blow-out", 1, 8, 3, key="eco_repair")
    counted = ec[2].slider("Fraction of benefit counted (%)", 20, 100, 40, key="eco_counted") / 100.0
    base = mc.stats[ControllerMode.BASELINE]

    def ch_avoided(mode):
        s = mc.stats[mode]
        base_ch = restorations * (base.blowout_runs / base.n_runs) * base.mean_homes_dark * repair_h
        mode_ch = restorations * (s.blowout_runs / s.n_runs) * s.mean_homes_dark * repair_h
        return max(0.0, base_ch - mode_ch) * counted

    pacer_ch = ch_avoided(ControllerMode.PACER)
    beacon_ch = ch_avoided(ControllerMode.PACER_BEACON)
    _stat_tiles([
        (f"{beacon_ch:,.0f}", "customer-hours of outage avoided / transformer / summer (PACER+Beacon)", "ok"),
        (f"{pacer_ch:,.0f}", "customer-hours avoided with PACER only", "ok"),
        (f"{beacon_ch / max(config.homes, 1):.1f} h", "per household per summer", "ok"),
    ])
    mcl = _mode_colors(theme)
    fig = themed_figure(theme, height=300)
    fig.add_trace(go.Bar(x=[_MODE_LABEL["pacer"], _MODE_LABEL["pacer_beacon"]], y=[pacer_ch, beacon_ch],
                         marker_color=[mcl["pacer"], mcl["pacer_beacon"]], width=0.5))
    fig.update_layout(title="Customer-hours of outage avoided per summer", yaxis_title="customer-hours", showlegend=False)
    st.plotly_chart(fig, width='stretch', theme=None, config=_chart_config())
    st.markdown("#### Programme economics (project estimates)")
    _stat_tiles([
        ("Rs 1.6-3.1 lakh", "per transformer capex + Rs 4,500-10,000 / yr", "accent"),
        ("9 mo - 5.5 yr", "DISCOM payback (central 1.8 yr); Rs 7-20 / customer-hour", "accent"),
        ("0.35-1.5 t", "CO2e avoided / transformer / yr", "ok"),
    ])
    st.caption("The live tiles are computed from THIS run's blow-out rates and homes-dark, scaled by your "
               "assumptions (it treats every restoration as this scenario; the deck's fleet average mixes "
               "severities). The programme economics are the project's published estimates.")
    _back_to_top()


def _sim_ledger(theme):
    _kicker("Ledger - every run this session, for side-by-side comparison")
    led = st.session_state.ledger
    if not led:
        st.info("Run a simulation to start the ledger.")
        _back_to_top()
        return
    df = pd.DataFrame(led)
    st.dataframe(df, width='stretch', hide_index=True)
    lc1, lc2 = st.columns([1, 4])
    lc1.download_button("Download CSV", df.to_csv(index=False).encode(), file_name="pacer_ledger.csv", mime="text/csv")
    if lc2.button("Clear ledger"):
        st.session_state.ledger = []
        st.rerun()
    st.caption("Each run is logged with its config hash and seed, so any row here reproduces byte-for-byte.")
    _back_to_top()


def _sim_provenance(active, theme):
    config = active["config"]
    mc = active["mc"]
    _kicker("Provenance - reproducibility, standards and the honest record")
    _stat_tiles([
        (f"{config.seed}", "random seed", "accent"),
        (f"{_config_hash(config)}", "configuration hash", "accent"),
        (f"{mc.n_runs}", "trials per mode", "accent"),
    ])
    st.markdown('<span class="pacer-chip accent">deterministic</span> '
                '<span class="pacer-chip ok">byte-identical on re-run</span> '
                '<span class="pacer-chip">golden-regression tested</span>', unsafe_allow_html=True)
    st.markdown("Same seed + same configuration reproduce every figure in this app byte-for-byte; a committed "
                "golden fixture and test enforce it.")
    df = _headline_dataframe(mc)
    st.markdown("###### Headline comparison (live engine)")
    st.table(df)
    with st.expander("Project deck -- published scenario matrix (reference)"):
        deck = pd.DataFrame(DECK_SCENARIOS, columns=["Scenario", "Today", "PACER", "PACER + Beacon"])
        st.table(deck)
        st.caption("The deck's published figures. This app's live engine matches the baseline exactly and gives "
                   "PACER / PACER+Beacon in the same order; it does not reproduce the Beacon reaching <=1 "
                   "(reported honestly). The 200/25/1 were a sanity check, never a fit target.")
    pc1, pc2 = st.columns(2)
    with pc1:
        st.caption("Results (Markdown) -- copy button")
        st.code(_df_to_markdown(df), language="markdown")
        st.download_button("Download CSV", df.to_csv(index=False).encode(),
                           file_name=f"pacer_results_seed{config.seed}.csv", mime="text/csv")
    with pc2:
        st.caption("Configuration -- copy button")
        st.code(_config_text(config), language="text")
    _tab_methodology(theme)
    _back_to_top()


# ===========================================================================
# MAIN
# ===========================================================================
_AREAS = ["Simulator", "Overview", "Problem & solution", "Impact & case", "Delivery", "Team & about"]
_SIM_VIEWS = [
    ("Overview", _sim_overview), ("Structure", _sim_structure), ("Environment", _sim_environment),
    ("Sensing", _sim_sensing), ("Detection", _sim_detection), ("Assimilation", _sim_assimilation),
    ("Economics", _sim_economics), ("Ledger", None), ("Provenance", _sim_provenance),
]


def main() -> None:
    _init_state()
    theme = st.session_state.theme
    st.markdown(theme_css(theme), unsafe_allow_html=True)

    sb = st.sidebar
    sb.markdown("### Navigate")
    area = sb.radio("Section", _AREAS, key="section", label_visibility="collapsed")
    sb.markdown("---")

    run_clicked = False
    if area == "Simulator":
        config, run_clicked = _sidebar_scenario(sb)
    else:
        config = st.session_state.active["config"] if st.session_state.active else Config()

    _render_header(config, theme)
    st.markdown('<span id="main-content"></span>', unsafe_allow_html=True)

    if run_clicked:
        _do_run(config)
    active = st.session_state.active

    if area == "Simulator":
        tc1, tc2 = st.columns([1, 3], vertical_alignment="bottom")
        tc1.number_input("Representative trial (scenario)", 0, 999, key="sim_trial")
        if active is not None and active["key"] != config.key():
            tc2.warning("Scenario changed since the last run -- press Run simulation to refresh.")
        tabs = st.tabs([name for name, _ in _SIM_VIEWS])
        for i, (name, fn) in enumerate(_SIM_VIEWS):
            with tabs[i]:
                if name == "Ledger":
                    _sim_ledger(theme)
                elif active is None:
                    st.info("Set up a scenario in the sidebar (or pick a preset) and press Run simulation.")
                else:
                    fn(active, theme)
    elif area == "Overview":
        _page_overview()
    elif area == "Problem & solution":
        tabs = st.tabs(["The problem", "The solution", "How it works", "Architecture & hardware"])
        with tabs[0]:
            _page_problem()
        with tabs[1]:
            _page_solution()
        with tabs[2]:
            _page_how_it_works()
        with tabs[3]:
            _page_architecture()
    elif area == "Impact & case":
        tabs = st.tabs(["Impact & assessment", "Innovation & IP", "Challenge alignment"])
        with tabs[0]:
            _page_impact()
        with tabs[1]:
            _page_innovation()
        with tabs[2]:
            _page_alignment()
    elif area == "Delivery":
        _page_delivery()
    elif area == "Team & about":
        _page_team()

    _footer(active)


if __name__ == "__main__":
    main()
