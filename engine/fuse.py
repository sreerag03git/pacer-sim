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

import numpy as np


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

    def any_blown(self) -> bool:
        return bool(np.any(self.blown))
