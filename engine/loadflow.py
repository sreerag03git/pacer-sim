"""Four-wire unbalanced LV load flow (backward-forward sweep).

Standard radial distribution solver (Kersting, *Distribution System Modeling and
Analysis*, ch. 10): a backward current sweep followed by a forward voltage sweep,
iterated to tolerance. Segments carry complex series impedance Z = R + jX; the
shared neutral conductor carries the phasor sum of the three phase currents, so an
unbalanced single-phase load pattern shifts the neutral point and pulls every
home's line-to-neutral voltage with it. Loads are voltage dependent via the
exponential model P = P0 (|V|/V0)^np, Q = Q0 (|V|/V0)^nq (np = nq = 0 is constant
power). Voltage unbalance is reported per ANSI/NEMA MG 1: 100 x (max deviation of a
phase voltage from the mean) / mean.

Pure numpy, no engine imports. Unit-tested in tests/test_engine.py. This is the
Phase-1 electrical core; FeederModel wires it in behind the ``use_reactance`` flag.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# source phase angles for a wye secondary: A at 0, B at -120, C at +120 degrees
_PHASE_ANGLE_DEG = np.array([0.0, -120.0, 120.0])


def nema_vuf(v_phase_mag) -> float:
    """ANSI/NEMA MG 1 voltage-unbalance factor (%) from the three phase magnitudes."""
    v = np.asarray(v_phase_mag, dtype=float)
    avg = v.mean()
    if avg <= 0:
        return 0.0
    return float(np.max(np.abs(v - avg)) / avg * 100.0)


@dataclass
class FeederSolution:
    v_home: np.ndarray        # complex line-to-neutral voltage at each home (V)
    i_phase_src: np.ndarray   # (3,) complex source phase currents (A)
    i_neutral_src: complex    # source neutral current (A) = -(I_A + I_B + I_C)
    vuf_pct: float            # NEMA voltage unbalance (%)
    iters: int
    converged: bool


def solve_feeder(
    home_phase,
    z_seg_ph,
    z_seg_n,
    z_src_ph: complex,
    z_src_n: complex,
    p0_w,
    q0_var,
    np_exp,
    nq_exp,
    v_ln: float,
    max_iter: int = 8,
    tol: float = 1e-4,
) -> FeederSolution:
    """Solve one radial 4-wire feeder.

    Homes are listed in route order (index 0 nearest the transformer); ``home_phase``
    gives each home's phase (0/1/2). ``z_seg_ph[k]`` / ``z_seg_n[k]`` are the phase-
    and neutral-conductor series impedances of the segment feeding node k; ``z_src_*``
    are the common source (transformer) impedances. Loads are P0 (W) / Q0 (var) per
    home with exponents ``np_exp`` / ``nq_exp`` (scalar or per-home). ``tol`` is in pu
    of ``v_ln``; stops at ``max_iter`` sweeps.
    """
    hp = np.asarray(home_phase, dtype=int)
    n = hp.size
    vsrc = v_ln * np.exp(1j * np.deg2rad(_PHASE_ANGLE_DEG))
    if n == 0:
        return FeederSolution(np.zeros(0, complex), np.zeros(3, complex), 0j, 0.0, 0, True)

    z_seg_ph = np.asarray(z_seg_ph, dtype=complex)
    z_seg_n = np.asarray(z_seg_n, dtype=complex)
    p0 = np.asarray(p0_w, dtype=float)
    q0 = np.asarray(q0_var, dtype=float)
    masks = [hp == p for p in range(3)]

    v_home = vsrc[hp].astype(complex)  # flat start at the source phasors
    tol_v = tol * v_ln
    it = 0
    converged = False
    for it in range(1, max_iter + 1):
        frac = np.where(np.abs(v_home) > 1e-6, np.abs(v_home) / v_ln, 1.0)
        p = p0 * frac ** np.asarray(np_exp, dtype=float)
        q = q0 * frac ** np.asarray(nq_exp, dtype=float)
        i_inj = np.conj((p + 1j * q) / v_home)  # load current drawn by each home (A)

        # backward sweep: conductor current in each segment = downstream injection sum
        i_ph_seg = np.zeros((3, n), dtype=complex)
        for ph in range(3):
            ip = np.where(masks[ph], i_inj, 0.0)
            i_ph_seg[ph] = np.cumsum(ip[::-1])[::-1]
        i_n_seg = -i_ph_seg.sum(axis=0)
        i_ph_src = i_ph_seg[:, 0].copy()
        i_n_src = i_n_seg[0]

        # forward sweep: conductor & neutral potentials, then L-N home voltage
        v_new = np.empty(n, dtype=complex)
        v_neu = -z_src_n * i_n_src - np.cumsum(z_seg_n * i_n_seg)
        for ph in range(3):
            v_cond = vsrc[ph] - z_src_ph * i_ph_src[ph] - np.cumsum(z_seg_ph * i_ph_seg[ph])
            v_new[masks[ph]] = (v_cond - v_neu)[masks[ph]]

        dv = float(np.max(np.abs(v_new - v_home)))
        v_home = v_new
        if dv < tol_v:
            converged = True
            break

    mags = np.array([np.abs(v_home[masks[ph]]).mean() if masks[ph].any() else v_ln for ph in range(3)])
    return FeederSolution(v_home, i_ph_src, complex(i_n_src), nema_vuf(mags), it, converged)
