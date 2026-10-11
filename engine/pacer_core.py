"""PACER Core -- the seven-rule local controller.

Every controllable device carries one instance of this logic. It uses only
local sensing (its own terminal voltage and current) and a per-device learner;
it needs no network and can only ever make a device *more* cautious. The seven
rules are implemented exactly as specified, not approximated:

  Rule 1  Outage timer   -- ignore supply blips < 60 s; only outages >= 60 s count.
  Rule 2  Random wait    -- window = min(2 + 8*outage_hours, 25) min; uniform draw.
  Rule 3  Soft start     -- duty cap ramps from the per-appliance soft-start value
                            to 1.0 over a 30-min window.
  Rule 4  Stress sensing -- (learned_normal_V - present_V) / self-measured impedance;
                            relative to a learned normal, never absolute voltage.
  Rule 5  Back-off       -- AC x0.75 floor 0.35; charger x0.5 floor 0; then latch 6-12 min.
  Rule 6  Stepped return -- small random additive upward steps (no rebound peak).
  Rule 7  Heat-dose floor-- above 32 C: start 55% and add 10 pts / 5 min
                            (20 for vulnerable) to 100%; always wins.
  Rails   min off 3 min; <= 6 starts/hour; no ON command ever; fault -> pass-through.

All state is held as numpy arrays indexed by device so the per-minute update
vectorises across the whole population.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from engine.config import Config
from engine.devices import Devices


@dataclass
class PacerParams:
    """Control-design constants for PACER Core. Named, with units; not fitted to
    any target outcome. These shape *how cautious* the controller is."""

    # Rule 1
    outage_min_seconds: float = 60.0
    # Rule 2
    wait_base_min: float = 2.0
    wait_slope_min_per_hour: float = 8.0
    wait_cap_min: float = 25.0
    # Rule 3
    soft_start_window_min: float = 30.0
    # Rule 4 -- stress sensing / self-impedance estimator
    stress_on_a: float = 60.0  # excess current-equivalent (A) that triggers back-off
    stress_off_a: float = 25.0  # below this the device may step back up (hysteresis)
    z_prior_ohm: float = 0.10  # impedance estimate before enough samples are seen
    z_min_ohm: float = 0.01  # clamp on the estimator
    z_max_ohm: float = 1.50
    i_step_threshold_a: float = 0.5  # minimum own-current step to record a dV/dI sample
    z_ring_size: int = 16  # rolling window of dV/dI samples
    # Rule 5
    latch_min_min: int = 6
    latch_max_min: int = 12  # inclusive
    # Rule 6
    step_up_min: float = 0.03
    step_up_max: float = 0.10
    # Rule 7
    heat_trigger_c: float = 32.0
    heat_start_duty: float = 0.55
    heat_rate_per_min: float = 0.10 / 5.0  # +10 points every 5 min
    heat_rate_vuln_per_min: float = 0.20 / 5.0  # +20 points every 5 min for vulnerable homes
    # Safety rails
    min_off_min: int = 3
    max_starts_per_hour: int = 6
    # Learner
    n_tod_bins: int = 48  # 30-min time-of-day bins
    learner_exclude_post_restore_min: int = 60


class PacerController:
    """Vectorised seven-rule controller over a device population."""

    def __init__(self, devices: Devices, config: Config, params: PacerParams | None = None) -> None:
        self.dev = devices
        self.cfg = config
        self.p = params or PacerParams()
        D = devices.n_devices
        self.D = D
        self.v_ln = config.v_ln
        self.pf = config.power_factor

        # --- learner: normal voltage by time-of-day bin (per device) ---
        self._bin_sum = np.zeros((D, self.p.n_tod_bins))
        self._bin_cnt = np.zeros((D, self.p.n_tod_bins))

        # --- self-impedance estimator (Rule 4) ---
        self._z_ring = np.full((D, self.p.z_ring_size), np.nan)
        self._z_ptr = np.zeros(D, dtype=int)
        self._z_cnt = np.zeros(D, dtype=int)
        self._z_est = np.full(D, self.p.z_prior_ohm)
        self._prev_v = np.full(D, config.v_ln)
        self._prev_i = np.zeros(D)
        self._have_prev = False

        # --- dynamic recovery state (set by schedule_restart) ---
        self._started = np.zeros(D, dtype=bool)
        self._start_offset = np.zeros(D, dtype=int)
        self._cap = np.zeros(D)
        self._latch_until = np.full(D, -1, dtype=int)
        self._heat_active = np.zeros(D, dtype=bool)
        self._heat_floor = np.zeros(D)
        self._heat_start = np.zeros(D, dtype=int)
        self._on_prev = np.zeros(D, dtype=bool)
        self._last_off = np.full(D, -10_000, dtype=int)
        self._start_ring = np.full((D, self.p.max_starts_per_hour), -10_000, dtype=int)
        self._start_ptr = np.zeros(D, dtype=int)

    # ---------------------------------------------------------------------------
    # Learner + estimator (called every valid minute)
    # ---------------------------------------------------------------------------
    def _tod_bin(self, minute_abs: int) -> int:
        bin_width = 1440 // self.p.n_tod_bins
        return int((minute_abs % 1440) // bin_width)

    def observe(self, minute_abs: int, v_home: np.ndarray, i_dev: np.ndarray, valid: bool) -> None:
        """Record normal-voltage and dV/dI samples. ``valid`` excludes outages and
        the first 60 min post-restore, per Rule 4."""
        if valid:
            b = self._tod_bin(minute_abs)
            self._bin_sum[:, b] += v_home
            self._bin_cnt[:, b] += 1.0

            if self._have_prev:
                di = i_dev - self._prev_i
                dv = v_home - self._prev_v
                qualifies = np.abs(di) > self.p.i_step_threshold_a
                # Self-impedance from the device's own load step: Z ~ -dV/dI.
                with np.errstate(divide="ignore", invalid="ignore"):
                    z_sample = np.where(qualifies, -dv / di, np.nan)
                z_sample = np.where(
                    (z_sample > self.p.z_min_ohm) & (z_sample < self.p.z_max_ohm),
                    z_sample,
                    np.nan,
                )
                rec = qualifies & np.isfinite(z_sample)
                idx = np.nonzero(rec)[0]
                for d in idx:
                    self._z_ring[d, self._z_ptr[d]] = z_sample[d]
                    self._z_ptr[d] = (self._z_ptr[d] + 1) % self.p.z_ring_size
                    self._z_cnt[d] = min(self._z_cnt[d] + 1, self.p.z_ring_size)
                have = self._z_cnt > 0
                if np.any(have):
                    # Median only over rows that actually hold samples (avoids an
                    # all-NaN-slice warning for devices with no step yet).
                    med = np.full(self.D, np.nan)
                    med[have] = np.nanmedian(self._z_ring[have], axis=1)
                    self._z_est = np.where(have & np.isfinite(med), med, self._z_est)

        self._prev_v = v_home.copy()
        self._prev_i = i_dev.copy()
        self._have_prev = True

    def learned_normal_v(self, minute_abs: int) -> np.ndarray:
        """Per-device learned normal voltage for the current time-of-day bin."""
        b = self._tod_bin(minute_abs)
        cnt = self._bin_cnt[:, b]
        out = np.where(cnt > 0, self._bin_sum[:, b] / np.maximum(cnt, 1.0), np.nan)
        # Fallback to the device's all-day mean, then to nominal voltage.
        total_cnt = self._bin_cnt.sum(axis=1)
        allday = np.where(total_cnt > 0, self._bin_sum.sum(axis=1) / np.maximum(total_cnt, 1.0), self.v_ln)
        out = np.where(np.isfinite(out), out, allday)
        return out

    @property
    def z_estimate(self) -> np.ndarray:
        return self._z_est.copy()

    # ---------------------------------------------------------------------------
    # Recovery scheduling (Rules 1 and 2)
    # ---------------------------------------------------------------------------
    def schedule_restart(self, outage_seconds: float, rng: np.random.Generator) -> bool:
        """Arm the controller at restoration.

        Returns False (and does not pace) if the outage was shorter than the
        Rule 1 threshold -- in that case the caller treats it as a blip.
        """
        self._cap[:] = 0.0
        self._started[:] = False
        self._latch_until[:] = -1
        self._heat_active[:] = False
        self._heat_floor[:] = 0.0
        self._heat_start[:] = 0
        self._on_prev[:] = False
        self._last_off[:] = -10_000
        self._start_ring[:] = -10_000
        self._start_ptr[:] = 0

        if outage_seconds < self.p.outage_min_seconds:
            return False  # Rule 1: ignore blips shorter than 60 s

        outage_hours = outage_seconds / 3600.0
        window_min = min(
            self.p.wait_base_min + self.p.wait_slope_min_per_hour * outage_hours,
            self.p.wait_cap_min,
        )
        # Rule 2: each device draws a uniform random start inside the window.
        self._start_offset = np.floor(rng.uniform(0.0, window_min, size=self.D)).astype(int)
        return True

    # ---------------------------------------------------------------------------
    # Per-minute serving
    # ---------------------------------------------------------------------------
    def serve_normal(self, demand: np.ndarray) -> np.ndarray:
        """Normal operation (warm-up, grid present): the device simply follows its
        own demand. PACER never adds load, so there is nothing to shape here."""
        served = np.clip(demand, 0.0, 1.0)
        self._on_prev = served > 1e-6
        return served

    def serve_baseline(self, minute_since_restore: int, demand: np.ndarray) -> np.ndarray:
        """Baseline stabiliser: a fixed 3-min wait, then full power in lockstep."""
        if minute_since_restore < 3:
            return np.zeros(self.D)
        return np.clip(demand, 0.0, 1.0)

    def serve_pacer(
        self,
        minute_since_restore: int,
        minute_abs: int,
        v_sense: np.ndarray,
        demand: np.ndarray,
        room_temp: np.ndarray,
        beacon_cap: np.ndarray,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """One minute of the seven-rule controller. Returns served duty per device.

        ``v_sense`` is the device's measured terminal voltage (previous minute --
        sensing physically lags action by one step). ``room_temp`` is the home's
        indoor temperature (-inf for non-AC devices, so Rule 7 never fires there).
        ``beacon_cap`` is the Beacon's per-device duty ceiling (1.0 when absent).
        """
        p = self.p
        m = minute_since_restore
        D = self.D

        # Rule 2: devices still inside their random wait stay off.
        newly_started = (~self._started) & (m >= self._start_offset)
        if np.any(newly_started):
            self._cap[newly_started] = self.dev.soft_start_duty[newly_started]
            self._started |= newly_started

        started = self._started
        active = started & (~self.dev.fault)

        # Rule 3: soft-start ceiling, ramping to full over the 30-min window.
        minutes_since_start = np.maximum(m - self._start_offset, 0)
        ramp = np.clip(minutes_since_start / p.soft_start_window_min, 0.0, 1.0)
        ceil_soft = self.dev.soft_start_duty + (1.0 - self.dev.soft_start_duty) * ramp

        # Rule 4: impedance-normalised stress relative to the learned normal.
        vnorm = self.learned_normal_v(minute_abs)
        sag = np.maximum(vnorm - v_sense, 0.0)
        stress_current = sag / np.maximum(self._z_est, p.z_min_ohm)
        stressed = stress_current > p.stress_on_a
        unstressed = stress_current < p.stress_off_a
        latch_active = m < self._latch_until

        # Rule 5: back-off (multiply, floor) and latch 6-12 min.
        latch_draw = rng.integers(p.latch_min_min, p.latch_max_min + 1, size=D)
        step_draw = rng.uniform(p.step_up_min, p.step_up_max, size=D)
        trig = active & stressed & (~latch_active)
        self._cap = np.where(
            trig,
            np.maximum(self._cap * self.dev.backoff_multiplier, self.dev.backoff_floor),
            self._cap,
        )
        self._latch_until = np.where(trig, m + latch_draw, self._latch_until)

        # Rule 6: stepped return -- small random additive steps when clear.
        up = active & unstressed & (~latch_active) & (~trig)
        self._cap = np.where(up, self._cap + step_draw, self._cap)

        # Bound by the soft-start ceiling and by 1.0 (heat dose may override next).
        self._cap = np.minimum(self._cap, ceil_soft)
        self._cap = np.clip(self._cap, 0.0, 1.0)

        # Rule 7: heat-dose floor (always wins over back-off and soft start).
        hot = active & (room_temp > p.heat_trigger_c)
        newly_hot = hot & (~self._heat_active)
        self._heat_active = self._heat_active | newly_hot
        self._heat_start = np.where(newly_hot, m, self._heat_start)
        self._heat_floor = np.where(newly_hot, p.heat_start_duty, self._heat_floor)
        rate = np.where(self.dev.is_vulnerable, p.heat_rate_vuln_per_min, p.heat_rate_per_min)
        active_heat = self._heat_active & active
        self._heat_floor = np.where(
            active_heat,
            np.minimum(1.0, p.heat_start_duty + rate * (m - self._heat_start)),
            self._heat_floor,
        )
        self._cap = np.where(hot, np.maximum(self._cap, self._heat_floor), self._cap)
        self._cap = np.clip(self._cap, 0.0, 1.0)

        # Serve: never exceed demand; the controller only ever caps, never adds load.
        served = np.where(active, np.minimum(demand, self._cap), 0.0)

        # Beacon: can only reduce load, but the health floor still wins.
        served = np.minimum(served, beacon_cap)
        served = np.where(
            hot, np.maximum(served, np.minimum(demand, self._heat_floor)), served
        )

        # Fault devices: pass-through (behave as if PACER were absent).
        served = np.where(self.dev.fault, np.clip(demand, 0.0, 1.0), served)

        served = self._apply_safety_rails(m, served)
        return served

    def _apply_safety_rails(self, m: int, desired: np.ndarray) -> np.ndarray:
        """Minimum off-time (3 min) and at most 6 starts/hour. No rail can switch a
        load on; they only ever hold a device off."""
        p = self.p
        served = desired.copy()
        on_desired = served > 1e-6

        # Minimum off-time: a device off within the last 3 min may not restart.
        recently_off = (m - self._last_off) < p.min_off_min
        blocked_min_off = on_desired & (~self._on_prev) & recently_off & (~self.dev.fault)
        served = np.where(blocked_min_off, 0.0, served)
        on_desired = served > 1e-6

        # Count starts in the trailing hour; block a 7th start.
        new_start = on_desired & (~self._on_prev) & (~self.dev.fault)
        idx = np.nonzero(new_start)[0]
        for d in idx:
            recent = np.sum(self._start_ring[d] > (m - 60))
            if recent >= p.max_starts_per_hour:
                served[d] = 0.0
            else:
                self._start_ring[d, self._start_ptr[d]] = m
                self._start_ptr[d] = (self._start_ptr[d] + 1) % p.max_starts_per_hour

        on_now = served > 1e-6
        just_off = self._on_prev & (~on_now)
        self._last_off = np.where(just_off, m, self._last_off)
        self._on_prev = on_now
        return served
