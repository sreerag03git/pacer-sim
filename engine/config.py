"""Immutable simulation configuration.

Every physical quantity is named and carries its unit in the comment. Nothing
here is tuned to reproduce a particular headline figure; the defaults describe a
plausible, overloaded Indian LV distribution transformer and the appliance mix
behind the evening restart surge.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field, replace
from typing import Optional


class ControllerMode(str, enum.Enum):
    """The three controller modes compared on identical scenarios."""

    BASELINE = "baseline"  # every stabiliser waits a fixed 3 min, then full power in lockstep
    PACER = "pacer"  # PACER Core (seven rules) inside every device, local sensing only
    PACER_BEACON = "pacer_beacon"  # PACER Core + per-transformer Beacon guidance

    @property
    def label(self) -> str:
        return {
            ControllerMode.BASELINE: "Baseline",
            ControllerMode.PACER: "PACER only",
            ControllerMode.PACER_BEACON: "PACER + Beacon",
        }[self]


class HeatwavePreset(str, enum.Enum):
    """Ambient temperature presets. Peak values are the afternoon maximum (degC).

    The default scenario uses HOT (42 C): the published PACER figures are stated
    to hold "even in simulated 42-45 C heatwaves", so a 42 C peak-summer evening
    is the low end of that stated band and the faithful headline scenario.
    """

    MILD = "mild"  # 34 C peak -- a warm post-monsoon evening
    HOT = "hot"  # 42 C peak -- peak-summer evening (the canonical load-shedding scenario)
    HEATWAVE = "heatwave"  # 46 C peak -- a declared heatwave

    @property
    def peak_c(self) -> float:
        return {
            HeatwavePreset.MILD: 34.0,
            HeatwavePreset.HOT: 42.0,
            HeatwavePreset.HEATWAVE: 46.0,
        }[self]


@dataclass(frozen=True)
class Config:
    """A complete, immutable scenario description.

    One ``Config`` fully determines a Monte Carlo experiment: identical seed +
    identical Config reproduce byte-identical results.
    """

    # --- controller under test -------------------------------------------------
    mode: ControllerMode = ControllerMode.BASELINE

    # --- population ------------------------------------------------------------
    homes: int = 200  # number of homes on the one transformer
    phases: int = 3  # three-phase LV feeder

    # Appliance penetration (fraction of homes that own the appliance). Not every
    # home has every appliance -- these are the loads that cause the restart surge.
    ac_penetration: float = 0.60  # homes with any air-conditioner
    inverter_ac_share: float = 0.45  # of AC homes, fraction that are inverter (vs fixed-speed) type
    charger_penetration: float = 0.40  # homes with an inverter / battery backup charger
    erickshaw_penetration: float = 0.12  # homes that charge an e-rickshaw
    pump_penetration: float = 0.35  # homes with a water pump
    vulnerable_fraction: float = 0.08  # homes registered as heat-vulnerable (Rule 7 priority)

    # Uncontrolled base load per home (lights, fans, fridge), kW. This load is NOT
    # paced -- it returns immediately on restoration and sets the floor.
    base_load_kw_per_home: float = 0.18

    # --- transformer & protection ---------------------------------------------
    # 160 kVA for 200 homes: under normal diversified evening load the unit
    # already runs near its rating (this is what "an overloaded transformer"
    # means), and the coincident post-outage restart then drives it to roughly
    # twice rating. The rating is an honest scenario choice, not a knob tuned to
    # any headline figure.
    nameplate_kva: float = 160.0  # transformer nameplate rating (kVA)
    v_ln: float = 240.0  # nominal line-to-neutral voltage (V)
    power_factor: float = 0.90  # aggregate displacement power factor (lagging)

    # Protective fuse. ``fuse_rating_a`` is the per-phase fuse rated current (A).
    # If left None it is derived from the nameplate and ``fuse_tightness``:
    # tightness 1.0 means the fuse is rated exactly at transformer rated current
    # ("tight fuse"); >1 is a looser fuse, <1 an over-tight one.
    fuse_rating_a: Optional[float] = None
    fuse_tightness: float = 1.0

    # --- event timeline (minutes) ----------------------------------------------
    warmup_minutes: int = 180  # normal operation before the cut (learner trains here)
    outage_minutes: int = 120  # duration of the load-shedding block
    recovery_minutes: int = 240  # observation window after power is restored
    day_start_minute: int = 15 * 60  # wall-clock minute-of-day at which warmup begins (15:00)

    # --- weather ---------------------------------------------------------------
    heatwave: HeatwavePreset = HeatwavePreset.HOT
    # Optional explicit afternoon-peak ambient (degC). When set it overrides the
    # preset, so the UI can expose a continuous temperature control.
    ambient_peak_c: Optional[float] = None
    ambient_night_c: float = 26.0  # pre-dawn minimum (degC); diurnal swing runs between this and the peak

    # --- Monte Carlo & determinism ---------------------------------------------
    mc_runs: int = 200  # randomised trials per scenario
    seed: int = 7  # master seed; same seed + same Config => byte-identical results

    # ---------------------------------------------------------------------------
    @property
    def dt_min(self) -> float:
        """Simulation time step (minutes). Fixed at 1 minute per the spec."""
        return 1.0

    @property
    def total_minutes(self) -> int:
        return self.warmup_minutes + self.outage_minutes + self.recovery_minutes

    @property
    def outage_start(self) -> int:
        """Index (minute) at which the cut begins."""
        return self.warmup_minutes

    @property
    def restore_minute(self) -> int:
        """Index (minute) at which power is restored."""
        return self.warmup_minutes + self.outage_minutes

    @property
    def outage_hours(self) -> float:
        return self.outage_minutes / 60.0

    @property
    def peak_ambient_c(self) -> float:
        """Afternoon-peak ambient actually used (explicit override, else preset)."""
        return self.ambient_peak_c if self.ambient_peak_c is not None else self.heatwave.peak_c

    @property
    def rated_phase_current_a(self) -> float:
        """Per-phase rated current (A) at nameplate, single-phase L-N basis.

        I_rated = (S_rated / phases) / V_LN. Current is apparent-power based, so
        the power factor does not enter here.
        """
        return (self.nameplate_kva * 1000.0 / self.phases) / self.v_ln

    @property
    def fuse_current_a(self) -> float:
        """Effective per-phase fuse rated current (A)."""
        if self.fuse_rating_a is not None:
            return float(self.fuse_rating_a)
        return self.fuse_tightness * self.rated_phase_current_a

    def key(self) -> tuple:
        """A hashable signature of the whole scenario (mode excluded), suitable as
        a cache key. Two configs with the same key produce identical Monte Carlo
        results."""
        return (
            self.homes,
            self.phases,
            round(self.ac_penetration, 6),
            round(self.inverter_ac_share, 6),
            round(self.charger_penetration, 6),
            round(self.erickshaw_penetration, 6),
            round(self.pump_penetration, 6),
            round(self.vulnerable_fraction, 6),
            round(self.base_load_kw_per_home, 6),
            round(self.nameplate_kva, 6),
            round(self.v_ln, 6),
            round(self.power_factor, 6),
            None if self.fuse_rating_a is None else round(self.fuse_rating_a, 6),
            round(self.fuse_tightness, 6),
            self.warmup_minutes,
            self.outage_minutes,
            self.recovery_minutes,
            self.day_start_minute,
            self.heatwave.value,
            None if self.ambient_peak_c is None else round(self.ambient_peak_c, 6),
            round(self.ambient_night_c, 6),
            self.mc_runs,
            self.seed,
        )

    def with_mode(self, mode: ControllerMode) -> "Config":
        """Return a copy identical in every respect but the controller mode.

        Used to compare the three modes on *identical* scenarios.
        """
        return replace(self, mode=mode)

    def validate(self) -> list[str]:
        """Return a list of human-readable problems; empty means valid."""
        problems: list[str] = []
        if self.homes < 1:
            problems.append("homes must be at least 1.")
        if not (0.0 <= self.ac_penetration <= 1.0):
            problems.append("AC penetration must be between 0 and 100%.")
        if not (0.0 <= self.inverter_ac_share <= 1.0):
            problems.append("Inverter-AC share must be between 0 and 100%.")
        for name, val in (
            ("charger penetration", self.charger_penetration),
            ("e-rickshaw penetration", self.erickshaw_penetration),
            ("pump penetration", self.pump_penetration),
            ("vulnerable fraction", self.vulnerable_fraction),
        ):
            if not (0.0 <= val <= 1.0):
                problems.append(f"{name} must be between 0 and 100%.")
        if self.nameplate_kva <= 0:
            problems.append("Transformer nameplate rating must be positive.")
        if self.fuse_current_a <= 0:
            problems.append("Fuse rating must be positive.")
        if self.outage_minutes < 0:
            problems.append("Outage duration cannot be negative.")
        if self.mc_runs < 1:
            problems.append("Monte Carlo run count must be at least 1.")
        if self.warmup_minutes < 60:
            problems.append("Warm-up must be at least 60 min so the voltage learner has data.")
        return problems
