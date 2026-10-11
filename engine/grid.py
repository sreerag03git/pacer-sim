"""Low-voltage feeder electrical model.

Homes are split across three phases and strung along a radial LV feeder. Each
home sits behind a short series impedance, so the voltage at a home is the
nominal secondary voltage minus the accumulated drop from every ampere flowing
through the segments upstream of it. Aggregate load therefore *physically*
produces the per-home voltage sag that PACER Rule 4 senses -- and because the
drop scales with load, a weak feeder can sag toward ~190 V under the restart
surge, exactly where relative (not absolute) sensing is needed.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class FeederParams:
    """Per-home and source series impedances (ohms, resistive LV approximation)."""

    # Series impedance of the segment feeding each home. Calibrated so the far
    # end of a loaded phase sags ~25 V at rated and toward ~190 V at ~2x load.
    z_per_home_ohm: float = 0.0030
    z_per_home_spread: float = 0.0008  # +/- uniform spread so the feeder is not perfectly uniform
    # Common upstream impedance per phase (transformer secondary + service main).
    z_source_ohm: float = 0.020


class FeederModel:
    """Radial three-phase LV feeder with per-home voltage computation."""

    def __init__(
        self,
        home_phase: np.ndarray,
        v_ln: float,
        power_factor: float,
        rng: np.random.Generator,
        params: FeederParams | None = None,
    ) -> None:
        """
        home_phase : int array (0..2) giving each home's phase.
        """
        self.p = params or FeederParams()
        self.v_ln = float(v_ln)
        self.pf = float(power_factor)
        self.home_phase = np.asarray(home_phase, dtype=int)
        self.n_homes = self.home_phase.size
        self.n_phases = 3

        # Per-home segment impedance with mild spatial spread.
        self.z_home = self.p.z_per_home_ohm + rng.uniform(
            -self.p.z_per_home_spread, self.p.z_per_home_spread, self.n_homes
        )
        self.z_home = np.maximum(self.z_home, 1e-4)

        # Order homes along each phase feeder (position = order of appearance).
        self._phase_order: list[np.ndarray] = []
        self._z_cum_upstream = np.zeros(self.n_homes)  # true upstream path impedance per home
        for ph in range(self.n_phases):
            idx = np.nonzero(self.home_phase == ph)[0]
            self._phase_order.append(idx)
            # Upstream path impedance = source + sum of own + nearer segments.
            z_seg = self.z_home[idx]
            self._z_cum_upstream[idx] = self.p.z_source_ohm + np.cumsum(z_seg)

    def home_upstream_impedance(self) -> np.ndarray:
        """True Thevenin impedance seen at each home (the quantity Rule 4 estimates)."""
        return self._z_cum_upstream.copy()

    def phase_currents(self, home_power_kw: np.ndarray) -> np.ndarray:
        """Per-phase aggregate line current (A) from per-home real power."""
        i_home = home_power_kw * 1000.0 / (self.v_ln * self.pf)
        out = np.zeros(self.n_phases)
        for ph in range(self.n_phases):
            out[ph] = i_home[self._phase_order[ph]].sum()
        return out

    def home_voltages(self, home_power_kw: np.ndarray) -> np.ndarray:
        """Per-home line-to-neutral voltage (V) under the given load."""
        i_home = home_power_kw * 1000.0 / (self.v_ln * self.pf)
        v = np.full(self.n_homes, self.v_ln)
        for ph in range(self.n_phases):
            idx = self._phase_order[ph]
            if idx.size == 0:
                continue
            i_ord = i_home[idx]
            z_ord = self.z_home[idx]
            # Downstream current through each segment = suffix sum of home currents.
            downstream = np.cumsum(i_ord[::-1])[::-1]
            phase_total = downstream[0] if downstream.size else 0.0
            # Common source drop + accumulated per-segment drop.
            drop = self.p.z_source_ohm * phase_total + np.cumsum(downstream * z_ord)
            v[idx] = self.v_ln - drop
        return v

    def representative_home(self) -> int:
        """Index of a far-ish home on the most loaded phase, for display."""
        # Pick the last home on phase 0's feeder as a representative weak point.
        order0 = self._phase_order[0]
        if order0.size:
            return int(order0[-1])
        return 0
