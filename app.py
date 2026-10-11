"""PACER-Sim -- Streamlit UI.

This module is UI only. All physics and statistics live in the (Streamlit-free)
``engine`` package; this file drives the engine and presents its results. The
theme system lives in ``theme``.

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
from engine.stats import clopper_pearson
from theme import phase_colors, semantic, theme_css, themed_figure

APP_VERSION = "0.1.0"
BUILD_DATE = "2026-10-08"

st.set_page_config(
    page_title="PACER-Sim",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Cached compute (single trial). Monte Carlo is run explicitly with a progress
# bar, so it is cached by hand in session_state rather than via cache_data.
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False, hash_funcs={Config: lambda c: c.key()})
def _compute_trial(config: Config, mode: str, trial_index: int) -> TrialResult:
    return run_trial(config.with_mode(ControllerMode(mode)), trial_index)


def _config_hash(config: Config) -> str:
    return hashlib.sha1(repr(config.key()).encode()).hexdigest()[:8]


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
def _init_state() -> None:
    st.session_state.setdefault("theme", "light")
    st.session_state.setdefault("active", None)  # dict: key, config, mc, ts
    st.session_state.setdefault("confirm_reset", False)


def _toggle_theme() -> None:
    st.session_state.theme = "dark" if st.session_state.theme == "light" else "light"


# ---------------------------------------------------------------------------
# Header (sticky) + skip link
# ---------------------------------------------------------------------------
def _render_header(config: Config, theme: str) -> None:
    st.markdown(
        '<a class="pacer-skip" href="#main-content">Skip to content</a>'
        '<span id="top"></span>',
        unsafe_allow_html=True,
    )
    with st.container():
        # Marker makes this container the sticky header (see theme/css.py).
        st.markdown('<span class="pacer-header-marker"></span>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns([6, 3, 2], vertical_alignment="center")
        with c1:
            st.markdown(
                '<div class="pacer-title">PACER-Sim</div>'
                '<div class="pacer-subtitle">Phase-Aware Coordinated Energisation &amp; Recovery '
                '-- distribution-transformer restart simulation</div>',
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                f'<div class="pacer-build">seed <b>{config.seed}</b> &middot; '
                f'cfg <b>{_config_hash(config)}</b><br>build {BUILD_DATE} &middot; v{APP_VERSION}</div>',
                unsafe_allow_html=True,
            )
        with c3:
            label = "Switch to dark" if theme == "light" else "Switch to light"
            st.button(label, on_click=_toggle_theme, use_container_width=True, key="theme_btn")


# ---------------------------------------------------------------------------
# Sidebar -> Config + run intent
# ---------------------------------------------------------------------------
def _sidebar() -> tuple[Config, bool]:
    sb = st.sidebar
    sb.markdown("### Scenario")

    mode_label = sb.selectbox(
        "Controller mode",
        [m.label for m in ControllerMode],
        index=0,
        help="The controller used for the single-trial Simulation tab. Monte Carlo and Results always compare all three.",
    )
    mode = {m.label: m for m in ControllerMode}[mode_label]

    sb.markdown("#### Population")
    homes = sb.number_input("Homes on the transformer", min_value=50, max_value=500, value=200, step=10)
    ac = sb.slider("AC penetration (%)", 0, 100, 60)
    vuln = sb.slider("Registered-vulnerable homes (%)", 0, 30, 8)

    sb.markdown("#### Transformer and fuse")
    nameplate = sb.number_input("Nameplate rating (kVA)", min_value=50.0, max_value=400.0, value=160.0, step=10.0)
    tightness = sb.slider(
        "Fuse rating (x rated current)", 0.80, 1.40, 1.00, 0.05,
        help="1.0 = a tight fuse rated at the transformer's own rated current.",
    )
    rated_i = (nameplate * 1000.0 / 3.0) / 240.0
    sb.caption(f"Fuse: {tightness * rated_i:.0f} A/phase (rated current {rated_i:.0f} A/phase)")

    sb.markdown("#### Event and weather")
    outage = sb.slider("Outage duration (min)", 0, 360, 120, 10)
    preset_label = sb.selectbox(
        "Ambient",
        ["Hot (42 C)", "Mild (34 C)", "Heatwave (46 C)", "Custom"],
        index=0,
    )
    custom_peak = None
    heatwave = HeatwavePreset.HOT
    if preset_label.startswith("Hot"):
        heatwave = HeatwavePreset.HOT
    elif preset_label.startswith("Mild"):
        heatwave = HeatwavePreset.MILD
    elif preset_label.startswith("Heatwave"):
        heatwave = HeatwavePreset.HEATWAVE
    else:
        custom_peak = float(sb.slider("Peak ambient (C)", 28, 48, 42))

    sb.markdown("#### Monte Carlo")
    runs = sb.slider("Trials per mode", 10, 500, 200, 10)
    seed = sb.number_input("Random seed", min_value=0, max_value=1_000_000, value=7, step=1)

    config = Config(
        mode=mode,
        homes=int(homes),
        ac_penetration=ac / 100.0,
        vulnerable_fraction=vuln / 100.0,
        nameplate_kva=float(nameplate),
        fuse_tightness=float(tightness),
        outage_minutes=int(outage),
        heatwave=heatwave,
        ambient_peak_c=custom_peak,
        mc_runs=int(runs),
        seed=int(seed),
    )

    # Validation with clear success / error states.
    problems = config.validate()
    if problems:
        for p in problems:
            sb.error(p)
    else:
        sb.markdown(
            f'<span class="pacer-chip ok">configuration valid</span> '
            f'<span class="pacer-chip accent">deterministic &middot; seed {config.seed}</span>',
            unsafe_allow_html=True,
        )

    run_clicked = sb.button(
        "Run analysis", type="primary", use_container_width=True, disabled=bool(problems)
    )

    # Reset behind a confirmation step.
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


# ---------------------------------------------------------------------------
# Run (with a real progress bar)
# ---------------------------------------------------------------------------
def _do_run(config: Config) -> None:
    holder = st.empty()
    with holder.container():
        st.markdown("Running Monte Carlo across all three modes...")
        bar = st.progress(0.0, text="Starting")

        # Throttle UI updates: pushing a websocket frame on every trial dominates
        # wall-clock. Update only when the progress crosses a new half-percent.
        last = {"bucket": -1}

        def cb(frac: float, msg: str) -> None:
            frac = min(max(frac, 0.0), 1.0)
            bucket = int(frac * 200)  # 0.5% resolution
            if bucket != last["bucket"]:
                last["bucket"] = bucket
                bar.progress(frac, text=msg)

        mc = run_monte_carlo(config, progress=cb)
    holder.empty()
    st.session_state.active = {
        "key": config.key(),
        "config": config,
        "mc": mc,
        "ts": _dt.datetime.now(),
    }


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------
def _chart_config() -> dict:
    return {"displaylogo": False, "displayModeBar": False, "responsive": True}


def _add_event_markers(fig: go.Figure, tr: TrialResult, theme: str, mark_blow: bool = True) -> None:
    sem = semantic(theme)
    # outage band (relative minutes: restoration = 0)
    x0 = tr.outage_start - tr.restore_minute
    fig.add_vrect(x0=x0, x1=0, fillcolor=sem["outage"], line_width=0, layer="below")
    fig.add_vline(x=0, line=dict(color=sem["muted"], width=1, dash="dot"))
    if mark_blow and tr.blew and tr.blow_minute_since_restore >= 0:
        fig.add_vline(
            x=tr.blow_minute_since_restore,
            line=dict(color=sem["danger"], width=1.5, dash="dash"),
        )
        fig.add_annotation(
            x=tr.blow_minute_since_restore, yref="paper", y=1.0,
            text="fuse blow", showarrow=False, font=dict(color=sem["danger"], size=10),
            xanchor="left", bgcolor=sem["surface"],
        )


def _time_axis(tr: TrialResult) -> np.ndarray:
    return np.arange(tr.total_minutes) - tr.restore_minute


def _fig_load(tr: TrialResult, config: Config, theme: str) -> go.Figure:
    sem = semantic(theme)
    t = _time_axis(tr)
    fig = themed_figure(theme, height=300)
    fig.add_trace(go.Scatter(x=t, y=tr.load_pu, mode="lines", name="Load",
                             line=dict(color=sem["accent"], width=1.6)))
    fig.add_hline(y=1.0, line=dict(color=sem["muted"], width=1, dash="dot"),
                  annotation_text="rating", annotation_position="top left",
                  annotation_font=dict(color=sem["muted"], size=10))
    _add_event_markers(fig, tr, theme)
    fig.update_layout(title="Aggregate load vs rating", yaxis_title="x rating", xaxis_title="minutes from restoration")
    return fig


def _fig_fuse(tr: TrialResult, config: Config, theme: str) -> go.Figure:
    sem = semantic(theme)
    cols = phase_colors(theme)
    t = _time_axis(tr)
    fig = themed_figure(theme, height=300)
    for ph in range(config.phases):
        fig.add_trace(go.Scatter(x=t, y=tr.phase_heat_pct[:, ph], mode="lines",
                                 name=f"Phase {chr(65 + ph)}", line=dict(color=cols[ph], width=1.4)))
    fig.add_hline(y=100.0, line=dict(color=sem["danger"], width=1, dash="dash"),
                  annotation_text="melt", annotation_position="top left",
                  annotation_font=dict(color=sem["danger"], size=10))
    _add_event_markers(fig, tr, theme)
    fig.update_layout(title="Per-phase fuse-heat", yaxis_title="% of melting", xaxis_title="minutes from restoration")
    return fig


def _fig_hotspot(tr: TrialResult, config: Config, theme: str) -> go.Figure:
    sem = semantic(theme)
    t = _time_axis(tr)
    fig = themed_figure(theme, height=300)
    fig.add_trace(go.Scatter(x=t, y=tr.hot_spot_c, mode="lines", name="Hot-spot",
                             line=dict(color=sem["accent"], width=1.6)))
    fig.add_trace(go.Scatter(x=t, y=tr.top_oil_c, mode="lines", name="Top-oil",
                             line=dict(color=sem["muted"], width=1.2, dash="dot")))
    fig.add_hline(y=98.0, line=dict(color=sem["caution"], width=1, dash="dot"),
                  annotation_text="98 C rated", annotation_position="top left",
                  annotation_font=dict(color=sem["caution"], size=10))
    _add_event_markers(fig, tr, theme, mark_blow=False)
    fig.update_layout(title="Transformer hot-spot (IEC 60076-7)", yaxis_title="C", xaxis_title="minutes from restoration")
    return fig


def _fig_voltage(tr: TrialResult, config: Config, theme: str) -> go.Figure:
    sem = semantic(theme)
    t = _time_axis(tr)
    fig = themed_figure(theme, height=300)
    fig.add_trace(go.Scatter(x=t, y=tr.rep_voltage, mode="lines", name="Representative home",
                             line=dict(color=sem["accent"], width=1.6)))
    fig.add_trace(go.Scatter(x=t, y=tr.min_voltage, mode="lines", name="Weakest home",
                             line=dict(color=sem["caution"], width=1.2)))
    fig.add_hline(y=config.v_ln, line=dict(color=sem["muted"], width=1, dash="dot"),
                  annotation_text="nominal", annotation_position="top left",
                  annotation_font=dict(color=sem["muted"], size=10))
    _add_event_markers(fig, tr, theme, mark_blow=False)
    fig.update_layout(title="Home voltage", yaxis_title="V (L-N)", xaxis_title="minutes from restoration")
    return fig


def _fig_online(tr: TrialResult, config: Config, theme: str) -> go.Figure:
    sem = semantic(theme)
    t = _time_axis(tr)
    fig = themed_figure(theme, height=260)
    fig.add_trace(go.Scatter(x=t, y=tr.homes_online, mode="lines", name="Homes online",
                             line=dict(color=sem["ok"], width=1.6, shape="hv")))
    _add_event_markers(fig, tr, theme, mark_blow=True)
    fig.update_layout(title="Homes online", yaxis_title="homes", xaxis_title="minutes from restoration")
    return fig


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
def _tab_simulation(active: dict, theme: str) -> None:
    config: Config = active["config"]
    st.markdown("#### Single trial")
    c1, c2, c3 = st.columns([2, 2, 4], vertical_alignment="bottom")
    with c1:
        mode_label = st.selectbox("Mode", [m.label for m in ControllerMode],
                                  index=[m for m in ControllerMode].index(config.mode), key="sim_mode")
        mode = {m.label: m for m in ControllerMode}[mode_label]
    with c2:
        trial_idx = st.number_input("Representative trial", 0, config.mc_runs - 1, 0, 1, key="sim_trial")

    tr = _compute_trial(config, mode.value, int(trial_idx))

    sem = semantic(theme)
    m1, m2, m3, m4, m5 = st.columns(5)
    blow_chip = (
        f'<span class="pacer-chip danger">blow-out</span>' if tr.blew
        else f'<span class="pacer-chip ok">held</span>'
    )
    m1.markdown("Outcome")
    m1.markdown(blow_chip, unsafe_allow_html=True)
    m2.metric("Peak load", f"{tr.peak_pu:.2f} x")
    m3.metric("Homes dark", f"{tr.homes_dark}")
    m4.metric("Weakest voltage", f"{np.min(tr.min_voltage[tr.restore_minute:]):.0f} V")
    blow_txt = f"{tr.blow_minute_since_restore} min" if tr.blew else "--"
    m5.metric("Blow-out at", blow_txt)

    r1c1, r1c2 = st.columns(2)
    with r1c1:
        st.plotly_chart(_fig_load(tr, config, theme), use_container_width=True, config=_chart_config())
    with r1c2:
        st.plotly_chart(_fig_fuse(tr, config, theme), use_container_width=True, config=_chart_config())
    r2c1, r2c2 = st.columns(2)
    with r2c1:
        st.plotly_chart(_fig_hotspot(tr, config, theme), use_container_width=True, config=_chart_config())
    with r2c2:
        st.plotly_chart(_fig_voltage(tr, config, theme), use_container_width=True, config=_chart_config())
    st.plotly_chart(_fig_online(tr, config, theme), use_container_width=True, config=_chart_config())
    _back_to_top()


def _tab_montecarlo(active: dict, theme: str) -> None:
    mc: MonteCarloResult = active["mc"]
    sem = semantic(theme)
    st.markdown(f"#### {mc.n_runs} trials per mode")

    cols = st.columns(len(mc.modes))
    for col, m in zip(cols, mc.modes):
        s = mc.stats[m]
        rate = s.blowout_runs / s.n_runs * 100
        col.metric(m.label, f"{rate:.1f}%", help="Blow-out rate")
        col.caption(
            f"{s.blowout_runs}/{s.n_runs} runs, "
            f"95% CI [{s.blowout_ci.low*100:.1f}, {s.blowout_ci.high*100:.1f}]%"
        )

    # Blow-out rate with Clopper-Pearson error bars, coloured by severity.
    sev = {ControllerMode.BASELINE: sem["danger"], ControllerMode.PACER: sem["caution"],
           ControllerMode.PACER_BEACON: sem["ok"]}
    labels = [m.label for m in mc.modes]
    rates = [mc.stats[m].blowout_runs / mc.stats[m].n_runs * 100 for m in mc.modes]
    lo = [mc.stats[m].blowout_ci.low * 100 for m in mc.modes]
    hi = [mc.stats[m].blowout_ci.high * 100 for m in mc.modes]
    fig = themed_figure(theme, height=320)
    fig.add_trace(go.Bar(
        x=labels, y=rates, marker_color=[sev[m] for m in mc.modes],
        error_y=dict(type="data", symmetric=False,
                     array=[h - r for h, r in zip(hi, rates)],
                     arrayminus=[r - l for l, r in zip(lo, rates)],
                     color=sem["muted"], thickness=1),
        width=0.5,
    ))
    fig.update_layout(title="Blow-out rate with 95% confidence interval", yaxis_title="% of runs", showlegend=False)
    st.plotly_chart(fig, use_container_width=True, config=_chart_config())

    d1, d2 = st.columns(2)
    with d1:
        fig = themed_figure(theme, height=320)
        for m in mc.modes:
            fig.add_trace(go.Box(y=mc.stats[m].homes_dark, name=m.label, marker_color=sev[m],
                                 boxpoints=False, line=dict(width=1.2)))
        fig.update_layout(title="Homes dark per restoration", yaxis_title="homes", showlegend=False)
        st.plotly_chart(fig, use_container_width=True, config=_chart_config())
    with d2:
        fig = themed_figure(theme, height=320)
        for m in mc.modes:
            fig.add_trace(go.Box(y=mc.stats[m].peak_pu, name=m.label, marker_color=sev[m],
                                 boxpoints=False, line=dict(width=1.2)))
        fig.add_hline(y=1.0, line=dict(color=sem["muted"], width=1, dash="dot"))
        fig.update_layout(title="Peak load vs rating", yaxis_title="x rating", showlegend=False)
        st.plotly_chart(fig, use_container_width=True, config=_chart_config())
    _back_to_top()


def _headline_dataframe(mc: MonteCarloResult) -> pd.DataFrame:
    rows = []
    for m in mc.modes:
        s = mc.stats[m]
        rows.append({
            "Mode": m.label,
            "Blow-outs": f"{s.blowout_runs}/{s.n_runs}",
            "Rate": f"{s.blowout_runs / s.n_runs * 100:.1f}%",
            "95% CI": f"[{s.blowout_ci.low*100:.1f}, {s.blowout_ci.high*100:.1f}]%",
            "Homes dark": f"{s.mean_homes_dark:.1f}",
            "Peak x rating": f"{s.mean_peak_pu:.2f}",
            "Min >32 C": f"{s.mean_minutes_above_32:.1f}",
            "Ageing (h)": f"{s.mean_ageing_hours:.2f}",
        })
    return pd.DataFrame(rows)


def _df_to_markdown(df: pd.DataFrame) -> str:
    """Render a DataFrame as a GitHub-flavoured Markdown table (no tabulate dep)."""
    cols = list(df.columns)
    head = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    body = [
        "| " + " | ".join(str(v) for v in row) + " |"
        for row in df.itertuples(index=False)
    ]
    return "\n".join([head, sep, *body])


def _tab_results(active: dict, theme: str) -> None:
    mc: MonteCarloResult = active["mc"]
    config: Config = active["config"]
    df = _headline_dataframe(mc)

    st.markdown("#### Headline comparison")
    st.table(df)

    st.markdown("#### Statistical tests (two-proportion, blow-out rate)")
    for tt in mc.pairwise_tests:
        verdict = "significant" if tt.p_value < 0.05 else "not significant at 0.05"
        st.markdown(
            f'<span class="pacer-mono">{tt.label_a} vs {tt.label_b}: '
            f"{tt.prop_a*100:.1f}% vs {tt.prop_b*100:.1f}%, "
            f"z = {tt.z:+.3f}, p = {tt.p_value:.3g}</span> &mdash; {verdict}",
            unsafe_allow_html=True,
        )

    st.markdown("#### Reproducibility")
    st.markdown(
        f'<span class="pacer-chip accent">deterministic</span> '
        f'<span class="pacer-chip">seed {config.seed}</span> '
        f'<span class="pacer-chip">config {_config_hash(config)}</span> '
        f'<span class="pacer-chip">{mc.n_runs} runs/mode</span>',
        unsafe_allow_html=True,
    )
    st.caption("Same seed + same configuration reproduce these figures byte-for-byte.")

    st.markdown("#### Copy / export")
    cexp1, cexp2 = st.columns(2)
    with cexp1:
        st.caption("Results table (Markdown) -- use the copy button")
        st.code(_df_to_markdown(df), language="markdown")
        st.download_button("Download CSV", df.to_csv(index=False).encode(),
                           file_name=f"pacer_results_seed{config.seed}.csv", mime="text/csv")
    with cexp2:
        st.caption("Scenario configuration -- use the copy button")
        st.code(_config_text(config), language="text")
    _back_to_top()


def _config_text(config: Config) -> str:
    lines = [
        f"seed              {config.seed}",
        f"mc_runs           {config.mc_runs}",
        f"homes             {config.homes}",
        f"ac_penetration    {config.ac_penetration*100:.0f}%",
        f"vulnerable        {config.vulnerable_fraction*100:.0f}%",
        f"nameplate_kva     {config.nameplate_kva:.0f}",
        f"fuse_current_a    {config.fuse_current_a:.0f} (x{config.fuse_tightness:.2f} rated)",
        f"outage_minutes    {config.outage_minutes}",
        f"peak_ambient_c    {config.peak_ambient_c:.0f}",
        f"config_hash       {_config_hash(config)}",
    ]
    return "\n".join(lines)


def _tab_methodology(theme: str) -> None:
    st.markdown("#### How PACER-Sim works")
    st.markdown(
        "PACER-Sim advances one overloaded LV distribution transformer serving ~200 homes "
        "minute by minute through warm-up, a load-shedding outage, and recovery. Three "
        "controller modes are compared on identical scenarios. Every number shown in this "
        "app is computed by a run performed here; nothing is pre-baked."
    )
    with st.expander("The seven PACER rules"):
        st.markdown(
            "1. **Outage timer** -- ignore supply blips under 60 s; only outages of 60 s or more count.\n"
            "2. **Random wait** -- window = min(2 + 8 x outage_hours, 25) min; each device draws a uniform start inside it.\n"
            "3. **Soft start** -- the duty cap ramps from the per-appliance value (inverter AC 55%, chargers 30%, "
            "fixed-speed AC 55%) to 100% over a 30-min window.\n"
            "4. **Stress sensing** -- (learned normal voltage - present voltage) / self-measured impedance; relative "
            "to a learned per-time-of-day normal, never absolute voltage, with a self-impedance estimator (median of "
            "dV/dI over the device's own load steps).\n"
            "5. **Back-off** -- AC x0.75 (floor 0.35); charger x0.5 (floor 0); then latch and hold 6-12 min.\n"
            "6. **Stepped return** -- small random additive upward steps, so there is no rebound peak.\n"
            "7. **Heat-dose floor (always wins)** -- above 32 C, start 55% and add 10 points every 5 min (20 for "
            "registered-vulnerable homes) up to 100%, keeping the randomised start."
        )
        st.markdown(
            "Safety rails under everything: minimum off-time 3 min; at most 6 starts per hour; no command can ever "
            "switch a load **on**; any fault falls back to pass-through (the device behaves as if PACER were absent)."
        )
    with st.expander("Standards and models"):
        st.markdown(
            "- **Transformer thermal:** IEC 60076-7 top-oil + hot-spot difference equations at 1-min steps, with "
            "insulation ageing V = 2^((hot-spot - 98)/6). The thermal interface is swappable (an IEEE C57.91 "
            "implementation is included).\n"
            "- **Fuse:** a first-order element-heating surrogate for the fuse's I-squared-t time-current curve -- "
            "inverse-time, rides through brief surges, never melts at rated current, blows at 100% fuse-heat.\n"
            "- **Electrical:** a radial LV feeder with per-home series impedance, so aggregate load physically "
            "produces each home's voltage sag (what Rule 4 senses), with three-phase allocation and per-phase currents.\n"
            "- **Rooms:** a two-node (air + mass) thermal model driven by a diurnal ambient, so Rule 7's heat dose is real.\n"
            "- **Statistics:** Clopper-Pearson intervals on the blow-out proportion and a pooled two-proportion z-test between modes."
        )
    with st.expander("Assumptions"):
        st.markdown(
            "- Appliance penetrations and ratings are typical values for an Indian LV network; not every home has every appliance.\n"
            "- The transformer is deliberately sized so it runs near its rating under normal diversified load (an overloaded unit).\n"
            "- Phase assignment is independent per home, giving realistic phase imbalance.\n"
            "- Voltages use a resistive LV feeder approximation; sensing lags action by one minute (devices act on the previous minute's measurement).\n"
            "- Ambient follows a smooth diurnal curve between a night minimum and the chosen afternoon peak."
        )
    with st.expander("Limitations"):
        st.markdown(
            "- One-minute resolution averages out sub-minute transients such as motor inrush.\n"
            "- A single transformer is modelled; upstream (HV) dynamics are summarised by a source impedance.\n"
            "- The published 200/25/1 figures are a sanity check, not a fit target. Results are reported honestly; "
            "see the README for the full comparison and the temperature-sensitivity sweep.\n"
            "- Under extreme heat the health-first Rule 7 can override the Beacon's fuse guidance, so some blow-outs "
            "remain -- a genuine health-vs-fuse tension, not a modelling error."
        )
    _back_to_top()


def _back_to_top() -> None:
    st.markdown('<a class="pacer-top-link" href="#top">Back to top</a>', unsafe_allow_html=True)


def _footer(active: dict | None) -> None:
    ran = "no run yet"
    if active is not None:
        ran = active["ts"].strftime("%Y-%m-%d %H:%M:%S")
    st.markdown(
        f'<div class="pacer-foot">PACER-Sim v{APP_VERSION} &middot; build {BUILD_DATE} &middot; '
        f'last run {ran} &middot; simulated results, openly reproducible.</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    _init_state()
    theme = st.session_state.theme
    st.markdown(theme_css(theme), unsafe_allow_html=True)

    config, run_clicked = _sidebar()
    _render_header(config, theme)

    st.markdown('<span id="main-content"></span>', unsafe_allow_html=True)

    if run_clicked:
        _do_run(config)

    active = st.session_state.active

    # Staleness notice if the sidebar changed since the last run.
    if active is not None and active["key"] != config.key():
        st.warning("The scenario has changed since the last run. Press Run analysis to update the results below.")

    tabs = st.tabs(["Simulation", "Monte Carlo", "Results and verification", "Methodology"])
    with tabs[0]:
        if active is None:
            st.info("Configure the scenario in the sidebar and press Run analysis.")
        else:
            _tab_simulation(active, theme)
    with tabs[1]:
        if active is None:
            st.info("Configure the scenario in the sidebar and press Run analysis.")
        else:
            _tab_montecarlo(active, theme)
    with tabs[2]:
        if active is None:
            st.info("Configure the scenario in the sidebar and press Run analysis.")
        else:
            _tab_results(active, theme)
    with tabs[3]:
        _tab_methodology(theme)

    _footer(active)


if __name__ == "__main__":
    main()
