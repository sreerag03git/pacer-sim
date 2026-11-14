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

from engine.loadflow import solve_feeder


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
        use_reactance: bool = False,
        xr_cable: float = 0.4,
        xr_transformer: float = 5.0,
        tx_percent_z: float = 4.5,
        tx_tap_pu: float = 1.0,
        nameplate_kva: float = 160.0,
        home_np: np.ndarray | None = None,
        home_nq: np.ndarray | None = None,
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
        # Four-wire load-flow outputs (0 unless use_reactance, set per solve).
        self.use_reactance = bool(use_reactance)
        self.i_neutral_mag = 0.0
        self.vuf_pct = 0.0

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

        if self.use_reactance:
            self._tan_phi = float(np.tan(np.arccos(self.pf)))
            self._v_ln_eff = self.v_ln * float(tx_tap_pu)
            order = np.argsort(self._z_cum_upstream)  # one shared 4-wire route, near->far
            self._route_order = order
            self._route_phase = self.home_phase[order]
            # the shared route carries all three phases' homes, so per-segment Z is
            # ~1/3 of the per-home resistive segment -- this keeps the end-to-end
            # feeder impedance (and so the voltage sag) comparable to the calibrated
            # resistive model, on top of which the neutral shift and VUF emerge.
            r_seg = self.z_home[order] / 3.0
            self._z_seg = r_seg * (1.0 + 1j * float(xr_cable))
            z_base = self.v_ln ** 2 / max(nameplate_kva * 1000.0 / 3.0, 1e-6)
            r_src = (tx_percent_z / 100.0) * z_base / np.sqrt(1.0 + xr_transformer ** 2)
            self._z_src = complex(r_src * (1.0 + 1j * float(xr_transformer)))
            zeros = np.zeros(self.n_homes)
            self._np_route = (zeros if home_np is None else np.asarray(home_np, dtype=float))[order]
            self._nq_route = (zeros if home_nq is None else np.asarray(home_nq, dtype=float))[order]

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

    def _home_voltages_reactive(self, home_power_kw: np.ndarray) -> np.ndarray:
        """Four-wire unbalanced load flow: |V| per home, plus neutral current & VUF."""
        p0 = np.asarray(home_power_kw, dtype=float)[self._route_order] * 1000.0  # W
        sol = solve_feeder(
            self._route_phase, self._z_seg, self._z_seg, self._z_src, self._z_src,
            p0, p0 * self._tan_phi, self._np_route, self._nq_route, self._v_ln_eff,
        )
        self.i_neutral_mag = float(abs(sol.i_neutral_src))
        self.vuf_pct = float(sol.vuf_pct)
        v = np.empty(self.n_homes)
        v[self._route_order] = np.abs(sol.v_home)
        return v

    def home_voltages(self, home_power_kw: np.ndarray) -> np.ndarray:
        """Per-home line-to-neutral voltage (V) under the given load."""
        if self.use_reactance:
            return self._home_voltages_reactive(home_power_kw)
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
