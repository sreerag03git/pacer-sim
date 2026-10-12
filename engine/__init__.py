"""PACER physics engine (pure Python + numpy, zero Streamlit).

PACER = Phase-Aware Coordinated Energisation & Recovery.

This package contains a standards-grounded, minute-by-minute simulation of a
single overloaded LV distribution transformer serving ~200 homes, and the
deterministic PACER controller that staggers and softens the post-outage
restart. It is deliberately free of any UI dependency so it can run from the
command line and be regression-tested in isolation.

Public surface:
    Config                      -- immutable simulation configuration
    run_trial                   -- one deterministic minute-by-minute trial
    run_monte_carlo             -- N randomised trials with statistics
    ControllerMode              -- BASELINE / PACER / PACER_BEACON
    HeatwavePreset              -- ambient temperature presets
"""

from engine.config import (
    Config,
    ControllerMode,
    HeatwavePreset,
)
from engine.simulation import TrialResult, run_trial
from engine.montecarlo import ModeStatistics, MonteCarloResult, run_monte_carlo

__all__ = [
    "Config",
    "ControllerMode",
    "HeatwavePreset",
    "TrialResult",
    "run_trial",
    "ModeStatistics",
    "MonteCarloResult",
    "run_monte_carlo",
]

__version__ = "0.2.0"
