"""Engine unit tests: safety rails, swappable thermal interface, Rule 4 estimator.

These complement the golden-regression suite with targeted checks that
exercise mechanisms the headline run does not isolate.

Run with pytest (``python -m pytest tests``) or standalone
(``python tests/test_engine.py``).
"""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.config import Config, ControllerMode
from engine.devices import build_devices
from engine.grid import FeederModel
from engine.loadflow import nema_vuf, solve_feeder
from engine.montecarlo import run_sweep
from engine.pacer_core import PacerController
from engine.simulation import run_trial, scenario_structure
from engine.thermal import (
    IECThermalModel,
    IEEEThermalModel,
    TransformerThermalModel,
)


def test_fault_pass_through_fires() -> None:
    """With every device faulted, PACER must fall back to pass-through (no pacing),
    so the restart surge returns and blows the fuse just as the uncontrolled grid
    would -- whereas with no faults the same PACER scenario holds."""
    base = Config(seed=7, mc_runs=1)
    paced = run_trial(base.with_mode(ControllerMode.PACER), trial_index=0)
    faulted_cfg = Config(seed=7, mc_runs=1, fault_probability=1.0)
    faulted = run_trial(faulted_cfg.with_mode(ControllerMode.PACER), trial_index=0)

    # Pass-through removes the stagger/soft-start, so the peak is far higher and
    # the fuse blows -- demonstrating the rail is reachable and actually fires.
    assert faulted.peak_pu > paced.peak_pu + 0.3
    assert faulted.blew and not paced.blew


def test_thermal_interface_is_swappable() -> None:
    """Both the IEC 60076-7 and IEEE C57.91 implementations satisfy the same
    interface and produce physically sane, swappable behaviour."""
    load_profile = [0.75] * 30 + [1.8] * 30 + [0.9] * 60  # pu
    ambient = 40.0
    for model in (IECThermalModel(), IEEEThermalModel()):
        assert isinstance(model, TransformerThermalModel)
        model.reset(ambient)
        start_hs = model.hot_spot_c
        for k in load_profile:
            model.step(k, ambient, dt_min=1.0)
        # Hot-spot sits above top-oil above ambient; ageing accrues; overload heats.
        assert model.hot_spot_c >= model.top_oil_c >= ambient
        assert model.hot_spot_c > start_hs
        assert model.ageing_hours > 0.0


def test_impedance_estimator_tracks_true_feeder_impedance() -> None:
    """Rule 4's self-impedance estimator (median of dV/dI over the device's own
    load steps) must converge to the feeder's true upstream impedance."""
    cfg = Config(homes=60, seed=3)
    srng = np.random.default_rng(np.random.SeedSequence([cfg.seed, 0, 0]))
    dev = build_devices(cfg, srng)
    feeder = FeederModel(dev.home_phase, cfg.v_ln, cfg.power_factor, srng)
    ctrl = PacerController(dev, cfg)
    true_z = feeder.home_upstream_impedance()

    # Probe a few devices spread along the feeders: toggle each one's load on/off
    # (others idle) so its own current step is the only cause of the voltage step.
    targets = [0, dev.n_devices // 3, (2 * dev.n_devices) // 3, dev.n_devices - 1]
    minute = 0
    for tdev in targets:
        for _ in range(8):
            for level in (0.0, 1.0):
                served = np.zeros(dev.n_devices)
                served[tdev] = level
                home_power = np.bincount(dev.home, weights=served * dev.rated_kw, minlength=cfg.homes)
                v_home = feeder.home_voltages(home_power)
                i_dev = served * dev.rated_kw * 1000.0 / (cfg.v_ln * cfg.power_factor)
                ctrl.observe(cfg.day_start_minute + minute, v_home[dev.home], i_dev, valid=True)
                minute += 1

    est = ctrl.z_estimate
    for tdev in targets:
        truth = true_z[dev.home[tdev]]
        assert abs(est[tdev] - truth) < 0.01, f"device {tdev}: est {est[tdev]:.4f} vs true {truth:.4f}"


def test_fault_probability_validation() -> None:
    assert Config(fault_probability=0.5).validate() == []
    assert any("fault probability" in p for p in Config(fault_probability=1.5).validate())


def test_scenario_structure_reconciles() -> None:
    """The population description the UI's Structure view reads must be internally
    consistent (counts reconcile, shapes follow the config) and deterministic."""
    cfg = Config(homes=120, seed=5)
    s = scenario_structure(cfg)

    assert s["n_homes"] == cfg.homes
    # every home sits on exactly one phase; every device has exactly one phase/kind
    assert sum(s["homes_per_phase"]) == s["n_homes"]
    assert sum(s["devices_per_phase"]) == s["n_devices"]
    assert sum(s["kind_counts"]) == s["n_devices"]
    # shapes follow the config
    assert len(s["kind_counts"]) == 5 == len(s["appliance_labels"])
    for key in ("homes_per_phase", "devices_per_phase", "connected_kw_per_phase"):
        assert len(s[key]) == cfg.phases
    # physical sanity
    assert s["total_connected_kw"] > 0.0
    assert s["rated_phase_current_a"] > 0.0
    assert s["n_ac_homes"] <= s["n_homes"]
    assert 0 <= s["n_vulnerable"] <= s["n_devices"]
    # default fuse tightness 1.0 => fuse current equals the rated phase current
    assert abs(s["fuse_current_a"] - s["rated_phase_current_a"]) < 1e-6
    # pure function of the config -> identical on a second call
    assert scenario_structure(cfg) == s


def test_run_sweep_is_deterministic_and_ordered() -> None:
    """The sensitivity sweep must return a clean per-mode curve, be byte-stable
    across re-runs, and never show lockstep baseline beating PACER on blow-outs."""
    base = Config(homes=120, mc_runs=2, seed=7)  # loaded enough to exercise blow-outs
    modes = [ControllerMode.BASELINE, ControllerMode.PACER]
    values = [1.0, 1.2]
    sw = run_sweep(base, "fuse_tightness", values, modes=modes)

    assert sw.values == values and sw.modes == modes and sw.n_runs == base.mc_runs
    for m in modes:
        assert len(sw.rate_pct[m]) == len(values)
        assert all(0.0 <= r <= 100.0 for r in sw.rate_pct[m])
    # PACER's stagger can only match or beat the lockstep restart, per swept value
    for i in range(len(values)):
        assert sw.rate_pct[ControllerMode.BASELINE][i] >= sw.rate_pct[ControllerMode.PACER][i]
    # same seed + inputs => identical curve
    sw2 = run_sweep(base, "fuse_tightness", values, modes=modes)
    assert sw.rate_pct == sw2.rate_pct and sw.peak_pu == sw2.peak_pu


def test_nema_vuf_hand_case() -> None:
    """NEMA MG 1: mean 234 V, worst deviation 6 V -> 2.564% unbalance."""
    assert abs(nema_vuf([240.0, 228.0, 234.0]) - 6.0 / 234.0 * 100.0) < 1e-9
    assert nema_vuf([230.0, 230.0, 230.0]) == 0.0


def test_loadflow_neutral_rises_with_imbalance() -> None:
    """Four-wire sweep (Phase 1): a balanced population draws ~no source neutral
    current; piling load onto one phase makes |I_n| rise monotonically. Converges."""
    n = 30
    home_phase = np.arange(n) % 3  # 10 homes per phase, interleaved
    r = 0.004
    z_seg = np.full(n, r + 1j * 0.4 * r)  # LV cable, X/R = 0.4
    z_src = 0.01 + 1j * 0.05  # transformer, X/R = 5
    tan_phi = float(np.tan(np.arccos(0.90)))

    def neutral(load_w):
        sol = solve_feeder(home_phase, z_seg, z_seg, z_src, z_src,
                           load_w, load_w * tan_phi, 0.0, 0.0, 240.0)
        assert sol.converged
        return abs(sol.i_neutral_src), abs(sol.i_phase_src[0])

    base = np.full(n, 800.0)  # W per home
    i_bal, i_phase = neutral(base)
    assert i_bal < 0.2 * i_phase  # balanced -> neutral far below a phase current

    prev = i_bal
    for extra in (1.5, 2.5, 4.0):
        load = base.copy()
        load[home_phase == 0] *= extra
        cur, _ = neutral(load)
        assert cur > prev
        prev = cur


def test_reactance_path_outputs_and_determinism() -> None:
    """use_reactance wires the four-wire solver into a full trial: neutral current
    and VUF become nonzero, voltages stay physical, the run is deterministic, and
    the flag is off by default (outputs stay zero, old results untouched)."""
    cfg = Config(homes=60, seed=7, use_reactance=True).with_mode(ControllerMode.BASELINE)
    a = run_trial(cfg, trial_index=0)
    b = run_trial(cfg, trial_index=0)
    assert np.array_equal(a.i_neutral_a, b.i_neutral_a)  # deterministic
    assert a.peak_neutral_a > 0.0 and a.max_vuf_pct > 0.0  # imbalance is real
    assert 180.0 < float(a.rep_voltage.max()) < 250.0  # no runaway / overvoltage

    off = run_trial(Config(homes=60, seed=7).with_mode(ControllerMode.BASELINE), trial_index=0)
    assert off.peak_neutral_a == 0.0 and off.max_vuf_pct == 0.0


def _run_standalone() -> int:
    tests = [
        test_fault_pass_through_fires,
        test_thermal_interface_is_swappable,
        test_impedance_estimator_tracks_true_feeder_impedance,
        test_fault_probability_validation,
        test_scenario_structure_reconciles,
        test_run_sweep_is_deterministic_and_ordered,
        test_nema_vuf_hand_case,
        test_loadflow_neutral_rises_with_imbalance,
        test_reactance_path_outputs_and_determinism,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {t.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
