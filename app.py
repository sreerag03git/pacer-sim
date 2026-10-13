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
from engine.montecarlo import MonteCarloResult, run_monte_carlo
from engine.simulation import TrialResult, run_trial
from theme import diagrams, phase_colors, semantic, theme_css, themed_figure

APP_VERSION = "0.3.0"
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

st.set_page_config(page_title="PACER-Sim", layout="wide", initial_sidebar_state="expanded")


# ---------------------------------------------------------------------------
# Cached compute + small helpers
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False, hash_funcs={Config: lambda c: c.key()})
def _compute_trial(config: Config, mode: str, trial_index: int) -> TrialResult:
    return run_trial(config.with_mode(ControllerMode(mode)), trial_index)


def _config_hash(config: Config) -> str:
    return hashlib.sha1(repr(config.key()).encode()).hexdigest()[:8]


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
def _init_state() -> None:
    st.session_state.setdefault("theme", "light")
    st.session_state.setdefault("active", None)
    st.session_state.setdefault("confirm_reset", False)


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
                '<div class="pacer-title">PACER-Sim</div>'
                '<div class="pacer-subtitle">Phase-Aware Coordinated Energisation &amp; Recovery '
                '-- stopping the blackout after the blackout</div>',
                unsafe_allow_html=True)
        with c2:
            st.markdown(
                f'<div class="pacer-build">seed <b>{config.seed}</b> &middot; cfg <b>{_config_hash(config)}</b>'
                f'<br>build {BUILD_DATE} &middot; v{APP_VERSION}</div>', unsafe_allow_html=True)
        with c3:
            label = "Switch to dark" if theme == "light" else "Switch to light"
            st.button(label, on_click=_toggle_theme, use_container_width=True, key="theme_btn")


def _footer(active: dict | None) -> None:
    ran = active["ts"].strftime("%Y-%m-%d %H:%M:%S") if active else "no simulation run yet"
    st.markdown(
        f'<div class="pacer-foot">PACER-Sim v{APP_VERSION} &middot; build {BUILD_DATE} &middot; '
        f'Team PACERS &middot; Challenge 03 (Grid Reliability) &middot; last simulation {ran} &middot; '
        f'simulated results, openly reproducible.</div>', unsafe_allow_html=True)


# ===========================================================================
# SHOWCASE PAGES
# ===========================================================================
def _page_overview() -> None:
    _kicker("Challenge 03 - Grid Reliability & Renewable Intermittency",
            "In the evening, as rooftop solar fades, Indian DISCOMs cut power in scheduled blocks. "
            "The damage is done at restoration: every AC, inverter charger, water pump and e-rickshaw "
            "charger restarts within the same few minutes -- because almost every stabiliser waits the "
            "same fixed 3 minutes -- hitting the transformer at about twice its rating. The fuse blows, "
            "and a 2-hour cut becomes a 5-hour blackout for the whole street. PACER puts a small, "
            "communication-free protocol inside the devices that cause the surge, so they stagger and "
            "soften their own restart; an optional per-transformer Beacon makes it fuse-aware.")
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
    st.plotly_chart(_impact_bar(st.session_state.theme), use_container_width=True,
                    config={"displaylogo": False, "displayModeBar": False})
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
def _sidebar_scenario(sb) -> tuple[Config, bool]:
    sb.markdown("#### Scenario")
    mode_label = sb.selectbox("Controller mode", [m.label for m in ControllerMode], index=0,
                              help="Sets only the mode shown first on the Simulation tab; that tab's own Mode "
                                   "selector overrides it, and Monte Carlo and Results always compare all three.")
    mode = {m.label: m for m in ControllerMode}[mode_label]
    sb.markdown("###### Population")
    homes = sb.number_input("Homes on the transformer", 50, 500, 200, 10)
    ac = sb.slider("AC penetration (%)", 0, 100, 60)
    vuln = sb.slider("Registered-vulnerable homes (%)", 0, 30, 8)
    sb.markdown("###### Transformer and fuse")
    nameplate = sb.number_input("Nameplate rating (kVA)", 50.0, 400.0, 160.0, 10.0)
    tightness = sb.slider("Fuse rating (x rated current)", 0.80, 1.40, 1.00, 0.05,
                          help="1.0 = a tight fuse rated at the transformer's own rated current.")
    rated_i = (nameplate * 1000.0 / 3.0) / 240.0
    sb.caption(f"Fuse: {tightness * rated_i:.0f} A/phase (rated current {rated_i:.0f} A/phase)")
    sb.markdown("###### Event and weather")
    outage = sb.slider("Outage duration (min)", 0, 360, 120, 10)
    preset_label = sb.selectbox("Ambient", ["Hot (42 C)", "Mild (34 C)", "Heatwave (46 C)", "Custom"], index=0)
    custom_peak = None
    heatwave = HeatwavePreset.HOT
    if preset_label.startswith("Mild"):
        heatwave = HeatwavePreset.MILD
    elif preset_label.startswith("Heatwave"):
        heatwave = HeatwavePreset.HEATWAVE
    elif preset_label.startswith("Custom"):
        custom_peak = float(sb.slider("Peak ambient (C)", 28, 48, 42))
    sb.markdown("###### Monte Carlo")
    runs = sb.slider("Trials per mode", 10, 500, 200, 10)
    seed = sb.number_input("Random seed", 0, 1_000_000, 7, 1)

    config = Config(mode=mode, homes=int(homes), ac_penetration=ac / 100.0,
                    vulnerable_fraction=vuln / 100.0, nameplate_kva=float(nameplate),
                    fuse_tightness=float(tightness), outage_minutes=int(outage), heatwave=heatwave,
                    ambient_peak_c=custom_peak, mc_runs=int(runs), seed=int(seed))
    problems = config.validate()
    if problems:
        for p in problems:
            sb.error(p)
    else:
        sb.markdown(f'<span class="pacer-chip ok">configuration valid</span> '
                    f'<span class="pacer-chip accent">deterministic &middot; seed {config.seed}</span>',
                    unsafe_allow_html=True)
    run_clicked = sb.button("Run analysis", type="primary", use_container_width=True, disabled=bool(problems))
    sb.markdown("---")
    if not st.session_state.confirm_reset:
        if sb.button("Reset results", use_container_width=True):
            st.session_state.confirm_reset = True
            st.rerun()
    else:
        sb.warning("Clear the current run and cached results?")
        cc1, cc2 = sb.columns(2)
        if cc1.button("Confirm", use_container_width=True):
            st.session_state.active = None
            _compute_trial.clear()
            st.session_state.confirm_reset = False
            st.rerun()
        if cc2.button("Cancel", use_container_width=True):
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
    st.session_state.active = {"key": config.key(), "config": config, "mc": mc, "ts": _dt.datetime.now()}


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
    r1c1.plotly_chart(_fig_load(tr, config, theme), use_container_width=True, config=_chart_config())
    r1c2.plotly_chart(_fig_fuse(tr, config, theme), use_container_width=True, config=_chart_config())
    r2c1, r2c2 = st.columns(2)
    r2c1.plotly_chart(_fig_hotspot(tr, config, theme), use_container_width=True, config=_chart_config())
    r2c2.plotly_chart(_fig_voltage(tr, config, theme), use_container_width=True, config=_chart_config())
    st.plotly_chart(_fig_online(tr, config, theme), use_container_width=True, config=_chart_config())
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
    st.plotly_chart(fig, use_container_width=True, config=_chart_config())
    d1, d2 = st.columns(2)
    with d1:
        fig = themed_figure(theme, height=320)
        for m in mc.modes:
            fig.add_trace(go.Box(y=mc.stats[m].homes_dark, name=m.label, marker_color=sev[m], boxpoints=False, line=dict(width=1.2)))
        fig.update_layout(title="Homes dark per restoration", yaxis_title="homes", showlegend=False)
        st.plotly_chart(fig, use_container_width=True, config=_chart_config())
    with d2:
        fig = themed_figure(theme, height=320)
        for m in mc.modes:
            fig.add_trace(go.Box(y=mc.stats[m].peak_pu, name=m.label, marker_color=sev[m], boxpoints=False, line=dict(width=1.2)))
        fig.add_hline(y=1.0, line=dict(color=sem["muted"], width=1, dash="dot"))
        fig.update_layout(title="Peak load vs rating", yaxis_title="x rating", showlegend=False)
        st.plotly_chart(fig, use_container_width=True, config=_chart_config())
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
_SIM_AREA = "Simulator"
_AREAS = ["Overview", "Problem & solution", _SIM_AREA, "Impact & case", "Delivery", "Team & about"]


def main() -> None:
    _init_state()
    theme = st.session_state.theme
    st.markdown(theme_css(theme), unsafe_allow_html=True)

    sb = st.sidebar
    sb.markdown("### Navigate")
    area = sb.radio("Section", _AREAS, label_visibility="collapsed")
    sb.markdown("---")

    run_clicked = False
    if area == _SIM_AREA:
        config, run_clicked = _sidebar_scenario(sb)
    else:
        config = st.session_state.active["config"] if st.session_state.active else Config()

    _render_header(config, theme)
    st.markdown('<span id="main-content"></span>', unsafe_allow_html=True)

    if run_clicked:
        _do_run(config)
    active = st.session_state.active

    if area == "Overview":
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
    elif area == _SIM_AREA:
        if active is not None and active["key"] != config.key():
            st.warning("The scenario has changed since the last run. Press Run analysis to update the results below.")
        tabs = st.tabs(["Simulation", "Monte Carlo", "Results and verification"])
        for i, fn in enumerate((_tab_simulation, _tab_montecarlo, _tab_results)):
            with tabs[i]:
                if active is None:
                    st.info("Configure the scenario in the sidebar and press Run analysis.")
                else:
                    fn(active, theme)
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
