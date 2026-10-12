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
from engine.pacer_core import PacerController
from engine.simulation import run_trial
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


def _run_standalone() -> int:
    tests = [
        test_fault_pass_through_fires,
        test_thermal_interface_is_swappable,
        test_impedance_estimator_tracks_true_feeder_impedance,
        test_fault_probability_validation,
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
