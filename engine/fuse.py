"""Per-phase fuse model.

A fuse melts when enough heat accumulates in its element. We model the element
temperature as a first-order thermal system driven by I-squared heating and
cooled toward ambient -- a physically grounded surrogate for the fuse's
time-current (I2t) melting curve: it is inverse-time (bigger overloads melt
faster), it rides through brief surges (the element cools between them), and it
never melts at or below rated current. "Fuse-heat %" is the element temperature
expressed as a fraction of its melting temperature; the fuse blows at 100%.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np

# Representative IEC 60269-1 gG pre-arcing (melting) envelope in the sustained-
# overload region: current as a multiple of rated In, and pre-arcing time (s).
# This is a GENERIC gG shape (no manufacturer datasheet is bundled), labelled as
# the standard envelope -- cite IEC 60269-1, utilisation category gG. The first-
# order element surrogate is fitted to it near the operating point; a real gG
# curve is steeper than any first-order thermal model, so the two agree around
# ~2x In (where restart blow-outs occur) and diverge at the extremes -- the sub-
# second high-current end is energy, handled by the inrush I2t impulse, not tau.
IEC_GG_GATES = [(1.8, 600.0), (2.0, 300.0), (2.5, 120.0), (3.0, 40.0)]


def _model_melt_min(ratio, tau_min: float, melting_factor: float):
    """Pre-arcing time (min) from cold at a sustained current ``ratio`` = I/In."""
    r2 = np.asarray(ratio, dtype=float) ** 2
    mf2 = melting_factor ** 2
    with np.errstate(divide="ignore", invalid="ignore"):
        t = tau_min * np.log(r2 / (r2 - mf2))
    return np.where(r2 > mf2, t, np.inf)


@lru_cache(maxsize=1)
def fit_gg_params() -> "FuseParams":
    """Least-squares fit of (tau_min, melting_factor) so the surrogate's pre-arcing
    time passes through the gG envelope (IEC_GG_GATES). Cached -- the gates are
    constant. Best near the operating point; see IEC_GG_GATES for the caveat."""
    from scipy.optimize import least_squares

    r = np.array([g[0] for g in IEC_GG_GATES], dtype=float)
    t_min = np.array([g[1] / 60.0 for g in IEC_GG_GATES], dtype=float)

    def resid(x):
        return np.log(np.maximum(_model_melt_min(r, x[0], x[1]), 1e-9)) - np.log(t_min)

    sol = least_squares(resid, x0=[6.0, 1.45], bounds=([0.5, 1.1], [60.0, 1.70]))
    return FuseParams(melting_factor=float(sol.x[1]), tau_min=float(sol.x[0]))


@dataclass
class FuseParams:
    """Fuse thermal constants (per phase, all three phases identical)."""

    # Fusing factor: the continuous current, as a multiple of rated, that will
    # eventually melt the element. HRC fuses sit around 1.45-1.6. This sets the
    # melting *level*; it is a fuse property, not a tuning knob for results.
    melting_factor: float = 1.45
    # Element thermal time constant (min). Governs how fast heat builds: a 2x
    # overload melts a tight fuse in a few minutes, matching LV fuse curves.
    tau_min: float = 6.0


class FuseBank:
    """Three-phase fuse bank with independent per-phase heating."""

    def __init__(self, fuse_current_a: float, n_phases: int = 3, params: FuseParams | None = None) -> None:
        self.i_fuse = float(fuse_current_a)
        self.n = n_phases
        self.p = params or FuseParams()
        # Normalised element temperature rise. theta = (I/I_fuse)^2 at steady
        # state; melting occurs at theta_melt = melting_factor^2.
        self.theta = np.zeros(n_phases)
        self.theta_melt = self.p.melting_factor**2
        self.blown = np.zeros(n_phases, dtype=bool)
        self.blow_minute = np.full(n_phases, -1, dtype=int)

    @property
    def melting_current_a(self) -> float:
        """Continuous current that melts the fuse (A)."""
        return self.p.melting_factor * self.i_fuse

    def reset(self, pre_load_current_a: np.ndarray) -> None:
        """Seed the element at the steady state of the pre-outage load."""
        ratio = np.asarray(pre_load_current_a, dtype=float) / self.i_fuse
        self.theta = ratio**2
        self.blown[:] = False
        self.blow_minute[:] = -1

    def step(self, phase_current_a: np.ndarray, minute: int, dt_min: float) -> None:
        """Advance element heating one minute; latch any phase that reaches melt."""
        ratio = np.asarray(phase_current_a, dtype=float) / self.i_fuse
        theta_ss = ratio**2
        # First-order approach to the driven steady state.
        self.theta += (dt_min / self.p.tau_min) * (theta_ss - self.theta)
        self.theta = np.maximum(self.theta, 0.0)
        newly = (~self.blown) & (self.theta >= self.theta_melt)
        if np.any(newly):
            self.blown |= newly
            self.blow_minute[newly] = minute
        # A blown phase stays open (no further heating tracked meaningfully).
        self.theta[self.blown] = np.maximum(self.theta[self.blown], self.theta_melt)

    def heat_percent(self) -> np.ndarray:
        """Fuse-heat for each phase as a percentage of the melting level."""
        return 100.0 * self.theta / self.theta_melt

    def time_to_melt_min(self, phase_current_a: np.ndarray) -> np.ndarray:
        """Predicted minutes to melt at the given sustained current (inf if safe)."""
        ratio = np.asarray(phase_current_a, dtype=float) / self.i_fuse
        theta_ss = ratio**2
        out = np.full(self.n, np.inf)
        rising = theta_ss > self.theta_melt
        # theta(t) = theta_ss + (theta0 - theta_ss) e^{-t/tau}; solve for theta=theta_melt.
        with np.errstate(divide="ignore", invalid="ignore"):
            num = theta_ss[rising] - self.theta[rising]
            den = theta_ss[rising] - self.theta_melt
            out[rising] = self.p.tau_min * np.log(num / den)
        return out

    def time_current_curve(self, ratios: np.ndarray | None = None):
        """Modelled pre-arcing time (min) vs current (multiple of rated), from cold.
        For plotting the surrogate against the gG envelope (IEC_GG_GATES)."""
        if ratios is None:
            ratios = np.geomspace(self.p.melting_factor * 1.02, 10.0, 60)
        ratios = np.asarray(ratios, dtype=float)
        return ratios, _model_melt_min(ratios, self.p.tau_min, self.p.melting_factor)

    def any_blown(self) -> bool:
        return bool(np.any(self.blown))
