"""One deterministic minute-by-minute trial.

This is the orchestration layer: it builds the device population, the feeder, the
rooms, the transformer thermal model and the fuse bank, then advances the whole
system one minute at a time through warm-up -> outage -> recovery, driving the
controller for the configured mode. It owns no physics of its own; it wires the
model components together and records the result.

Determinism: all randomness is drawn from two generators seeded purely from
(master seed, trial index). The *scenario* generator (population, phase
assignment, weather noise) is independent of the controller mode, so the three
modes are compared on byte-identically the same scenario.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from engine.beacon import Beacon
from engine.config import Config, ControllerMode
from engine.devices import build_devices
from engine.fuse import FuseBank
from engine.grid import FeederModel
from engine.pacer_core import PacerController
from engine.thermal import IECThermalModel, RoomModel, RoomParams, ambient_series

# Reservoir thermostat deadband: demand saturates once the store is >15% depleted.
_RESERVOIR_DEADBAND = 0.15
_HEAT_EXPOSURE_C = 32.0  # indoor temperature above which occupants are "in heat"
# Pre-roll length to settle rooms/reservoirs before recorded warm-up begins.
_SETTLE_MINUTES = 90


@dataclass
class TrialResult:
    """Everything one trial produced: scalar outcomes plus full time series."""

    mode: str
    seed: int
    trial_index: int
    n_homes: int
    n_devices: int

    # timeline indices (minutes)
    outage_start: int
    restore_minute: int
    total_minutes: int

    # scalar outcomes
    blew: bool
    blow_minute_abs: int  # absolute minute index of the first blow-out, or -1
    blow_minute_since_restore: int  # relative to restoration, or -1
    homes_dark: int  # homes left dark by a blow-out (on a blown phase)
    peak_pu: float  # peak transformer load vs rating
    minutes_above_32: float  # mean per-home minutes indoors above 32 C (recovery)
    ageing_hours: float  # accumulated equivalent insulation ageing (h)
    phases_blown: int

    # time series (length total_minutes)
    total_load_kw: np.ndarray = field(repr=False)
    load_pu: np.ndarray = field(repr=False)
    phase_heat_pct: np.ndarray = field(repr=False)  # shape (T, 3)
    hot_spot_c: np.ndarray = field(repr=False)
    top_oil_c: np.ndarray = field(repr=False)
    rep_voltage: np.ndarray = field(repr=False)
    min_voltage: np.ndarray = field(repr=False)
    homes_online: np.ndarray = field(repr=False)
    mean_indoor_c: np.ndarray = field(repr=False)
    ambient_c: np.ndarray = field(repr=False)

    def scalar_summary(self) -> dict:
        """Compact, order-stable dict of the scalar outcomes (used for hashing)."""
        return {
            "mode": self.mode,
            "seed": self.seed,
            "trial_index": self.trial_index,
            "n_homes": self.n_homes,
            "n_devices": self.n_devices,
            "blew": bool(self.blew),
            "blow_minute_since_restore": int(self.blow_minute_since_restore),
            "homes_dark": int(self.homes_dark),
            "phases_blown": int(self.phases_blown),
            "peak_pu": round(float(self.peak_pu), 6),
            "minutes_above_32": round(float(self.minutes_above_32), 6),
            "ageing_hours": round(float(self.ageing_hours), 6),
        }


def run_trial(config: Config, trial_index: int = 0) -> TrialResult:
    """Run one deterministic trial for ``config.mode`` and trial ``trial_index``."""
    cfg = config
    dt = cfg.dt_min
    T = cfg.total_minutes

    # Two independent, purely seeded generators (see module docstring).
    scenario_rng = np.random.default_rng(np.random.SeedSequence([cfg.seed, trial_index, 0]))
    controller_rng = np.random.default_rng(np.random.SeedSequence([cfg.seed, trial_index, 1]))

    # --- build the scenario (mode-independent) ---
    dev = build_devices(cfg, scenario_rng)
    H = cfg.homes
    amb = ambient_series(T, cfg.day_start_minute, cfg.peak_ambient_c, cfg.ambient_night_c)

    feeder = FeederModel(dev.home_phase, cfg.v_ln, cfg.power_factor, scenario_rng)
    rooms = RoomModel(dev.n_rooms, RoomParams())
    rooms.reset(amb[0], scenario_rng)
    reservoir_x = dev.reservoir_x0.copy()

    thermal = IECThermalModel()
    thermal.reset(amb[0])
    fuse = FuseBank(cfg.fuse_current_a)
    fuse.reset(np.zeros(cfg.phases))  # heat up from cold during warm-up

    controller = PacerController(dev, cfg)
    beacon: Beacon | None = None
    if cfg.mode == ControllerMode.PACER_BEACON:
        beacon = Beacon(dev, cfg, melting_current_a=fuse.melting_current_a)

    # per-phase home masks (for voltage references and online counting)
    phase_home_masks = [dev.home_phase == ph for ph in range(cfg.phases)]

    # --- allocate time series ---
    ts_load = np.zeros(T)
    ts_pu = np.zeros(T)
    ts_heat = np.zeros((T, cfg.phases))
    ts_hs = np.zeros(T)
    ts_oil = np.zeros(T)
    ts_vrep = np.zeros(T)
    ts_vmin = np.zeros(T)
    ts_online = np.zeros(T)
    ts_indoor = np.zeros(T)

    rep_home = feeder.representative_home()
    room_minutes_hot = np.zeros(dev.n_rooms)

    # carried state between minutes
    v_prev_home = np.full(H, cfg.v_ln)
    phase_i_prev = np.zeros(cfg.phases)
    hs_phase_prev = np.full(cfg.phases, amb[0])
    fuse_heat_prev = fuse.heat_percent()
    paced = False

    # device -> home room temperature (-inf so Rule 7 never fires for non-AC)
    thermal_mask = dev.is_thermal
    reservoir_mask = dev.is_reservoir

    # --- settle rooms and reservoirs to a diversified steady state -------------
    # The transformer was operating normally before the cut, so warm-up must not
    # open on a coincident cold-start spike (every room exactly at setpoint, every
    # store at its initial charge). Pre-roll the physical stores with served =
    # demand. This is deterministic -- it consumes no random numbers -- so it does
    # not disturb reproducibility.
    for _ in range(_SETTLE_MINUTES):
        if dev.n_rooms:
            cooling = rooms.cooling_demand()
            ac_duty = np.zeros(dev.n_rooms)
            ac_duty[dev.room_idx[thermal_mask]] = cooling[dev.room_idx[thermal_mask]]
            rooms.step(ac_duty, amb[0], dt)
        res_served = np.clip((1.0 - reservoir_x) / _RESERVOIR_DEADBAND, 0.0, 1.0)
        dres = (res_served * dev.charge_rate_per_min - dev.normal_drain_per_min) * dt
        reservoir_x = np.where(reservoir_mask, np.clip(reservoir_x + dres, 0.0, 1.0), reservoir_x)

    for t in range(T):
        supply = not (cfg.outage_start <= t < cfg.restore_minute)
        in_recovery = t >= cfg.restore_minute
        m = t - cfg.restore_minute  # minute since restore (negative before)
        minute_abs = cfg.day_start_minute + t
        ambient_c = amb[t]

        # At the instant of restoration: arm the controller (Rules 1 & 2) and
        # let the Beacon lock each device onto its phase.
        if t == cfg.restore_minute:
            paced = controller.schedule_restart(cfg.outage_minutes * 60.0, controller_rng)
            if beacon is not None:
                beacon.lock_phases()
            v_prev_home = np.full(H, cfg.v_ln)

        # Which homes are actually powered this minute (supply present and their
        # phase fuse intact). A blown phase disconnects all its homes.
        blown_home = fuse.blown[dev.home_phase]
        supply_home = supply & (~blown_home)
        supply_dev = supply_home[dev.home]

        # --- compute demand (physical want), independent of control ---
        demand = np.zeros(dev.n_devices)
        cooling = rooms.cooling_demand() if dev.n_rooms else np.zeros(0)
        if dev.n_rooms:
            demand[thermal_mask] = cooling[dev.room_idx[thermal_mask]]
        res_demand = np.clip((1.0 - reservoir_x) / _RESERVOIR_DEADBAND, 0.0, 1.0)
        demand[reservoir_mask] = res_demand[reservoir_mask]

        # room temperature per device (for Rule 7)
        room_temp_dev = np.full(dev.n_devices, -np.inf)
        if dev.n_rooms:
            room_temp_dev[thermal_mask] = rooms.t_air[dev.room_idx[thermal_mask]]

        # --- serve ---
        if not supply:
            served = np.zeros(dev.n_devices)
        elif not in_recovery:
            served = controller.serve_normal(demand)
        elif cfg.mode == ControllerMode.BASELINE:
            served = controller.serve_baseline(m, demand)
        elif not paced:
            # Rule 1 judged this a blip: behave as normal (no pacing).
            served = controller.serve_normal(demand)
        else:
            if beacon is not None:
                beacon.update(m, phase_i_prev, hs_phase_prev, fuse_heat_prev)
                beacon_caps = beacon.device_caps()
            else:
                beacon_caps = np.ones(dev.n_devices)
            v_sense = v_prev_home[dev.home]
            served = controller.serve_pacer(
                m, minute_abs, v_sense, demand, room_temp_dev, beacon_caps, controller_rng
            )

        # disconnect homes on blown phases / during outage
        served = served * supply_dev

        # --- aggregate to homes and to the network ---
        home_appliance_kw = np.bincount(dev.home, weights=served * dev.rated_kw, minlength=H)
        home_power = np.where(supply_home, home_appliance_kw + dev.home_base_kw, 0.0)

        v_home = feeder.home_voltages(home_power)
        v_home_eff = np.where(supply_home, v_home, 0.0)
        phase_i = feeder.phase_currents(home_power)

        # --- advance physics ---
        fuse.step(phase_i, t, dt)
        apparent_kva = home_power.sum() / cfg.power_factor
        load_pu = apparent_kva / cfg.nameplate_kva
        thermal.step(load_pu, ambient_c, dt)

        ac_duty_room = np.zeros(dev.n_rooms)
        if dev.n_rooms:
            ac_duty_room[dev.room_idx[thermal_mask]] = served[thermal_mask]
        rooms.step(ac_duty_room, ambient_c, dt)

        # reservoirs: charge when powered, otherwise deplete (backing the home)
        powered_dev = supply_dev
        drain = np.where(powered_dev, dev.normal_drain_per_min, dev.outage_drain_per_min)
        dres = (served * dev.charge_rate_per_min - drain) * dt
        reservoir_x = np.where(reservoir_mask, np.clip(reservoir_x + dres, 0.0, 1.0), reservoir_x)

        # --- learner / estimator (Rule 4 support) ---
        valid = (not in_recovery) or (
            m >= controller.p.learner_exclude_post_restore_min and not fuse.any_blown()
        )
        if supply:
            i_dev = served * dev.rated_kw * 1000.0 / (cfg.v_ln * cfg.power_factor)
            controller.observe(minute_abs, v_home_eff[dev.home], i_dev, valid)
            if beacon is not None and not in_recovery:
                v_phase_ref = np.array(
                    [v_home_eff[phase_home_masks[ph]].mean() if phase_home_masks[ph].any() else cfg.v_ln
                     for ph in range(cfg.phases)]
                )
                beacon.observe(v_home_eff[dev.home], v_phase_ref)

        # per-phase hot-spot proxy for the Beacon next minute (shared hot-spot,
        # scaled by each phase's share of the load).
        mean_i = max(phase_i.mean(), 1e-6)
        hs_rise = max(thermal.hot_spot_c - ambient_c, 0.0)
        hs_phase_prev = ambient_c + hs_rise * (phase_i / mean_i)
        phase_i_prev = phase_i
        fuse_heat_prev = fuse.heat_percent()

        # --- record ---
        ts_load[t] = home_power.sum()
        ts_pu[t] = load_pu
        ts_heat[t] = fuse.heat_percent()
        ts_hs[t] = thermal.hot_spot_c
        ts_oil[t] = thermal.top_oil_c
        ts_vrep[t] = v_home_eff[rep_home]
        connected = v_home_eff[supply_home]
        ts_vmin[t] = connected.min() if connected.size else 0.0
        ts_online[t] = int(np.count_nonzero(supply_home))
        ts_indoor[t] = rooms.t_air.mean() if dev.n_rooms else ambient_c

        if in_recovery and dev.n_rooms:
            room_minutes_hot += rooms.t_air > _HEAT_EXPOSURE_C

        v_prev_home = v_home_eff

    # --- scalar outcomes ---
    phases_blown = int(np.count_nonzero(fuse.blown))
    blew = phases_blown > 0
    if blew:
        valid_blows = fuse.blow_minute[fuse.blown]
        blow_abs = int(valid_blows.min())
        blow_rel = blow_abs - cfg.restore_minute
    else:
        blow_abs = -1
        blow_rel = -1
    homes_dark = int(np.count_nonzero(fuse.blown[dev.home_phase]))
    minutes_above_32 = float(room_minutes_hot.mean()) if dev.n_rooms else 0.0

    return TrialResult(
        mode=cfg.mode.value,
        seed=cfg.seed,
        trial_index=trial_index,
        n_homes=H,
        n_devices=dev.n_devices,
        outage_start=cfg.outage_start,
        restore_minute=cfg.restore_minute,
        total_minutes=T,
        blew=blew,
        blow_minute_abs=blow_abs,
        blow_minute_since_restore=blow_rel,
        homes_dark=homes_dark,
        peak_pu=float(ts_pu.max()),
        minutes_above_32=minutes_above_32,
        ageing_hours=float(thermal.ageing_hours),
        phases_blown=phases_blown,
        total_load_kw=ts_load,
        load_pu=ts_pu,
        phase_heat_pct=ts_heat,
        hot_spot_c=ts_hs,
        top_oil_c=ts_oil,
        rep_voltage=ts_vrep,
        min_voltage=ts_vmin,
        homes_online=ts_online,
        mean_indoor_c=ts_indoor,
        ambient_c=amb,
    )
