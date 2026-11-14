# Changelog

## Phase 2 — motor inrush + real fuse (in progress)

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
