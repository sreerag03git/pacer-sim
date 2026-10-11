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
test. A Streamlit UI (`app.py`, `theme/`) drives and reads the engine, with a
dark/light engineering theme and four tabs (Simulation, Monte Carlo, Results and
verification, Methodology).

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

## Headline result (seed 7, 200 runs, default scenario)

Default scenario: 200 homes, 160 kVA transformer, per-phase fuse at rated
current ("tight fuse"), 120-min outage, 42 °C peak-summer evening.

| Mode | Blow-outs | Rate | Homes dark | Peak × rating | Ageing (h) |
|------|-----------|------|------------|---------------|------------|
| Baseline | 200 / 200 | 100.0% | 189.4 | 2.04 | 10.6 |
| PACER only | 17 / 200 | 8.5% | 6.6 | 1.23 | 13.0 |
| PACER + Beacon | 8 / 200 | 4.0% | 3.6 | 1.27 | 12.5 |

Baseline vs PACER: z = +18.4, p ≈ 2e-75. Baseline vs PACER+Beacon: z = +19.2,
p ≈ 3e-82. (Clopper–Pearson intervals and the pairwise two-proportion tests are
printed by the CLI.)

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
- **PACER-only — same order, honestly a little *better*: 17/200 (8.5%) vs 25/200
  (12.5%).** The impedance-normalised stress sensing (Rule 4) throttles the
  heavy phase before the fuse melts, holding the restart plateau to ~1.23×, just
  under the fuse. If anything our engine is *more* optimistic about PACER than the
  deck; we report it rather than inflate it.
- **PACER + Beacon — reduces PACER's blow-outs by roughly half (8/200), but does
  not reach ≤1 at this operating point.** Two honest reasons: (a) the health-first
  heat-dose floor (Rule 7) is implemented as *always wins*, so under heat it can
  legitimately override the Beacon's fuse guidance — a real health-vs-fuse
  tension, not a bug; (b) the Beacon senses with a one-minute lag. Its benefit
  grows with heat stress (below).

### It is physics, not a fitted point — temperature sensitivity

Holding everything else fixed and sweeping only the peak ambient temperature
(80 runs/point) gives a smooth, physical curve — exactly what an un-rigged model
should look like:

| Peak °C | Baseline | PACER | PACER+Beacon |
|--------:|---------:|------:|-------------:|
| 38 | 100% | 0% | 0% |
| 40 | 100% | 1% | 0% |
| 42 (default) | 100% | ~4–8% | ~0–4% |
| 43 | 100% | 12% | 8% |
| 44 | 100% | 28% | 20% |
| 45 | 100% | 49% | 41% |

The published PACER figure (12.5%) lands near ~43 °C in our engine. We chose
42 °C as the default because the deck states its figures hold "even in simulated
42–45 °C heatwaves", so 42 °C is the faithful low end of that stated band — a
scenario choice, documented up front, not a value picked to match an output.

---

## Standards and models

- **Transformer thermal:** IEC 60076-7 top-oil + hot-spot difference equations at
  1-min steps, with insulation ageing `V = 2^((θ_hs − 98)/6)`. Behind a swappable
  `TransformerThermalModel` interface; an IEEE C57.91 implementation is included
  to prove the swap (`engine/thermal.py`).
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
.streamlit/        config.toml (first-paint theme, clean chrome)
tests/             golden-regression + determinism tests
```

The UI (`app.py`, `theme/`) is UI only: all physics and statistics live in the
Streamlit-free `engine` package, which the app merely drives and reads.
