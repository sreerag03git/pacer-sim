"""The optional per-transformer Beacon (controller mode C).

The Beacon runs a per-phase view of the transformer thermal state and the fuse
heating, and broadcasts a signed, rate-limited per-phase duty ceiling that holds
each phase below 85% of its fuse-melting level and below a hot-spot-band target
(1.2 / 1.1 / 1.0 / 0.9 pu). It is active only inside the post-restore pacing
window and its guidance always expires. Guidance can only ever *reduce* load.

Devices do not trust an address; they infer which phase they are on by
correlating their own voltage series against the Beacon's per-phase reference
series. If a device cannot lock onto a phase it assumes the worst (most
constrained) phase, so an unlocked device is never less cautious.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from engine.config import Config
from engine.devices import Devices


@dataclass
class BeaconParams:
    """Beacon design constants (named, with units; not fitted)."""

    # Hot-spot bands (degC) -> allowed per-phase load target (pu of rated).
    hs_band_edges_c: tuple[float, float, float] = (98.0, 110.0, 120.0)
    hs_band_targets_pu: tuple[float, float, float, float] = (1.2, 1.1, 1.0, 0.9)
    # Hard fuse cap: never let a phase exceed this fraction of the melting level.
    fuse_fraction: float = 0.85
    # Guidance is rate-limited so it cannot chatter. Protective systems clamp
    # quickly but release slowly, so the step limits are asymmetric: a large
    # reduction is allowed in one step, relaxation is gradual.
    max_tighten_step_per_min: float = 0.40
    max_relax_step_per_min: float = 0.05
    # The pacing window after restoration during which guidance is broadcast.
    window_min: int = 90
    # Anticipatory initial cap. At restoration the Beacon knows a coincident
    # surge is coming, so it opens with conservative guidance instead of a wide-
    # open 1.0 that it could only tighten a step too late. The value is the fuse
    # fraction of the melting level divided by a worst-case ~2x incoming surge:
    # 0.85 * 1.45 / 2 ~= 0.6. It then adapts from measurement: if the first
    # post-restore minutes show headroom (the surge is still building) it relaxes
    # gradually at max_relax_step_per_min, and tightens hard (max_tighten_step)
    # the moment the fuse-heat brake or the current ceiling demands it.
    initial_cap: float = 0.6
    # Phase-lock confidence: lock only if the best correlation is strong and
    # clearly beats the runner-up; otherwise stay unlocked (assume worst phase).
    lock_min_corr: float = 0.5
    lock_margin: float = 0.10


class Beacon:
    """Per-phase thermal/fuse-aware guidance with voltage-correlation phase lock."""

    def __init__(self, devices: Devices, config: Config, melting_current_a: float, params: BeaconParams | None = None) -> None:
        self.dev = devices
        self.cfg = config
        self.p = params or BeaconParams()
        self.n_phases = config.phases
        self.rated_phase_current_a = config.rated_phase_current_a
        self.melting_current_a = melting_current_a

        # Per-phase broadcast cap (duty ceiling). Opens conservative (anticipatory)
        # so guidance is already in force the moment the surge begins.
        self._phase_cap = np.full(self.n_phases, self.p.initial_cap)

        # --- phase-lock accumulators (built during warm-up) ---
        D = devices.n_devices
        self._n = 0
        self._sv = np.zeros(D)  # sum of device voltage
        self._svv = np.zeros(D)  # sum of v^2
        self._sr = np.zeros(self.n_phases)  # sum of each phase reference
        self._srr = np.zeros(self.n_phases)
        self._svr = np.zeros((D, self.n_phases))  # sum of v * ref_phase
        self._locked_phase = np.full(D, -1, dtype=int)  # -1 == unlocked

    # ---------------------------------------------------------------------------
    def observe(self, v_home_per_device: np.ndarray, v_phase_ref: np.ndarray) -> None:
        """Accumulate statistics for voltage-correlation phase inference."""
        self._n += 1
        self._sv += v_home_per_device
        self._svv += v_home_per_device**2
        self._sr += v_phase_ref
        self._srr += v_phase_ref**2
        self._svr += v_home_per_device[:, None] * v_phase_ref[None, :]

    def lock_phases(self) -> None:
        """Estimate each device's phase from accumulated voltage correlations."""
        n = max(self._n, 1)
        mean_v = self._sv / n
        var_v = np.maximum(self._svv / n - mean_v**2, 1e-9)
        mean_r = self._sr / n
        var_r = np.maximum(self._srr / n - mean_r**2, 1e-9)
        cov = self._svr / n - mean_v[:, None] * mean_r[None, :]
        corr = cov / np.sqrt(var_v[:, None] * var_r[None, :])

        best = np.argmax(corr, axis=1)
        best_corr = corr[np.arange(corr.shape[0]), best]
        sorted_corr = np.sort(corr, axis=1)
        second = sorted_corr[:, -2] if corr.shape[1] >= 2 else np.full(corr.shape[0], -np.inf)
        confident = (best_corr > self.p.lock_min_corr) & ((best_corr - second) > self.p.lock_margin)
        self._locked_phase = np.where(confident, best, -1)

    # ---------------------------------------------------------------------------
    def _phase_target_pu(self, hotspot_per_phase: np.ndarray) -> np.ndarray:
        """Map each phase's hot-spot to its allowed load target (pu)."""
        e = self.p.hs_band_edges_c
        t = self.p.hs_band_targets_pu
        target = np.full(self.n_phases, t[0])
        target = np.where(hotspot_per_phase >= e[0], t[1], target)
        target = np.where(hotspot_per_phase >= e[1], t[2], target)
        target = np.where(hotspot_per_phase >= e[2], t[3], target)
        return target

    def update(
        self,
        minute_since_restore: int,
        phase_current_prev_a: np.ndarray,
        hotspot_per_phase_c: np.ndarray,
        fuse_heat_prev_pct: np.ndarray,
    ) -> None:
        """Advance the per-phase broadcast cap one minute (rate-limited).

        Two signals set the target: the hot-spot-band current ceiling, and the
        fuse-heat itself. Holding a phase below 85% of its melting *current* is
        equivalent to holding its fuse-heat below 0.85^2 ~= 72%, so once a phase
        climbs past that the Beacon drives its cap down hard -- it is tracking how
        hot each fuse is getting, not merely the instantaneous current.
        """
        if minute_since_restore >= self.p.window_min:
            # Guidance expires at the window end: hard-release so devices truly
            # revert to PACER-only. By this point the restart surge is long over,
            # so there is no load step to fear from releasing in one go.
            self._phase_cap[:] = 1.0
            return

        target_pu = self._phase_target_pu(hotspot_per_phase_c)
        ceiling_a = np.minimum(
            target_pu * self.rated_phase_current_a,
            self.p.fuse_fraction * self.melting_current_a,
        )
        present = np.maximum(phase_current_prev_a, 1e-6)
        desired_cap = np.clip(ceiling_a / present, 0.0, 1.0)

        # Fuse-heat brake: a phase heating past the 85%-of-melting equivalent
        # must shed load regardless of the instantaneous current estimate.
        target_heat_pct = 100.0 * self.p.fuse_fraction**2
        over_heat = fuse_heat_prev_pct > target_heat_pct
        desired_cap = np.where(over_heat, 0.0, desired_cap)

        # Rate-limit: clamp fast (large negative step), relax slowly.
        delta = np.clip(
            desired_cap - self._phase_cap,
            -self.p.max_tighten_step_per_min,
            self.p.max_relax_step_per_min,
        )
        self._phase_cap = np.clip(self._phase_cap + delta, 0.0, 1.0)

    def device_caps(self) -> np.ndarray:
        """Per-device duty ceiling from the broadcast. Unlocked devices take the
        most constrained (worst) phase cap."""
        worst = float(np.min(self._phase_cap))
        locked = self._locked_phase
        caps = np.where(locked >= 0, self._phase_cap[np.clip(locked, 0, self.n_phases - 1)], worst)
        return caps
