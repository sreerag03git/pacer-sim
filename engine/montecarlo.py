"""Monte Carlo: N randomised trials per mode, with statistics.

Each mode is run over the *same* set of trial indices, so mode ``m`` trial ``i``
sees byte-identically the same scenario across all three controllers -- only the
controller differs. Per mode we report blow-outs (with a Clopper-Pearson
interval), homes dark per restoration, peak load vs rating, minutes above 32 C
and insulation ageing; between modes we report a two-proportion test on the
blow-out rate.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable, Optional, Sequence

import numpy as np

from engine.config import Config, ControllerMode
from engine.simulation import TrialResult, run_trial
from engine.stats import ProportionCI, TwoProportionTest, clopper_pearson, two_proportion_z_test

ProgressCallback = Callable[[float, str], None]

# Sweepable scenario variables: name -> (Config field, is_percent_fraction).
SWEEP_VARIABLES: dict[str, str] = {
    "Ambient peak (C)": "ambient_peak_c",
    "Fuse tightness (x rated)": "fuse_tightness",
    "AC penetration (%)": "ac_penetration",
    "Outage duration (min)": "outage_minutes",
    "Transformer rating (kVA)": "nameplate_kva",
    "Vulnerable homes (%)": "vulnerable_fraction",
}


@dataclass
class ModeStatistics:
    """Aggregated outcomes for one controller mode over ``n_runs`` trials."""

    mode: ControllerMode
    n_runs: int
    blowout_runs: int
    blowout_ci: ProportionCI
    mean_homes_dark: float
    mean_peak_pu: float
    mean_minutes_above_32: float
    mean_ageing_hours: float
    # per-trial vectors (for distribution plots and re-analysis)
    blew: np.ndarray = field(repr=False)
    homes_dark: np.ndarray = field(repr=False)
    peak_pu: np.ndarray = field(repr=False)
    minutes_above_32: np.ndarray = field(repr=False)
    ageing_hours: np.ndarray = field(repr=False)

    def summary(self) -> dict:
        """Order-stable scalar summary (used for the headline table and hashing)."""
        return {
            "mode": self.mode.value,
            "n_runs": int(self.n_runs),
            "blowout_runs": int(self.blowout_runs),
            "blowout_rate": round(self.blowout_runs / self.n_runs, 6) if self.n_runs else float("nan"),
            "blowout_ci_low": round(self.blowout_ci.low, 6),
            "blowout_ci_high": round(self.blowout_ci.high, 6),
            "mean_homes_dark": round(self.mean_homes_dark, 6),
            "mean_peak_pu": round(self.mean_peak_pu, 6),
            "mean_minutes_above_32": round(self.mean_minutes_above_32, 6),
            "mean_ageing_hours": round(self.mean_ageing_hours, 6),
        }


@dataclass
class MonteCarloResult:
    """The full three-mode comparison for one Config."""

    config: Config
    seed: int
    n_runs: int
    modes: list[ControllerMode]
    stats: dict[ControllerMode, ModeStatistics]
    pairwise_tests: list[TwoProportionTest]

    def headline_rows(self) -> list[dict]:
        return [self.stats[m].summary() for m in self.modes]


def _aggregate(mode: ControllerMode, results: Sequence[TrialResult]) -> ModeStatistics:
    blew = np.array([r.blew for r in results], dtype=bool)
    homes_dark = np.array([r.homes_dark for r in results], dtype=float)
    peak_pu = np.array([r.peak_pu for r in results], dtype=float)
    minutes_above_32 = np.array([r.minutes_above_32 for r in results], dtype=float)
    ageing_hours = np.array([r.ageing_hours for r in results], dtype=float)
    n = len(results)
    blowout_runs = int(blew.sum())
    return ModeStatistics(
        mode=mode,
        n_runs=n,
        blowout_runs=blowout_runs,
        blowout_ci=clopper_pearson(blowout_runs, n),
        mean_homes_dark=float(homes_dark.mean()) if n else float("nan"),
        mean_peak_pu=float(peak_pu.mean()) if n else float("nan"),
        mean_minutes_above_32=float(minutes_above_32.mean()) if n else float("nan"),
        mean_ageing_hours=float(ageing_hours.mean()) if n else float("nan"),
        blew=blew,
        homes_dark=homes_dark,
        peak_pu=peak_pu,
        minutes_above_32=minutes_above_32,
        ageing_hours=ageing_hours,
    )


def run_monte_carlo(
    config: Config,
    modes: Optional[Sequence[ControllerMode]] = None,
    progress: Optional[ProgressCallback] = None,
) -> MonteCarloResult:
    """Run the Monte Carlo comparison across ``modes`` (default: all three)."""
    if modes is None:
        modes = [ControllerMode.BASELINE, ControllerMode.PACER, ControllerMode.PACER_BEACON]
    modes = list(modes)

    n = config.mc_runs
    total_steps = len(modes) * n
    step = 0
    stats: dict[ControllerMode, ModeStatistics] = {}

    for mode in modes:
        mode_cfg = config.with_mode(mode)
        results: list[TrialResult] = []
        for i in range(n):
            results.append(run_trial(mode_cfg, trial_index=i))
            step += 1
            if progress is not None:
                progress(step / total_steps, f"{mode.label}: trial {i + 1}/{n}")
        stats[mode] = _aggregate(mode, results)

    # pairwise two-proportion tests on the blow-out rate (consecutive modes)
    tests: list[TwoProportionTest] = []
    for a, b in zip(modes[:-1], modes[1:]):
        sa, sb = stats[a], stats[b]
        tests.append(
            two_proportion_z_test(
                sa.blowout_runs, sa.n_runs, sb.blowout_runs, sb.n_runs, a.label, b.label
            )
        )
    # also baseline vs the strongest mode, if more than two modes
    if len(modes) > 2:
        sa, sb = stats[modes[0]], stats[modes[-1]]
        tests.append(
            two_proportion_z_test(
                sa.blowout_runs, sa.n_runs, sb.blowout_runs, sb.n_runs, modes[0].label, modes[-1].label
            )
        )

    return MonteCarloResult(
        config=config,
        seed=config.seed,
        n_runs=n,
        modes=modes,
        stats=stats,
        pairwise_tests=tests,
    )


@dataclass
class SweepResult:
    """Blow-out rate (and homes-dark, peak) for each mode as one scenario variable
    is swept, holding everything else fixed."""

    field_name: str
    values: list[float]
    modes: list[ControllerMode]
    rate_pct: dict[ControllerMode, list[float]]
    homes_dark: dict[ControllerMode, list[float]]
    peak_pu: dict[ControllerMode, list[float]]
    n_runs: int


def run_sweep(
    base_config: Config,
    field_name: str,
    values: Sequence[float],
    modes: Optional[Sequence[ControllerMode]] = None,
    progress: Optional[ProgressCallback] = None,
) -> SweepResult:
    """Run a Monte Carlo comparison at each value of ``field_name`` (a Config
    field), returning the blow-out curve per mode. Everything else is held fixed,
    so the result is a clean sensitivity curve."""
    if modes is None:
        modes = [ControllerMode.BASELINE, ControllerMode.PACER, ControllerMode.PACER_BEACON]
    modes = list(modes)
    rate = {m: [] for m in modes}
    dark = {m: [] for m in modes}
    peak = {m: [] for m in modes}
    total = max(len(values), 1)
    for i, v in enumerate(values):
        cfg = replace(base_config, **{field_name: v})
        res = run_monte_carlo(cfg, modes=modes)
        for m in modes:
            s = res.stats[m]
            rate[m].append(s.blowout_runs / s.n_runs * 100.0)
            dark[m].append(s.mean_homes_dark)
            peak[m].append(s.mean_peak_pu)
        if progress is not None:
            progress((i + 1) / total, f"{field_name} = {v}  ({i + 1}/{total})")
    return SweepResult(field_name, list(values), modes, rate, dark, peak, base_config.mc_runs)
