"""Physics helpers for experimental LH slider gap-fill motion.

Used by the path planner (hard feasibility) and GuitarBotParser (timing +
trajectory generation). Distances are in millimeters along the fretboard;
encoder conversion matches plan.py (2048 ticks / MM_TO_ENCODER factor).
"""
from __future__ import annotations

import math
import numpy as np

from tuning import tune as tu


def press_unpress_duration_s() -> float:
    """Fixed press (or unpress) phase length from the presser point budget."""
    return float(tu.PRESSER_INTERPOLATION_POINTS) * float(tu.TIME_STEP)


def fret_to_mm(fret: int | float | None) -> float:
    """Nut-relative mm for a fret index (0 = open / parked near nut)."""
    if fret is None:
        return 0.0
    fret_i = int(fret)
    if fret_i <= 0:
        return 0.0
    frets = tu.SLIDER_MM_PER_FRET
    idx = min(fret_i, len(frets)) - 1
    return float(frets[idx])


def distance_mm(fret_a: int | float | None, fret_b: int | float | None) -> float:
    return abs(fret_to_mm(fret_b) - fret_to_mm(fret_a))


def min_slide_time_s(
    distance_mm_val: float,
    v_max: float | None = None,
    a_max: float | None = None,
) -> float:
    """Minimum time to travel ``distance_mm_val`` under trapezoidal limits.

    Accel and decel both use ``a_max``. Returns 0 for zero/negative distance.
    """
    d = abs(float(distance_mm_val))
    if d <= 1e-9:
        return 0.0

    v_max = float(tu.LH_SLIDER_V_MAX_MM_S if v_max is None else v_max)
    a_max = float(tu.LH_SLIDER_A_MAX_MM_S2 if a_max is None else a_max)
    if v_max <= 0.0 or a_max <= 0.0:
        raise ValueError("LH slider v_max and a_max must be positive")

    # Distance to reach v_max from rest (and symmetrically to stop).
    d_accel = (v_max * v_max) / (2.0 * a_max)
    if 2.0 * d_accel >= d:
        # Triangular profile: peak velocity below v_max.
        return 2.0 * math.sqrt(d / a_max)

    t_accel = v_max / a_max
    t_cruise = (d - 2.0 * d_accel) / v_max
    return 2.0 * t_accel + t_cruise


def min_finger_move_time_s(
    distance_mm_val: float,
    v_max: float | None = None,
    a_max: float | None = None,
) -> float:
    """Minimum unpress + slide + press duration for a fret change.

    Zero-distance moves still require ``LH_PREP_TIME_MIN`` as a floor (same-fret /
    tiny nudge), not a full unpress/press cycle.
    """
    d = abs(float(distance_mm_val))
    min_prep = float(getattr(tu, "LH_PREP_TIME_MIN", 0.1))
    if d <= 1e-9:
        return min_prep

    t_phase = press_unpress_duration_s()
    t_slide = min_slide_time_s(d, v_max=v_max, a_max=a_max)
    return max(min_prep, 2.0 * t_phase + t_slide)


def move_feasible(
    available_gap_s: float,
    distance_mm_val: float,
    v_max: float | None = None,
    a_max: float | None = None,
) -> bool:
    """True if ``available_gap_s`` can fit a safe finger move over ``distance_mm_val``."""
    return float(available_gap_s) + 1e-9 >= min_finger_move_time_s(
        distance_mm_val, v_max=v_max, a_max=a_max
    )


def mm_to_encoder_delta(distance_mm_val: float) -> float:
    """Unsigned encoder magnitude for a mm travel (2048-count LH convention)."""
    return abs(float(distance_mm_val)) * 2048.0 / float(tu.MM_TO_ENCODER_CONVERSION_FACTOR)


def encoder_to_mm(encoder_delta: float) -> float:
    return abs(float(encoder_delta)) * float(tu.MM_TO_ENCODER_CONVERSION_FACTOR) / 2048.0


def trapezoid_positions(
    q0: float,
    qf: float,
    n_points: int,
    *,
    v_max_mm_s: float | None = None,
    a_max_mm_s2: float | None = None,
    dt: float | None = None,
) -> np.ndarray:
    """Encoder-tick positions from q0 toward qf over ``n_points`` samples.

    Builds a minimum-time trapezoid in mm, then **time-scales** it to fill the
    allotted duration when extra time is available (slower cruise, never above
    a_max).

    If the allotment is shorter than ``t_min``, travels only as far as ``a_max``
    allows in that time (no final snap to ``qf`` — that caused firmware
    discontinuity faults).
    """
    n = int(n_points)
    if n <= 0:
        return np.array([], dtype=int)
    if n == 1:
        return np.array([int(round(q0))], dtype=int)

    dt = float(tu.TIME_STEP if dt is None else dt)
    duration = n * dt
    q0_f = float(q0)
    qf_f = float(qf)
    enc_dist = abs(qf_f - q0_f)
    if enc_dist < 1e-6:
        return np.full(n, int(round(qf_f)), dtype=int)

    d_mm = encoder_to_mm(enc_dist)
    t_min = min_slide_time_s(d_mm, v_max=v_max_mm_s, a_max=a_max_mm_s2)
    v_max = float(tu.LH_SLIDER_V_MAX_MM_S if v_max_mm_s is None else v_max_mm_s)
    a_max = float(tu.LH_SLIDER_A_MAX_MM_S2 if a_max_mm_s2 is None else a_max_mm_s2)

    # Stretch when we have spare time; when short on time, keep a_max and only
    # cover the distance reachable in ``duration`` (caller should prefer skip).
    #
    # Time-stretch of a fixed distance: v ~ 1/S, a ~ 1/S^2 (not 1/S). Using
    # a_eff = a_max/S made long gap-fills finish early, then the decelerating
    # formula drove s back to 0 before a final snap to qf — firmware saw a
    # DISCONTINUITY_THRESHOLD jump.
    if t_min > 1e-9 and duration + 1e-12 >= t_min:
        scale = duration / t_min
        d_travel = d_mm
        a_eff = a_max / (scale * scale)
        v_eff = v_max / scale
    else:
        scale = 1.0
        # Max distance with triangular profile in ``duration`` under a_max:
        # d = 2 * (1/2 a (T/2)^2) = a T^2 / 4.
        d_travel = min(d_mm, a_max * duration * duration / 4.0)
        a_eff = a_max
        v_eff = v_max

    d_accel = (v_eff * v_eff) / (2.0 * a_eff) if a_eff > 0 else 0.0
    direction = 1.0 if qf_f >= q0_f else -1.0

    times = np.arange(n, dtype=float) * dt
    t_end = max(duration - dt, dt)
    pos_mm = np.zeros(n, dtype=float)

    if 2.0 * d_accel >= d_travel - 1e-12:
        t_peak = math.sqrt(d_travel / a_eff) if a_eff > 0 else t_end / 2.0
        s_peak = 0.5 * a_eff * t_peak * t_peak
        v_peak = a_eff * t_peak
        t_done = 2.0 * t_peak
        for i, t in enumerate(times):
            t_clamped = min(t, t_end, t_done)
            if t_clamped <= t_peak:
                s = 0.5 * a_eff * t_clamped * t_clamped
            else:
                t_dec = t_clamped - t_peak
                s = s_peak + v_peak * t_dec - 0.5 * a_eff * t_dec * t_dec
            pos_mm[i] = min(max(s, 0.0), d_travel)
    else:
        t_accel = v_eff / a_eff
        t_cruise = (d_travel - 2.0 * d_accel) / v_eff
        t1 = t_accel
        t2 = t_accel + t_cruise
        t_done = t2 + t_accel
        for i, t in enumerate(times):
            t_clamped = min(t, t_end, t_done)
            if t_clamped <= t1:
                s = 0.5 * a_eff * t_clamped * t_clamped
            elif t_clamped <= t2:
                s = d_accel + v_eff * (t_clamped - t1)
            else:
                t_dec = t_clamped - t2
                s = d_accel + v_eff * t_cruise + v_eff * t_dec - 0.5 * a_eff * t_dec * t_dec
            pos_mm[i] = min(max(s, 0.0), d_travel)

    # Continuity: last sample follows the profile. Only snap exactly to qf when
    # the window was long enough to complete the move under a_max.
    reached = duration + 1e-12 >= t_min
    if reached:
        pos_mm[-1] = d_mm
    enc = q0_f + direction * (pos_mm * 2048.0 / float(tu.MM_TO_ENCODER_CONVERSION_FACTOR))
    if reached:
        enc[-1] = qf_f
    return enc.astype(int)


def phase_point_counts(prep_time_s: float) -> tuple[int, int, int]:
    """Split a prep window into fixed unpress/press and a remaining slide.

    Unpress and press each use ``PRESSER_INTERPOLATION_POINTS`` when the window
    is large enough; otherwise points are shared as evenly as possible while
    keeping at least one sample per phase.
    """
    dt = float(tu.TIME_STEP)
    total = max(3, int(round(float(prep_time_s) / dt)))
    fixed = int(tu.PRESSER_INTERPOLATION_POINTS)

    if total >= 2 * fixed + 1:
        phase1 = fixed
        phase3 = fixed
        phase2 = total - phase1 - phase3
    else:
        phase1 = max(1, total // 3)
        phase3 = max(1, total // 3)
        phase2 = max(1, total - phase1 - phase3)
        # Repair if rounding ate the slide.
        while phase1 + phase2 + phase3 > total and phase2 > 1:
            phase2 -= 1
        while phase1 + phase2 + phase3 < total:
            phase2 += 1

    return phase1, phase2, phase3
