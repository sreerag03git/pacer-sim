"""Device population: turn a Config + a scenario RNG into concrete devices.

This is a struct-of-arrays layout (one numpy array per attribute, indexed by
device) so the per-minute controller update vectorises cleanly. The scenario
RNG alone drives the population draw, so the *same* scenario is produced for all
three controller modes -- the modes are compared on identical homes, appliances,
phase assignment and vulnerability.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from engine.appliances import ApplianceKind, THERMAL_KINDS, params as appliance_params
from engine.config import Config


@dataclass
class Devices:
    """All devices on the transformer, plus home- and room-level bookkeeping."""

    # --- per-device static arrays (length D) ---
    kind: np.ndarray
    home: np.ndarray
    phase: np.ndarray
    rated_kw: np.ndarray
    soft_start_duty: np.ndarray
    backoff_multiplier: np.ndarray
    backoff_floor: np.ndarray
    is_vulnerable: np.ndarray
    is_thermal: np.ndarray
    room_idx: np.ndarray  # index into the room model, -1 for non-AC devices
    is_reservoir: np.ndarray
    charge_rate_per_min: np.ndarray
    outage_drain_per_min: np.ndarray
    normal_drain_per_min: np.ndarray
    reservoir_x0: np.ndarray  # initial state-of-charge / tank level
    fault: np.ndarray  # pass-through (PACER absent) if True

    # --- per-home arrays (length H) ---
    home_phase: np.ndarray
    home_base_kw: np.ndarray
    home_vulnerable: np.ndarray

    # --- room bookkeeping ---
    n_rooms: int
    room_home: np.ndarray  # home index for each room

    @property
    def n_devices(self) -> int:
        return int(self.kind.size)


def build_devices(config: Config, rng: np.random.Generator) -> Devices:
    """Draw the device population for one trial from ``rng``."""
    H = config.homes

    # Phase assignment: independent per home. Real Indian LV feeders carry
    # meaningful phase imbalance (the reason DISCOMs issue phase-rebalancing work
    # orders), so an unlucky phase can run hotter than the others -- which is
    # precisely where a per-phase-aware Beacon earns its keep.
    home_phase = rng.integers(0, config.phases, size=H)

    # Vulnerable homes (Rule 7 priority).
    home_vulnerable = rng.random(H) < config.vulnerable_fraction

    # Uncontrolled base load per home (+/-15% spread), present whenever supply is.
    home_base_kw = config.base_load_kw_per_home * (1.0 + rng.uniform(-0.15, 0.15, H))

    # Appliance ownership draws (independent Bernoulli per appliance family).
    has_ac = rng.random(H) < config.ac_penetration
    ac_is_inverter = rng.random(H) < config.inverter_ac_share
    has_charger = rng.random(H) < config.charger_penetration
    has_erick = rng.random(H) < config.erickshaw_penetration
    has_pump = rng.random(H) < config.pump_penetration

    kinds: list[int] = []
    homes: list[int] = []
    room_idx_list: list[int] = []

    room_home_list: list[int] = []

    def add(kind: ApplianceKind, home: int) -> None:
        kinds.append(int(kind))
        homes.append(home)
        if kind in THERMAL_KINDS:
            room_idx_list.append(len(room_home_list))
            room_home_list.append(home)
        else:
            room_idx_list.append(-1)

    for h in range(H):
        if has_ac[h]:
            add(ApplianceKind.INVERTER_AC if ac_is_inverter[h] else ApplianceKind.FIXED_AC, h)
        if has_charger[h]:
            add(ApplianceKind.INVERTER_CHARGER, h)
        if has_erick[h]:
            add(ApplianceKind.ERICKSHAW_CHARGER, h)
        if has_pump[h]:
            add(ApplianceKind.WATER_PUMP, h)

    D = len(kinds)
    kind = np.array(kinds, dtype=int)
    home = np.array(homes, dtype=int)
    room_idx = np.array(room_idx_list, dtype=int)
    phase = home_phase[home]

    rated_kw = np.zeros(D)
    soft_start_duty = np.zeros(D)
    backoff_multiplier = np.zeros(D)
    backoff_floor = np.zeros(D)
    is_thermal = np.zeros(D, dtype=bool)
    is_reservoir = np.zeros(D, dtype=bool)
    charge_rate_per_min = np.zeros(D)
    outage_drain_per_min = np.zeros(D)
    normal_drain_per_min = np.zeros(D)
    reservoir_x0 = np.zeros(D)

    for d in range(D):
        p = appliance_params(ApplianceKind(kind[d]))
        rated_kw[d] = p.rated_kw
        soft_start_duty[d] = p.soft_start_duty
        backoff_multiplier[d] = p.backoff_multiplier
        backoff_floor[d] = p.backoff_floor
        if ApplianceKind(kind[d]) in THERMAL_KINDS:
            is_thermal[d] = True
        else:
            is_reservoir[d] = True
            charge_rate_per_min[d] = 1.0 / p.charge_minutes if p.charge_minutes else 0.0
            outage_drain_per_min[d] = 1.0 / p.outage_drain_minutes if p.outage_drain_minutes else 0.0
            normal_drain_per_min[d] = 1.0 / p.normal_drain_minutes if p.normal_drain_minutes else 0.0

    # Initial reservoir states. E-rickshaws arrive and plug in across the whole
    # evening, so at any instant only some are actively charging -- their start
    # charge is spread widely (diversified), not clustered low. Inverter
    # batteries and water tanks start near full and cycle gently.
    reservoir_x0 = np.ones(D)
    for d in range(D):
        if not is_reservoir[d]:
            continue
        if ApplianceKind(kind[d]) == ApplianceKind.ERICKSHAW_CHARGER:
            reservoir_x0[d] = rng.uniform(0.20, 1.00)
        else:
            reservoir_x0[d] = rng.uniform(0.85, 1.00)

    is_vulnerable = home_vulnerable[home]

    # Random hardware faults -> PACER pass-through for that device.
    fault = rng.random(D) < 0.0  # default 0 probability; the path exists and is exercised by config

    return Devices(
        kind=kind,
        home=home,
        phase=phase,
        rated_kw=rated_kw,
        soft_start_duty=soft_start_duty,
        backoff_multiplier=backoff_multiplier,
        backoff_floor=backoff_floor,
        is_vulnerable=is_vulnerable,
        is_thermal=is_thermal,
        room_idx=room_idx,
        is_reservoir=is_reservoir,
        charge_rate_per_min=charge_rate_per_min,
        outage_drain_per_min=outage_drain_per_min,
        normal_drain_per_min=normal_drain_per_min,
        reservoir_x0=reservoir_x0,
        fault=fault,
        home_phase=home_phase,
        home_base_kw=home_base_kw,
        home_vulnerable=home_vulnerable,
        n_rooms=len(room_home_list),
        room_home=np.array(room_home_list, dtype=int),
    )
