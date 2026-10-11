"""Thermal models: transformer (IEC 60076-7), room (two-node), and ambient.

The transformer thermal model sits behind an abstract interface so an
alternative loading guide (IEEE C57.91 is provided as a second implementation)
can be swapped in without touching the grid, fuse or controller code.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass

import numpy as np

# -------------------------------------------------------------------------------
# Ambient weather
# -------------------------------------------------------------------------------


def ambient_series(
    total_minutes: int,
    day_start_minute: int,
    peak_c: float,
    night_c: float,
) -> np.ndarray:
    """Diurnal ambient temperature (degC) for each simulated minute.

    A simple sinusoid between the pre-dawn minimum (around 05:00) and the
    afternoon maximum (around 15:00). Good enough to drive room heating and the
    transformer's ambient term; the exact curve is not safety-critical.
    """
    minutes = day_start_minute + np.arange(total_minutes)
    minute_of_day = minutes % 1440
    mean = 0.5 * (peak_c + night_c)
    amp = 0.5 * (peak_c - night_c)
    # peak at 15:00 (900 min): cosine with its max shifted to 900.
    phase = 2.0 * np.pi * (minute_of_day - 900.0) / 1440.0
    return mean + amp * np.cos(phase)


# -------------------------------------------------------------------------------
# Transformer thermal -- swappable interface
# -------------------------------------------------------------------------------


class TransformerThermalModel(abc.ABC):
    """Interface for a transformer hot-spot / ageing model.

    Implementations advance one 1-minute step given the per-unit load and the
    ambient temperature, exposing top-oil and hot-spot temperatures and the
    accumulated insulation ageing. Any standard that can produce these from load
    and ambient can be dropped in.
    """

    top_oil_c: float
    hot_spot_c: float
    ageing_hours: float  # accumulated equivalent ageing (hours at 98 degC reference)

    @abc.abstractmethod
    def reset(self, ambient_c: float) -> None:
        ...

    @abc.abstractmethod
    def step(self, load_pu: float, ambient_c: float, dt_min: float) -> None:
        ...

    @property
    def name(self) -> str:
        return self.__class__.__name__


@dataclass
class IECThermalParams:
    """IEC 60076-7 constants for an ONAN distribution transformer.

    Values follow the distribution-transformer row of IEC 60076-7:2018,
    clause 8.2 / Annex. They are standard constants, not fitted quantities.
    """

    delta_theta_or: float = 55.0  # top-oil rise over ambient at rated load (K)
    delta_theta_hr: float = 23.0  # hot-spot-to-top-oil gradient at rated current (K)
    R: float = 5.0  # ratio of load loss to no-load loss at rated
    x: float = 0.8  # oil exponent
    y: float = 1.6  # winding exponent
    k11: float = 1.0  # thermal model constant
    k21: float = 1.0  # thermal model constant (=1 => single-exponential hot-spot)
    k22: float = 2.0  # thermal model constant
    tau_o: float = 180.0  # oil time constant (min)
    tau_w: float = 4.0  # winding time constant (min)
    hot_spot_reference_c: float = 98.0  # reference hot-spot for ageing (thermally upgraded paper)
    ageing_halving_k: float = 6.0  # +6 K doubles the ageing rate (IEC)


class IECThermalModel(TransformerThermalModel):
    """IEC 60076-7 top-oil + hot-spot difference-equation model with ageing.

    State variables follow the standard's exponential (difference-equation)
    solution advanced at 1-min steps.
    """

    def __init__(self, params: IECThermalParams | None = None) -> None:
        self.p = params or IECThermalParams()
        self._theta_o = 0.0  # top-oil rise over ambient (K)
        self._theta_h1 = 0.0  # first hot-spot gradient component (K)
        self._theta_h2 = 0.0  # second hot-spot gradient component (K)
        self._ambient = 0.0
        self.top_oil_c = 0.0
        self.hot_spot_c = 0.0
        self.ageing_hours = 0.0

    def reset(self, ambient_c: float) -> None:
        p = self.p
        self._ambient = ambient_c
        # Start from the steady state of a typical pre-outage diversified load
        # (~0.75 pu) so the model does not open cold.
        k0 = 0.75
        self._theta_o = p.delta_theta_or * ((1 + p.R * k0 * k0) / (1 + p.R)) ** p.x
        self._theta_h1 = p.delta_theta_hr * k0**p.y
        self._theta_h2 = 0.0
        self._recompute(ambient_c)
        self.ageing_hours = 0.0

    def step(self, load_pu: float, ambient_c: float, dt_min: float) -> None:
        p = self.p
        k = max(load_pu, 0.0)

        # Top-oil: D(theta_o) = dt/(k11*tau_o) * [ steady_rise - theta_o ]
        steady_oil = p.delta_theta_or * ((1 + p.R * k * k) / (1 + p.R)) ** p.x
        self._theta_o += (dt_min / (p.k11 * p.tau_o)) * (steady_oil - self._theta_o)

        # Hot-spot gradient (two components per IEC; with k21=1 the second is zero).
        steady_grad = p.delta_theta_hr * k**p.y
        self._theta_h1 += (dt_min / (p.k22 * p.tau_w)) * (
            p.k21 * steady_grad - self._theta_h1
        )
        self._theta_h2 += (dt_min / (p.tau_o / p.k22)) * (
            (p.k21 - 1.0) * steady_grad - self._theta_h2
        )

        self._recompute(ambient_c)

        # Insulation ageing: relative rate V = 2^((theta_h - 98)/6); accumulate hours.
        v = 2.0 ** ((self.hot_spot_c - p.hot_spot_reference_c) / p.ageing_halving_k)
        self.ageing_hours += v * (dt_min / 60.0)

    def _recompute(self, ambient_c: float) -> None:
        self._ambient = ambient_c
        delta_h = self._theta_h1 - self._theta_h2
        self.top_oil_c = ambient_c + self._theta_o
        self.hot_spot_c = ambient_c + self._theta_o + delta_h


class IEEEThermalModel(TransformerThermalModel):
    """IEEE C57.91 clause-7 top-oil + hot-spot model (alternative standard).

    Provided to demonstrate that the thermal interface is genuinely swappable.
    Uses the C57.91 exponential forms with distribution-class constants.
    """

    def __init__(
        self,
        top_oil_rise_rated: float = 55.0,  # top-oil rise at rated (degC)
        hot_spot_rise_rated: float = 25.0,  # hot-spot over top-oil at rated (degC)
        tau_oil: float = 180.0,  # oil time constant (min)
        tau_wind: float = 5.0,  # winding time constant (min)
        n: float = 0.8,  # oil exponent
        m: float = 0.8,  # winding exponent
        loss_ratio: float = 5.0,  # R
        hot_spot_reference_c: float = 98.0,
        ageing_halving_k: float = 6.0,
    ) -> None:
        self.top_oil_rise_rated = top_oil_rise_rated
        self.hot_spot_rise_rated = hot_spot_rise_rated
        self.tau_oil = tau_oil
        self.tau_wind = tau_wind
        self.n = n
        self.m = m
        self.R = loss_ratio
        self.ref = hot_spot_reference_c
        self.halving = ageing_halving_k
        self._oil_rise = 0.0
        self._hs_rise = 0.0
        self.top_oil_c = 0.0
        self.hot_spot_c = 0.0
        self.ageing_hours = 0.0

    def reset(self, ambient_c: float) -> None:
        k0 = 0.75
        self._oil_rise = self.top_oil_rise_rated * ((1 + self.R * k0 * k0) / (1 + self.R)) ** self.n
        self._hs_rise = self.hot_spot_rise_rated * k0 ** (2 * self.m)
        self.top_oil_c = ambient_c + self._oil_rise
        self.hot_spot_c = self.top_oil_c + self._hs_rise
        self.ageing_hours = 0.0

    def step(self, load_pu: float, ambient_c: float, dt_min: float) -> None:
        k = max(load_pu, 0.0)
        ult_oil = self.top_oil_rise_rated * ((1 + self.R * k * k) / (1 + self.R)) ** self.n
        self._oil_rise += (dt_min / self.tau_oil) * (ult_oil - self._oil_rise)
        ult_hs = self.hot_spot_rise_rated * k ** (2 * self.m)
        self._hs_rise += (dt_min / self.tau_wind) * (ult_hs - self._hs_rise)
        self.top_oil_c = ambient_c + self._oil_rise
        self.hot_spot_c = self.top_oil_c + self._hs_rise
        v = 2.0 ** ((self.hot_spot_c - self.ref) / self.halving)
        self.ageing_hours += v * (dt_min / 60.0)


# -------------------------------------------------------------------------------
# Room two-node thermal model (vectorised across AC homes)
# -------------------------------------------------------------------------------


@dataclass
class RoomParams:
    """Lumped two-node (air + mass) room thermal parameters.

    Expressed directly as time constants and rates in minutes / degC so the
    model needs no unit juggling. Values give a hot flat that rises several
    degrees above setpoint during a two-hour evening cut and that a working AC
    can pull back down in ~15-20 min.
    """

    setpoint_c: float = 25.0  # thermostat setpoint
    deadband_c: float = 1.0  # +/- band around setpoint
    tau_env_min: float = 110.0  # air <-> outdoor coupling time constant (min)
    tau_mass_air_min: float = 55.0  # air <-> internal mass coupling (min)
    tau_mass_min: float = 200.0  # mass <-> air (slow) coupling (min)
    internal_gain_c_per_min: float = 0.010  # occupants + background appliances (degC/min)
    cool_rate_c_per_min: float = 0.26  # indoor cooling at full AC duty (degC/min)


class RoomModel:
    """Vectorised two-node room model, one entry per air-conditioned home."""

    def __init__(self, n_rooms: int, params: RoomParams | None = None) -> None:
        self.n = n_rooms
        self.p = params or RoomParams()
        self.t_air = np.zeros(n_rooms)
        self.t_mass = np.zeros(n_rooms)

    def reset(self, ambient_c: float, rng: np.random.Generator) -> None:
        """Initialise near the setpoint (AC has been running before the cut)."""
        p = self.p
        self.t_air = p.setpoint_c + rng.uniform(-0.5, 0.8, self.n)
        self.t_mass = self.t_air + rng.uniform(0.0, 0.6, self.n)

    def step(self, ac_duty: np.ndarray, ambient_c: float, dt_min: float) -> None:
        """Advance one minute. ``ac_duty`` in [0,1] is the served cooling duty."""
        p = self.p
        d_air = (
            (ambient_c - self.t_air) / p.tau_env_min
            + (self.t_mass - self.t_air) / p.tau_mass_air_min
            + p.internal_gain_c_per_min
            - p.cool_rate_c_per_min * ac_duty
        )
        d_mass = (self.t_air - self.t_mass) / p.tau_mass_min
        self.t_air = self.t_air + dt_min * d_air
        self.t_mass = self.t_mass + dt_min * d_mass

    def cooling_demand(self) -> np.ndarray:
        """Thermostat call for cooling in [0,1] (proportional across the deadband)."""
        p = self.p
        lo = p.setpoint_c - p.deadband_c
        return np.clip((self.t_air - lo) / (2.0 * p.deadband_c), 0.0, 1.0)
