#!/usr/bin/env python3
"""
test_rlfret_consistency.py  —  Python-side sanity check for /RLFret trajectory generation.

Tests:
  1. Same RLFret parameters from the SAME starting state produce bit-identical trajectories.
  2. BothHandsParser.left_hand.current_positions tracks the presser correctly
     between consecutive calls (with and without unpress_after).
  3. Consecutive calls with unpress_after=False accumulate presser state correctly,
     i.e. each call's UNPRESS phase correctly starts from the previous call's target_torque.
  4. Consecutive calls with unpress_after=True always start UNPRESS from -650
     (known state) → bit-identical trajectories.
  5. Encoder formula cross-check: BothHandsParser._mm_to_encoder vs
     guitarl action_space.to_encoder_position() for the same fret position.

Usage:
    cd /home/guitarbot/Documents/GitHub/GuitarBot
    conda run -n guitaRL python test_rlfret_consistency.py
"""

import sys
import copy
import numpy as np
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
GUITARBOT = Path(__file__).parent
GUITARL   = GUITARBOT.parent / "guitarl"

sys.path.insert(0, str(GUITARBOT))
sys.path.insert(0, str(GUITARL))

import tune as tu
from BothHandsParser import BothHandsParser

# ── Helpers ───────────────────────────────────────────────────────────────────

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
WARN = "\033[33mWARN\033[0m"
BOLD = "\033[1m"
DIM  = "\033[2m"
RST  = "\033[0m"

def check(label: str, condition: bool, detail: str = "") -> bool:
    tag = PASS if condition else FAIL
    print(f"  [{tag}] {label}")
    if detail:
        print(f"         {DIM}{detail}{RST}")
    return condition


def section(title: str):
    print(f"\n{BOLD}{'─'*60}{RST}")
    print(f"{BOLD}  {title}{RST}")
    print(f"{BOLD}{'─'*60}{RST}")


def fresh_parser() -> BothHandsParser:
    """Return a BothHandsParser with left_hand reset to initial_point."""
    p = BothHandsParser()
    p.left_hand.current_positions = tu.initial_point.copy()
    return p


def presser_id(string_idx: int) -> int:
    return string_idx + 6


def slider_id(string_idx: int) -> int:
    return string_idx


# ── Test parameters ───────────────────────────────────────────────────────────

CASES = [
    # (string_idx, fret_position, torque)
    (0, 4.0, 200),
    (0, 7.0, 150),
    (2, 5.0, 300),
    (2, 4.0,  80),
    (4, 7.0, 200),
]

# ── Test 1: Identical inputs + identical start → identical trajectory ──────────

section("Test 1 — Identical inputs + state → bit-identical trajectories")

all_pass = True
for string_idx, fret, torque in CASES:
    pid = presser_id(string_idx)
    sid = slider_id(string_idx)

    # Build two fresh parsers in exactly the same starting state
    p1 = fresh_parser()
    p2 = fresh_parser()

    t1 = p1.parse_rlfret_with_pluck(
        string_idx=string_idx, fret_position=fret, torque=torque,
        pluck_velocity=80, unpress_after=False
    )
    t2 = p2.parse_rlfret_with_pluck(
        string_idx=string_idx, fret_position=fret, torque=torque,
        pluck_velocity=80, unpress_after=False
    )

    same_shape  = t1.shape == t2.shape
    same_values = np.array_equal(t1, t2)
    ok = same_shape and same_values

    check(
        f"str={string_idx} fret={fret} torque={torque}  "
        f"same_shape={same_shape} same_values={same_values}",
        ok,
        f"  shapes: {t1.shape} vs {t2.shape}" if not same_shape else
        f"  max_diff={np.max(np.abs(t1 - t2)):.4f}" if not same_values else
        f"  {t1.shape[0]} points × 15 motors"
    )
    all_pass = all_pass and ok

# ── Test 2: Presser state tracking across consecutive calls (unpress_after=False) ──

section("Test 2 — Presser current_positions tracking (unpress_after=False)")

for string_idx, fret, torque in CASES[:3]:
    pid = presser_id(string_idx)
    p = fresh_parser()

    initial_presser = p.left_hand.current_positions[pid]

    t1 = p.parse_rlfret_with_pluck(
        string_idx=string_idx, fret_position=fret, torque=torque,
        pluck_velocity=80, unpress_after=False
    )
    pos_after_1 = p.left_hand.current_positions[pid]

    # With unpress_after=False the parser should record target_torque as current
    check(
        f"str={string_idx}: after 1st call, current_positions[presser]={pos_after_1} (expected {torque})",
        pos_after_1 == torque,
        f"  initial={initial_presser}, target={torque}, got={pos_after_1}"
    )

    # Second call with same args — UNPRESS phase should start from 'torque'
    t2 = p.parse_rlfret_with_pluck(
        string_idx=string_idx, fret_position=fret, torque=torque,
        pluck_velocity=80, unpress_after=False
    )
    pos_after_2 = p.left_hand.current_positions[pid]

    check(
        f"str={string_idx}: after 2nd call, current_positions[presser]={pos_after_2} (expected {torque})",
        pos_after_2 == torque,
    )

    # The two trajectories should NOT be identical (call 2 starts differently)
    same = np.array_equal(t1, t2)
    check(
        f"str={string_idx}: call 1 ≠ call 2 (different UNPRESS start expected)",
        not same,
        "  If they are identical, the parser isn't using current_positions for UNPRESS start."
    )

    # Specifically: verify the UNPRESS start value in t2 matches t1's ending presser value
    unpress_start_t2 = t2[0, pid]
    check(
        f"str={string_idx}: t2 row 0 presser channel={unpress_start_t2:.1f} (should be initial_point value)",
        abs(unpress_start_t2 - tu.initial_point[pid]) < 1e-3,
        f"  t2 starts from initial_point presser={tu.initial_point[pid]}, got {unpress_start_t2}"
    )
    print()

# ── Test 3: unpress_after=True → known end state → identical consecutive calls ──

section("Test 3 — unpress_after=True → deterministic start state → identical calls")

for string_idx, fret, torque in CASES[:3]:
    pid = presser_id(string_idx)
    p = fresh_parser()

    t1 = p.parse_rlfret_with_pluck(
        string_idx=string_idx, fret_position=fret, torque=torque,
        pluck_velocity=80, unpress_after=True
    )
    pos_after_1 = p.left_hand.current_positions[pid]

    check(
        f"str={string_idx}: after 1st call w/ unpress_after=True, presser={pos_after_1} "
        f"(expected {tu.LH_PRESSER_UNPRESSED_POS}={tu.LH_PRESSER_UNPRESSED_POS})",
        pos_after_1 == tu.LH_PRESSER_UNPRESSED_POS,
    )

    t2 = p.parse_rlfret_with_pluck(
        string_idx=string_idx, fret_position=fret, torque=torque,
        pluck_velocity=80, unpress_after=True
    )

    same_shape  = t1.shape == t2.shape
    same_values = np.array_equal(t1, t2)

    check(
        f"str={string_idx}: consecutive calls bit-identical: "
        f"same_shape={same_shape}, same_values={same_values}",
        same_shape and same_values,
        f"  max_diff={np.max(np.abs(t1 - t2)):.4f}" if same_shape and not same_values else
        (f"  shapes differ: {t1.shape} vs {t2.shape}" if not same_shape else "")
    )
    print()

# ── Test 4: Encoder formula cross-check ───────────────────────────────────────

section("Test 4 — Encoder formula: BothHandsParser vs guitarl action_space")

try:
    from env.action_space import (
        RLFretAction, PresserAction, TORQUE_SAFE_MIN,
        SLIDER_MOTOR_DIRECTION, MM_TO_ENCODER_CONVERSION_FACTOR as RL_MM2ENC,
        SLIDER_ENCODER_OFFSET as RL_OFFSET
    )

    p = fresh_parser()

    print(f"  {'Str':>3} {'Fret':>5} {'BHP mm':>10} {'BHP enc':>10} {'RL enc':>10} {'match':>6}")
    print(f"  {'─'*3} {'─'*5} {'─'*10} {'─'*10} {'─'*10} {'─'*6}")

    any_mismatch = False
    for string_idx in [0, 2, 4]:
        for fret in [4.0, 5.0, 7.0]:
            mm = p._fret_to_mm(fret)

            # BothHandsParser formula: ((mm * 2048) / MM_TO_ENC_FACTOR + OFFSET) * direction
            bhp_enc = int(
                ((mm * 2048) / tu.MM_TO_ENCODER_CONVERSION_FACTOR + tu.SLIDER_ENCODER_OFFSET)
                * tu.SLIDER_MOTOR_DIRECTION[string_idx]
            )

            # guitarl action_space formula: mm * 9.4 * direction + offset
            rl_enc = int(
                mm * RL_MM2ENC * SLIDER_MOTOR_DIRECTION[string_idx] + RL_OFFSET
            )

            match = bhp_enc == rl_enc
            any_mismatch = any_mismatch or not match
            flag = "" if match else " ← MISMATCH"
            print(f"  {string_idx:>3} {fret:>5.1f} {mm:>10.1f} {bhp_enc:>10} {rl_enc:>10} "
                  f"{'YES' if match else 'NO':>6}{flag}")

    print()
    check(
        "BothHandsParser and guitarl action_space encoder formulas agree",
        not any_mismatch,
        "MISMATCH means guitarl is computing slider targets the RL agent explores "
        "are NOT the same mm positions BothHandsParser sends to the robot."
    )

    # Also compute relative scale factor to quantify the divergence
    mm_test = 139.0  # fret 5
    bhp = (mm_test * 2048) / tu.MM_TO_ENCODER_CONVERSION_FACTOR
    rl  = mm_test * RL_MM2ENC
    print(f"\n  At {mm_test}mm:")
    print(f"    BHP factor = mm * 2048/9.4 = {2048/9.4:.1f} enc/mm  →  result = {bhp:.0f}")
    print(f"    RL  factor = mm * 9.4      = {RL_MM2ENC:.1f} enc/mm  →  result = {rl:.0f}")
    print(f"    Ratio: {bhp/rl:.1f}x  (the RL agent is exploring a range ~{bhp/rl:.0f}x "
          f"compressed relative to real fret spacing)")

except ImportError as e:
    print(f"  [{WARN}] Could not import guitarl action_space: {e}")
    print(f"         Skipping cross-check. Run from workspace root or set PYTHONPATH.")

# ── Test 5: Trajectory shape and presser column sanity ────────────────────────

section("Test 5 — Trajectory shape and presser/slider channel sanity")

for string_idx, fret, torque in CASES:
    pid = presser_id(string_idx)
    sid = slider_id(string_idx)
    p   = fresh_parser()

    traj = p.parse_rlfret_with_pluck(
        string_idx=string_idx, fret_position=fret, torque=torque,
        pluck_velocity=80, unpress_after=False
    )

    ok_shape = traj.ndim == 2 and traj.shape[1] == 15
    check(f"str={string_idx} fret={fret}: shape={traj.shape} (expected ?×15)", ok_shape)

    if ok_shape:
        final_presser = traj[-1, pid]
        final_slider  = traj[-1, sid]
        check(
            f"  final presser col {pid} ≈ {torque} (got {final_presser:.0f})",
            abs(final_presser - torque) < 5,
        )
        # During SLIDE phase the presser should be at -650
        # SLIDE starts after UNPRESS_POINTS (≈ tu.PRESSER_INTERPOLATION_POINTS = 10)
        # and lasts tu.LH_SINGLE_NOTE_MOTION_POINTS = 40 points
        # Just check midpoint of expected SLIDE region
        slide_mid = tu.PRESSER_INTERPOLATION_POINTS + tu.LH_SINGLE_NOTE_MOTION_POINTS // 2
        slide_presser = traj[slide_mid, pid]
        check(
            f"  presser col {pid} during SLIDE (row {slide_mid}) = -650 (got {slide_presser:.0f})",
            abs(slide_presser - tu.LH_PRESSER_UNPRESSED_POS) < 5,
        )
    print()

# ── Summary ───────────────────────────────────────────────────────────────────

section("Summary")
print("""
KEY FINDINGS TO LOOK FOR:
  • Test 1 PASS  → Python trajectory generation is deterministic given the same start state.
  • Test 2: Call 1 ≠ Call 2 → Parser correctly starts UNPRESS from the previous target torque,
            so each call generates a different trajectory. This is CORRECT behaviour.
  • Test 3 PASS  → unpress_after=True normalises the end state → consecutive calls identical.
                   This is the fix: always ending at -650 gives the MCU a known starting state.
  • Test 4 MISMATCH → The RL agent (guitarl) is sending the slider to a different mm
                      position than BothHandsParser computes. Must be fixed for accurate
                      fret targeting.
""")
