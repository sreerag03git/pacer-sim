"""Appliance profiles.

Each controllable appliance carries its own electrical rating and its own
PACER soft-start / back-off / floor parameters (Rules 3 and 5). Appliances fall
into two physical families:

  * thermal   -- air-conditioners, whose "demand" is driven by a room thermal
                 model (the room heats up during the outage, so at restoration
                 the thermostat calls for full cooling).
  * reservoir -- battery chargers, e-rickshaw chargers and water pumps, whose
                 "demand" is driven by a store (state-of-charge / tank level)
                 that depletes during the outage and so is near-empty at
                 restoration.

Both families produce the same effect: a strong, coincident call for power the
moment supply returns. PACER Core shapes *how* that call is served.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class ApplianceKind(enum.IntEnum):
    """Integer-coded appliance kinds (ints so they vectorise cleanly)."""

    INVERTER_AC = 0
    FIXED_AC = 1
    INVERTER_CHARGER = 2
    ERICKSHAW_CHARGER = 3
    WATER_PUMP = 4


# Families
THERMAL_KINDS = (ApplianceKind.INVERTER_AC, ApplianceKind.FIXED_AC)
RESERVOIR_KINDS = (
    ApplianceKind.INVERTER_CHARGER,
    ApplianceKind.ERICKSHAW_CHARGER,
    ApplianceKind.WATER_PUMP,
)


@dataclass(frozen=True)
class ApplianceParams:
    """Static physical and PACER-control parameters for one appliance kind.

    Powers are electrical real power at full duty (kW). The PACER fractions are
    the exact constants from the seven rules; they are NOT fitted.
    """

    kind: ApplianceKind
    label: str
    rated_kw: float  # real power drawn at full duty (kW)

    # Rule 3 -- soft start. The device's duty cap begins at ``soft_start_duty``
    # and ramps linearly to 1.0 over a 30-min window from its (randomised) start.
    soft_start_duty: float

    # Rule 5 -- back-off. On sensed stress the cap is multiplied by
    # ``backoff_multiplier`` and clamped to never fall below ``backoff_floor``.
    backoff_multiplier: float
    backoff_floor: float

    # Reservoir dynamics (ignored for thermal kinds). State x in [0, 1].
    #   charge_minutes       -- minutes at full duty to go empty -> full.
    #   outage_drain_minutes -- minutes of unserved outage to go full -> empty
    #                           (battery backing the home, tank being drawn down).
    #   normal_drain_minutes -- slow depletion while grid present (self-discharge
    #                           / trickle usage); drives gentle normal cycling.
    charge_minutes: float = 0.0
    outage_drain_minutes: float = 0.0
    normal_drain_minutes: float = 0.0


# --- the five appliance profiles -------------------------------------------------
# Ratings are typical Indian single-phase appliances. Soft-start / back-off
# fractions are the Rule 3 / Rule 5 constants verbatim (AC and pump treated as
# motor loads; both charger types treated as charger loads).
_PARAMS: dict[ApplianceKind, ApplianceParams] = {
    ApplianceKind.INVERTER_AC: ApplianceParams(
        kind=ApplianceKind.INVERTER_AC,
        label="Inverter AC",
        rated_kw=1.10,  # 1 to 1.5 ton inverter split, efficient running draw
        soft_start_duty=0.55,  # Rule 3: inverter AC 55%
        backoff_multiplier=0.75,  # Rule 5: AC x0.75
        backoff_floor=0.35,  # Rule 5: AC floor 0.35
    ),
    ApplianceKind.FIXED_AC: ApplianceParams(
        kind=ApplianceKind.FIXED_AC,
        label="Fixed-speed AC",
        rated_kw=1.50,  # fixed-speed compressor, higher running draw
        soft_start_duty=0.55,  # Rule 3: fixed-speed AC 55%
        backoff_multiplier=0.75,  # Rule 5: AC x0.75
        backoff_floor=0.35,  # Rule 5: AC floor 0.35
    ),
    ApplianceKind.INVERTER_CHARGER: ApplianceParams(
        kind=ApplianceKind.INVERTER_CHARGER,
        label="Inverter / battery charger",
        rated_kw=0.60,  # home inverter battery recharge
        soft_start_duty=0.30,  # Rule 3: chargers 30%
        backoff_multiplier=0.50,  # Rule 5: charger x0.5
        backoff_floor=0.00,  # Rule 5: charger floor 0
        charge_minutes=50.0,  # ~50 min full-duty recharge from empty
        outage_drain_minutes=95.0,  # battery backs the home; drained within ~95 min of outage
        normal_drain_minutes=1440.0,  # slow self-discharge while grid present (24 h)
    ),
    ApplianceKind.ERICKSHAW_CHARGER: ApplianceParams(
        kind=ApplianceKind.ERICKSHAW_CHARGER,
        label="E-rickshaw charger",
        rated_kw=1.20,  # lead-acid / Li pack charger
        soft_start_duty=0.30,  # Rule 3: chargers 30%
        backoff_multiplier=0.50,  # Rule 5: charger x0.5
        backoff_floor=0.00,  # Rule 5: charger floor 0
        charge_minutes=240.0,  # long full charge (traction pack)
        outage_drain_minutes=1e6,  # does not deplete during the cut; it simply could not charge
        normal_drain_minutes=1e6,  # modelled via low initial state at the evening cut
    ),
    ApplianceKind.WATER_PUMP: ApplianceParams(
        kind=ApplianceKind.WATER_PUMP,
        label="Water pump",
        rated_kw=0.75,  # 1 HP monoblock
        soft_start_duty=0.55,  # motor soft start (treated as a motor load)
        backoff_multiplier=0.75,  # treated as a motor load
        backoff_floor=0.35,
        charge_minutes=20.0,  # fills the overhead tank quickly
        outage_drain_minutes=300.0,  # household draw empties the tank over ~5 h
        normal_drain_minutes=420.0,  # steady daytime usage drives gentle cycling
    ),
}


def params(kind: ApplianceKind) -> ApplianceParams:
    return _PARAMS[kind]


def all_params() -> dict[ApplianceKind, ApplianceParams]:
    return dict(_PARAMS)
