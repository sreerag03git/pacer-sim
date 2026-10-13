# PACER-Sim

A standards-grounded, minute-by-minute simulation of one overloaded LV
distribution transformer serving ~200 homes, and the deterministic **PACER**
controller (Phase-Aware Coordinated Energisation & Recovery) that staggers and
softens the post-outage restart. The engine compares three controller modes on
identical scenarios:

- **Baseline** — every stabiliser waits a fixed 3 minutes, then restarts in lockstep.
- **PACER only** — the seven-rule PACER Core inside every device (local sensing, no network).
- **PACER + Beacon** — PACER Core plus an optional per-transformer Beacon that
  broadcasts rate-limited, fuse- and thermal-aware per-phase guidance.

The physics engine (`engine/`) is **pure Python + numpy with zero Streamlit
imports**. It runs from the command line and is covered by a golden-regression
test. A Streamlit UI (`app.py`, `theme/`) is a full project showcase with a
dark/light engineering theme, hand-built theme-aware SVG diagrams, and six
sections: **Overview**, **Problem & solution** (the surge mechanism, the
three-layer architecture, the seven-rule control loop, feeder and hardware
drawings), **Simulator** (Simulation, Monte Carlo, Results and verification),
**Impact & case** (impact assessment, innovation/IP, challenge alignment),
**Delivery** (user journey, roadmap, methodology), and **Team & about**.

---

## Install & run

```bash
pip install -r requirements.txt
```

Launch the full interactive UI:

```bash
streamlit run app.py
```

Or run the engine headline comparison from the command line (no UI):

```bash
# Headline comparison across the three modes (seed 7, 200 Monte Carlo runs):
python -m engine.cli

# Faster, or explore scenarios:
python -m engine.cli --runs 50
python -m engine.cli --heatwave heatwave --outage 180 --nameplate 160
```

Reproduce the exact headline figures by passing the defaults (`--seed 7 --runs 200`).
Same seed + same config → **byte-identical** results.

### Tests

```bash
python -m pytest tests          # or:  python tests/test_golden.py
```

The suite asserts that (1) `engine/` imports no Streamlit, (2) seed 7 reproduces
the committed golden fixture `tests/golden_seed7.json` exactly, and (3) re-runs
are byte-identical. To intentionally re-baseline the fixture after an engine
change: `python -m tests._make_golden`.

---

## Deploy (Streamlit Community Cloud)

The app is self-contained — no secrets, databases or external services — so it
deploys straight from this repository:

1. Sign in at [share.streamlit.io](https://share.streamlit.io) with the GitHub
   account that owns this repo.
2. **Create app → Deploy a public app from GitHub**, then select:
   - Repository: this repo
   - Branch: `main`
   - Main file path: `app.py`
3. (Optional) Advanced settings → Python 3.11 or 3.12.
4. Deploy. The first launch installs `requirements.txt` and boots the app.

Note: a full 200-trial Monte Carlo run is CPU-bound and can take a couple of
minutes on a free single-vCPU host (the progress bar reflects real progress);
lower "Trials per mode" in the sidebar for a quicker pass. The same app runs
locally with `streamlit run app.py`, and in a container with any Python 3.10+
base image (`pip install -r requirements.txt && streamlit run app.py`).

---

## Headline result (seed 7, 200 runs, default scenario)

Default scenario: 200 homes, 160 kVA transformer, per-phase fuse at rated
current ("tight fuse"), 120-min outage, 42 °C peak-summer evening.

| Mode | Blow-outs | Rate | Homes dark | Peak × rating | Ageing (h) |
|------|-----------|------|------------|---------------|------------|
| Baseline | 200 / 200 | 100.0% | 189.0 | 2.04 | 10.6 |
| PACER only | 16 / 200 | 8.0% | 6.2 | 1.23 | 13.0 |
| PACER + Beacon | 12 / 200 | 6.0% | 4.7 | 1.29 | 12.5 |

Baseline vs PACER: z = +18.5, p ≈ 4e-76. Baseline vs PACER+Beacon: z = +18.8,
p ≈ 4e-79. PACER vs PACER+Beacon: z = +0.8, p = 0.43 (**not** significant).
(Clopper–Pearson intervals and the pairwise two-proportion tests are printed by
the CLI.)

---

## Integrity note — honest comparison to the published figures

The published PACER figures are **200 / 25 / 1** at seed 7 (tight fuse): baseline
blows in ~200/200 runs, PACER-only ~25, PACER+Beacon ≤1. These were used **only
as a sanity check, never as a target to fit.** No constant was reverse-engineered,
clamped or special-cased to land on them. Every physical quantity is a named,
commented constant derived from standards or typical appliance ratings; the
scenario defaults describe a realistically overloaded transformer.

What the engine actually produces, and where it differs:

- **Baseline — matches.** 200/200 blow-outs, ~189 homes dark (published ~197),
  peak ≈ 2.0× rating ("roughly doubling"). The lockstep restart is a genuine,
  reproducible collapse.
- **PACER-only — same order, honestly a little *better*: 16/200 (8.0%) vs 25/200
  (12.5%).** The impedance-normalised stress sensing (Rule 4) throttles the
  heavy phase before the fuse melts, holding the restart plateau to ~1.23×, just
  under the fuse. If anything our engine is *more* optimistic about PACER than the
  deck; we report it rather than inflate it.
- **PACER + Beacon — no statistically significant benefit over PACER-only in this
  engine, and we do *not* reproduce the published "≤1".** At the default it is
  12/200 vs 16/200 (p = 0.43); in a 46 °C heatwave it is 113/200 vs 114/200 — a
  wash. Two honest reasons: (a) in cool conditions PACER's local throttling
  already holds the plateau below the fuse, so the Beacon has little to add; (b)
  in hot conditions the health-first Rule 7 overrides the Beacon's fuse guidance
  exactly when blows occur — a genuine health-vs-fuse tension. An earlier build
  *did* show the Beacon helping under heat, but that benefit turned out to rest on
  an over-counting heat-dose bug (the floor grew by wall-clock since the first
  32 °C crossing instead of by cumulative minutes above 32 °C); fixing it removed
  the apparent advantage. We report the wash rather than tune the Beacon to hit
  ≤1 — which is exactly why auditing and reporting honestly is the point.

### It is physics, not a fitted point — temperature sensitivity

Holding everything else fixed and sweeping only the peak ambient temperature
(80 runs/point) gives a smooth, physical curve — exactly what an un-rigged model
should look like. PACER and PACER+Beacon track together within sampling noise;
baseline is 100% throughout:

| Peak °C | Baseline | PACER | PACER+Beacon |
|--------:|---------:|------:|-------------:|
| 38 | 100% | 0% | 0% |
| 40 | 100% | 1% | 1% |
| 42 (default) | 100% | 4% | 1% |
| 43 | 100% | 12% | 12% |
| 44 | 100% | 26% | 28% |
| 45 | 100% | 46% | 50% |
| 46 | 100% | 57% | 55% |

At 80 runs/point these low rates carry wide confidence intervals (hence the 4%
here vs 8% in the 200-run headline at 42 °C — the 200-run figure is the
authoritative one). The published PACER figure (12.5%) lands near ~43 °C. We chose
42 °C as the default because the deck states its figures hold "even in simulated
42–45 °C heatwaves", so 42 °C is the faithful low end of that stated band — a
scenario choice, documented up front, not a value picked to match an output.

---

## Standards and models

- **Transformer thermal:** IEC 60076-7 top-oil + hot-spot difference equations at
  1-min steps, with insulation ageing `V = 2^((θ_hs − 98)/6)`. Behind a swappable
  `TransformerThermalModel` interface; a second conforming implementation
  (IEEE C57.91) is provided and exercised by the tests to demonstrate the swap
  (`engine/thermal.py`, `tests/test_engine.py`).
- **Fuse:** per-phase first-order element-heating surrogate for the fuse's I²t
  time-current curve — inverse-time, rides through brief surges, never melts at
  rated, blows at 100% fuse-heat (`engine/fuse.py`).
- **Electrical:** radial LV feeder with per-home series impedance; aggregate load
  physically produces each home's voltage sag (what Rule 4 senses), plus
  three-phase allocation and per-phase currents (`engine/grid.py`).
- **Rooms:** two-node (air + mass) thermal model driven by a diurnal ambient, so
  Rule 7's heat dose is real (`engine/thermal.py`).
- **Appliances:** inverter AC, fixed-speed AC, inverter/battery charger, e-rickshaw
  charger, water pump — each with its own rating, soft-start, back-off and floor,
  at realistic penetrations (`engine/appliances.py`).
- **Monte Carlo + statistics:** N randomised trials per scenario; Clopper–Pearson
  intervals on the blow-out proportion and a pooled two-proportion z-test between
  modes (`engine/stats.py`, `engine/montecarlo.py`).

### The seven PACER rules (`engine/pacer_core.py`)

1. **Outage timer** — ignore supply blips < 60 s; only outages ≥ 60 s count.
2. **Random wait** — window = `min(2 + 8·outage_hours, 25)` min; each device draws a uniform start inside it.
3. **Soft start** — duty cap ramps from the per-appliance value (inverter AC 55%, chargers 30%, fixed-speed AC 55%) to 100% over 30 min.
4. **Stress sensing** — `(learned_normal_V − present_V) / self-measured impedance`; relative to a learned per-time-of-day normal, never absolute voltage, with a self-impedance estimator (median of dV/dI over the device's own load steps).
5. **Back-off** — AC ×0.75 floor 0.35; charger ×0.5 floor 0; then latch and hold 6–12 min.
6. **Stepped return** — small random additive upward steps, so there is no rebound peak.
7. **Heat-dose floor (always wins)** — above 32 °C, start 55% and add 10 points / 5 min (20 for registered-vulnerable homes) up to 100%, keeping the randomised start.

Safety rails under everything: minimum off-time 3 min; ≤ 6 starts/hour; no command
can switch a load *on*; any fault falls back to pass-through.

---

## Project structure

```
engine/            pure, UI-free, tested physics + controller
  config.py        immutable scenario configuration
  appliances.py    appliance profiles
  devices.py       device population builder (struct-of-arrays)
  grid.py          LV feeder electrical model
  thermal.py       IEC 60076-7 (+ IEEE C57.91) transformer + room models
  fuse.py          per-phase fuse heating / melting
  pacer_core.py    the seven-rule controller
  beacon.py        per-transformer Beacon (mode C)
  simulation.py    one deterministic minute-by-minute trial
  montecarlo.py    N trials + statistics
  stats.py         Clopper–Pearson + two-proportion test
  cli.py           command-line headline comparison
app.py             Streamlit UI (UI only; drives and reads the engine)
theme/             theme system
  palette.py       the two engineering palettes (exact hexes)
  css.py           injected CSS: CSS variables + Streamlit restyle
  plotly_template.py  Plotly templates bound to the active theme
  diagrams.py      hand-built, theme-aware SVG diagrams
.streamlit/        config.toml (first-paint theme, clean chrome)
tests/             golden-regression + determinism tests
```

The UI (`app.py`, `theme/`) is UI only: all physics and statistics live in the
Streamlit-free `engine` package, which the app merely drives and reads.
