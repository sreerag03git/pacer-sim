"""Shared helpers for the golden regression fixture and test.

Keeping the canonical config and serialisation in one place guarantees the
fixture generator and the test compute exactly the same thing.
"""

from __future__ import annotations

import hashlib

import numpy as np

from engine.config import Config, ControllerMode
from engine.montecarlo import run_monte_carlo
from engine.simulation import TrialResult, run_trial

# A small, fast, fully-specified config. 24 runs is enough to pin determinism
# while keeping the regression test quick.
GOLDEN_CONFIG = Config(seed=7, mc_runs=24)


def series_sha256(result: TrialResult) -> str:
    """Stable hash of a trial's key time series (rounded to 4 dp)."""
    parts = [
        np.round(result.load_pu, 4),
        np.round(result.phase_heat_pct, 4).ravel(),
        np.round(result.hot_spot_c, 4),
        np.round(result.rep_voltage, 4),
        np.round(result.min_voltage, 4),
        np.round(result.homes_online, 4),
    ]
    blob = b"".join(p.tobytes() for p in parts)
    return hashlib.sha256(blob).hexdigest()


# The Clopper-Pearson interval bounds come from scipy.stats.beta.ppf, whose
# low-order decimals can shift between scipy point releases. They are a pure
# function of (blowout_runs, n_runs) -- both pinned by the engine -- so excluding
# them keeps the byte-identical golden check about the engine (numpy) itself and
# not about a third-party library's rounding.
_SCIPY_DERIVED_KEYS = ("blowout_ci_low", "blowout_ci_high")


def golden_payload(config: Config) -> dict:
    """Compute the full canonical payload used by both fixture and test."""
    result = run_monte_carlo(config)
    headline = [
        {k: v for k, v in result.stats[m].summary().items() if k not in _SCIPY_DERIVED_KEYS}
        for m in result.modes
    ]

    # A single deterministic trial, with a full time-series hash.
    trial = run_trial(config.with_mode(ControllerMode.BASELINE), trial_index=0)

    return {
        "config": {
            "seed": config.seed,
            "mc_runs": config.mc_runs,
            "homes": config.homes,
            "nameplate_kva": config.nameplate_kva,
            "fuse_current_a": round(config.fuse_current_a, 6),
            "outage_minutes": config.outage_minutes,
            "heatwave": config.heatwave.value,
            "peak_ambient_c": config.peak_ambient_c,
        },
        "headline": headline,
        "single_trial": {
            **trial.scalar_summary(),
            "series_sha256": series_sha256(trial),
        },
    }
