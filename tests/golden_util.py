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


def golden_payload(config: Config) -> dict:
    """Compute the full canonical payload used by both fixture and test."""
    result = run_monte_carlo(config)
    headline = [result.stats[m].summary() for m in result.modes]

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
