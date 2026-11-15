# Changelog

## Phase 6 — technical + 3D visuals (in progress)

New theme modules, wired into the simulator (all computed from the run, theme-aware):
- **3D transformer thermal** (`theme/viz3d.py`) — an oil tank + core + three phase
  windings, each coloured by its live hot-spot temperature (per-phase when that
  model is on), with a minute slider to scrub the restoration; the worst phase is
  named. In the Environment view.
- **IEC single-line diagram** (`theme/technical.py`) — grid -> Dyn transformer -> LV
  busbar -> three fused phase feeders -> loads, labelled with live per-phase peak
  load and fuse status. In the Structure view.
- **Phasor diagram** (`theme/technical.py`) — the three current phasors scaled by
  per-phase load with the neutral phasor (their vector sum) drawn dashed; it grows
  as the phases diverge. Beside the single-line.

Already shipped earlier: the fuse time-current curve (Phase 2) and the 3D
mode-comparison + restart surface (Overview). Deferred: the fully animated restart
playback, the 3D feeder network (needs per-home voltage snapshots stored), and the
2-D ambient x fuse sensitivity heatmap.

## Phase 5 — Beacon evidence view

A dedicated "Does the Beacon earn its cost?" simulator view (app-only; no engine
change). It runs the PACER-Core vs PACER+Beacon two-proportion test on the current
scenario and shows the marginal blow-out reduction with a 95% CI and p-value, then
**auto-generates a one-sentence verdict from the numbers** ("significant (p=..)" or
"no significant extra benefit; the CI includes zero"). A temperature sweep traces
where (if anywhere) the Beacon becomes significant, starring any significant point.
Finally it states the honest positioning: PACER-Core is the zero-infrastructure
hero; the Beacon is justified only where the test says so, and otherwise is
per-phase thermal telemetry + fuse-heat alerting + phase-rebalancing -- quantified
by the per-phase hot-spot spread it removes (Phase 3) when that model is enabled.

## Phase 4 — scenario coverage + robustness (in progress)

All opt-in / default to today's behaviour, so the golden fixture is byte-identical.

- **Coverage sweep** — `Config.module_adoption` (default 1.0): the fraction of homes
  with a PACER Module; the rest run pass-through. Guarded so full adoption draws no
  extra RNG. Added to `SWEEP_VARIABLES` ("Module adoption"), so the sweep tool traces
  blow-out rate vs adoption 0..100%. Test: PACER degrades monotonically toward the
  uncontrolled baseline as adoption falls (0% -> all blow).
- **Fault sweep** — `fault_probability` added to `SWEEP_VARIABLES`, so the sweep tool
  traces blow-out rate vs fault probability (exercising the pass-through rail).
- **Spoofed Beacon** — `Config.beacon_spoofed`: the Beacon broadcasts deliberately
  too-high caps. Because a cap can only *reduce* a device's own duty, the spoof
  collapses to PACER-only and cannot worsen the restart. Test: spoofed `blew` /
  `peak_pu` match PACER-only per trial -- the "signalling can only reduce load" claim.
- **Correlated estimator noise** — `Config.estimator_noise_ohm` (default 0): a
  shared-coupling term that confounds Rule 4's dV/dI when the whole population steps
  together, pre-empting the "your estimator is too clean" critique. Test: the sensed
  stress signal shifts off its clean value, deterministically.

Deferred (next): the multi-day learner (trains the evening voltage bins across days)
-- it restructures the single-day timeline, so it is its own reviewed step.

## Phase 3 — per-phase thermal + safety thresholds

**Three independent per-phase winding hot-spots over a shared top-oil**
(`engine/thermal.py` `PerPhaseIECThermal`, same IEC 60076-7 equations per phase).
Opt-in via `Config.per_phase_thermal` (default **False** = single-hot-spot model,
byte-identical golden). When on, the Beacon is fed real per-phase hot-spots instead
of the current-share proxy, and worst-phase ageing is reported. New outputs:
`hot_spot_phase_c` series and `peak_hot_spot_c`. A seed-7 run shows the Beacon
cutting per-phase hot-spot spread from ~36 C (lockstep baseline) to ~14 C — the
per-phase evidence the single-hot-spot model could not surface.

**IEC 60076-7 safety thresholds** (always on, observational): minutes with hot-spot
> 140 C (advisory) and > 160 C (bubbling / gas risk), as `minutes_hs_over_140` /
`minutes_hs_over_160`. Zero at the 42 C default (peak ~113 C); they fire in hotter
or more overloaded scenarios.

## Phase 2 — motor inrush + real fuse (in progress)

**Locked-rotor motor inrush** (`engine/simulation.py`, `engine/fuse.py`). Opt-in
via `Config.model_inrush` (default **False** = byte-identical golden). Fixed-speed
AC compressors and water pumps draw `I_start = k_LR * I_rated` (k=7) for 0.3 s
decaying to running current; `FuseBank.add_inrush` adds the excess I2t as an
impulse on the element. Modelled as the *aggregate* per phase — motors starting in
the same minute add in the same conductor, so the excess energy is quadratic in
simultaneity (`S*I_run*dI0 + (S/3)*dI0^2`). Result: lockstep baseline restart gets
a real inrush bump (peak fuse-heat 108.8 -> 109.5%), while PACER's stagger makes it
negligible (90.2% unchanged) — inrush is one more thing staggering defeats.
`high_fidelity_inrush` sub-steps the fuse at 1 s for 5 min post-restore (finer melt
timing; with a minute-resolution surrounding sim its effect is small). Inverter
AC/chargers soft-start, so they carry no inrush. Test: inrush lifts lockstep heat
more than staggered, deterministic, hi-fi path runs.

**Fuse calibrated to the IEC 60269 gG envelope** (`engine/fuse.py`). Added a
representative generic gG pre-arcing envelope (`IEC_GG_GATES`, labelled the
standard shape — no manufacturer datasheet bundled; cite IEC 60269-1 cat. gG), a
least-squares fit of the element `(tau, melting_factor)` to it (`fit_gg_params`),
and `FuseBank.time_current_curve()` for overlaying the modelled curve on the
envelope. Opt-in via `Config.fuse_iec_gg` (default **False** keeps the original
constants byte-for-byte). The fit is within ~2x across the sustained-overload
region and tight (~0.8x) at the 2x operating point where restart blow-outs occur.

**Limitation (honest):** a first-order thermal surrogate is gentler than a real
gG curve, so the two agree near ~2x In and diverge at the extremes; the sub-
second high-current end is energy, which the inrush I2t impulse (next) handles,
not `tau`. Opt-in, not the default, so headline numbers are unmoved.

## Phase 1 — electrical physics (in progress)

**Load-flow solver core** (`engine/loadflow.py`, new): a four-wire unbalanced
radial feeder solver via backward-forward sweep (Kersting). Segments carry
complex `Z = R + jX`; the shared neutral carries `-(I_A + I_B + I_C)`, so
unbalanced single-phase loads shift the neutral point and every home's L-N
voltage. Loads are voltage dependent (`P = P0 (V/V0)^np`, `Q = Q0 (V/V0)^nq`).
Reports source **neutral current** and **NEMA MG 1 voltage-unbalance factor
(VUF%)**, with convergence diagnostics (tol 1e-4 pu, max 8 sweeps).

**Wired into the simulation** behind `Config.use_reactance` (default **False** =
today's resistive model, so headline numbers and the golden fixture are unchanged
byte-for-byte). When True, `FeederModel.home_voltages` runs the four-wire solver:
transformer source impedance from `%Z` with `X/R = 5`, LV cable `X/R = 0.4` (one
shared 4-wire route; per-segment Z scaled so end-to-end sag matches the calibrated
resistive feeder), per-device `np/nq` exponents aggregated per home
(`engine/devices.py`), and an off-load tap. New `TrialResult` outputs: `i_neutral_a`
/ `vuf_pct` time series and `peak_neutral_a` / `max_vuf_pct`. A representative seed-7
run gives peak neutral ~35% of rated phase current, VUF peaking ~9% at the surge
instant, home voltage sagging ~240 to ~215 V — physical, not a fitted point.

Tests: NEMA VUF hand-case; balanced population draws ~no neutral current and
`|I_n|` rises monotonically with imbalance; the sweep converges; and a full
`use_reactance=True` trial is deterministic, voltages stay physical, `|I_n|`/VUF
are nonzero, while the default (off) path keeps those outputs zero.

**Limitations (honest):** `use_reactance` is opt-in and not yet the default — the
published comparison still runs the resistive model, so this adds physics without
moving the headline numbers (flipping the default is a separate reviewed step with
its own golden). The fuse current still comes from the nominal-voltage estimate,
not re-derived from the load-flow phase currents; and there is no UI surface for
`|I_n|` / VUF yet (that lands with the Phase 6 visuals).
