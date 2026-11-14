# Changelog

## Phase 1 — electrical physics (in progress)

**Load-flow solver core** (`engine/loadflow.py`, new): a four-wire unbalanced
radial feeder solver via backward-forward sweep (Kersting). Segments carry
complex `Z = R + jX`; the shared neutral carries `-(I_A + I_B + I_C)`, so
unbalanced single-phase loads shift the neutral point and every home's L-N
voltage. Loads are voltage dependent (`P = P0 (V/V0)^np`, `Q = Q0 (V/V0)^nq`).
Reports source **neutral current** and **NEMA MG 1 voltage-unbalance factor
(VUF%)**, with convergence diagnostics (tol 1e-4 pu, max 8 sweeps).

Unit tests (`tests/test_engine.py`): NEMA VUF hand-case; balanced population
draws ~no neutral current and `|I_n|` rises monotonically with imbalance; the
sweep converges.

**Not yet wired into a run.** The solver is standalone and off the simulation
path, so existing headline numbers and the golden fixture are unchanged
byte-for-byte. Next increment: wire it into `FeederModel` behind a
`use_reactance` config flag (default False = today's resistive model), derive
the transformer source impedance from `%Z` with `X/R = 5` and LV cable `X/R =
0.4`, attach per-device `np/nq`, surface `|I_n|` / VUF as trial outputs, and add
a golden test for the reactive scenario.
