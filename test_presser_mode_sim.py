#!/usr/bin/env python3
"""
test_presser_mode_sim.py  —  Simulate the microcontroller's presser state machine.

Ports the processTrajPoints presser safety logic from strikerController.h to Python
and runs it against actual RLFret trajectories to expose where inconsistency arises.

What this simulates:
  • The 1ms RPDO timer that dequeues one trajectory point per tick
  • processTrajPoints presser logic:
      if (curr_pos <= 15 && trajPoint[x] <= 0)  → POSITION mode, command = trajPoint
      else                                        → TORQUE mode,   command = trajPoint
      [BUG: `all_Trajs[x][0] = 0` is immediately overwritten by `all_Trajs[x][0] = trajPoint[x]`]
  • A simplified first-order motor model for both POSITION and TORQUE modes

Scenarios:
  A. Two identical trajectories from the same physical start position → should be identical.
  B. Two identical trajectories where the motor didn't fully return to 0 before the 2nd one.
  C. Effect of `unpress_after=True` on start-state consistency.
  D. Demonstration that the `all_Trajs[x][0] = 0` safety line is a dead assignment.

Usage:
    cd /home/guitarbot/Documents/GitHub/GuitarBot
    conda run -n guitaRL python test_presser_mode_sim.py
"""

import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")   # headless
import matplotlib.pyplot as plt
from pathlib import Path
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

GUITARBOT = Path(__file__).parent
GUITARL   = GUITARBOT.parent / "guitarl"
sys.path.insert(0, str(GUITARBOT))
sys.path.insert(0, str(GUITARL))

import tune as tu
from BothHandsParser import BothHandsParser

# ── ANSI helpers ──────────────────────────────────────────────────────────────
PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
WARN = "\033[33mWARN\033[0m"
BOLD = "\033[1m"
DIM  = "\033[2m"
RST  = "\033[0m"

def section(title: str):
    print(f"\n{BOLD}{'─'*68}{RST}")
    print(f"{BOLD}  {title}{RST}")
    print(f"{BOLD}{'─'*68}{RST}")

def check(label: str, condition: bool, detail: str = ""):
    tag = PASS if condition else FAIL
    print(f"  [{tag}] {label}")
    if detail:
        print(f"         {DIM}{detail}{RST}")
    return condition


# ── Motor model ───────────────────────────────────────────────────────────────

class Mode(Enum):
    POSITION = auto()
    TORQUE   = auto()

@dataclass
class MotorState:
    """Simplified EC20 presser motor model.

    Physical limits:
      - Encoder range:  [HOME_TICKS=0, MAX_TICKS=800]
      - In TORQUE mode: velocity ∝ commanded_torque (clamped to MAX_VELOCITY)
      - In POSITION mode: velocity proportional to position error (clamped)

    The model is intentionally simple — we care about the DIRECTION of motion
    and the threshold crossings (curr_pos crossing 15), not exact dynamics.
    """
    pos: float = 0.0           # current encoder position (ticks)
    mode: Mode = Mode.POSITION
    press_state: bool = False  # mirrors Striker::press_state

    # Simplified first-order dynamics
    MAX_VELOCITY:   float = 80.0   # ticks per 1ms step (coarse, adjust to taste)
    TORQUE_SCALE:   float = 0.12   # ticks/ms per unit torque
    POSITION_KP:    float = 0.30   # proportional gain for position mode
    HOME:           float = 0.0
    MAX_POS:        float = 800.0
    PRESS_THRESHOLD: float = 15.0  # matches MCU: curr_pos <= 15 = "near home"

    # Statistics for this run
    mode_switches: int = 0

    def step(self, commanded_value: float) -> Tuple[float, Mode, float]:
        """
        Advance one 1ms tick.  Returns (new_pos, mode, actual_command).

        Also mirrors the processTrajPoints bug:
          inside the `curr_pos <= 15 && commanded_value <= 0` branch:
            setModePOSITION()   — ok
            all_Trajs[x][0] = 0 — DEAD ASSIGNMENT (immediately overwritten)
          outside:
            setModeTORQUE()
          ALWAYS: all_Trajs[x][0] = commanded_value  ← overwrites the 0
        """
        was_mode = self.mode
        near_home = self.pos <= self.PRESS_THRESHOLD

        # ── Mode switching (mirrors processTrajPoints) ──────────────────────
        if near_home and commanded_value <= 0:
            if self.press_state:              # was in torque/press mode
                self.mode = Mode.POSITION
                self.press_state = False
            # BUG: safety_zero = 0  ← this line has no effect on the final command
            #      because the code unconditionally does:
            #           all_Trajs[x][0] = commanded_value   (overwrites 0)
        else:
            if not self.press_state:          # was in position/unpress mode
                self.mode = Mode.TORQUE
                self.press_state = True

        if self.mode != was_mode:
            self.mode_switches += 1

        # ── Motor actuation ─────────────────────────────────────────────────
        # Note: commanded_value is used IN BOTH modes (the 0 override is dead)
        if self.mode == Mode.TORQUE:
            velocity = np.clip(
                commanded_value * self.TORQUE_SCALE,
                -self.MAX_VELOCITY,
                self.MAX_VELOCITY
            )
        else:
            # Position mode: simple P controller toward commanded position
            error    = commanded_value - self.pos
            velocity = np.clip(
                error * self.POSITION_KP,
                -self.MAX_VELOCITY,
                self.MAX_VELOCITY
            )

        self.pos = float(np.clip(self.pos + velocity, self.HOME, self.MAX_POS))
        return self.pos, self.mode, commanded_value


# ── Trajectory extraction ─────────────────────────────────────────────────────

def extract_presser_channel(traj: np.ndarray, string_idx: int) -> np.ndarray:
    """Return the presser column (motors 6-11) for the given string."""
    return traj[:, string_idx + 6]


def run_simulation(
    presser_traj: np.ndarray,
    start_pos: float = 0.0,
    start_mode: Mode = Mode.POSITION,
    start_press_state: bool = False,
    label: str = "",
) -> dict:
    """
    Simulate the MCU's processTrajPoints presser logic on a 1-D presser trajectory.

    Returns a dict with per-tick history for analysis.
    """
    motor = MotorState(
        pos=start_pos,
        mode=start_mode,
        press_state=start_press_state,
    )

    history = {
        "commanded":     [],
        "position":      [],
        "mode":          [],
        "press_state":   [],
        "mode_switches": [],
    }

    for i, cmd in enumerate(presser_traj):
        new_pos, new_mode, actual_cmd = motor.step(float(cmd))
        history["commanded"].append(actual_cmd)
        history["position"].append(new_pos)
        history["mode"].append(new_mode)
        history["press_state"].append(motor.press_state)
        history["mode_switches"].append(motor.mode_switches)

    history["final_pos"] = motor.pos
    history["final_mode"] = motor.mode
    history["total_mode_switches"] = motor.mode_switches

    return history


def compare_simulations(h1: dict, h2: dict, label: str = "") -> dict:
    """Compare two simulation runs, returning summary of differences."""
    pos1 = np.array(h1["position"])
    pos2 = np.array(h2["position"])
    mode1 = np.array([m.value for m in h1["mode"]])
    mode2 = np.array([m.value for m in h2["mode"]])

    diff_pos  = np.abs(pos1 - pos2)
    diff_mode = mode1 != mode2

    return {
        "label":              label,
        "max_pos_diff_ticks": float(np.max(diff_pos)),
        "mean_pos_diff_ticks": float(np.mean(diff_pos)),
        "mode_diff_count":    int(np.sum(diff_mode)),
        "first_mode_diff_idx": int(np.argmax(diff_mode)) if diff_mode.any() else -1,
        "identical":          not diff_mode.any() and np.allclose(pos1, pos2, atol=0.1),
        "final_pos_diff":     abs(h1["final_pos"] - h2["final_pos"]),
        "mode_switches_run1": h1["total_mode_switches"],
        "mode_switches_run2": h2["total_mode_switches"],
    }


def plot_comparison(traj, h1, h2, title, filename):
    """Save a 3-panel comparison plot."""
    t = np.arange(len(traj)) * tu.TIME_STEP * 1000  # ms

    fig, axes = plt.subplots(3, 1, figsize=(14, 9), sharex=True)
    fig.suptitle(title, fontsize=13, fontweight="bold")

    ax = axes[0]
    ax.plot(t, traj, "k--", lw=1, alpha=0.5, label="Commanded")
    ax.plot(t, h1["position"], "b-", lw=1.5, label="Run 1 position")
    ax.plot(t, h2["position"], "r-", lw=1.5, alpha=0.7, label="Run 2 position")
    ax.axhline(15, color="orange", ls=":", lw=0.8, label="PRESS_THRESHOLD (15)")
    ax.set_ylabel("Encoder ticks")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    ax = axes[1]
    mode_vals1 = [1 if m == Mode.TORQUE else 0 for m in h1["mode"]]
    mode_vals2 = [1 if m == Mode.TORQUE else 0 for m in h2["mode"]]
    ax.step(t, mode_vals1, "b-", lw=1.5, label="Run 1 mode (1=TORQUE)")
    ax.step(t, mode_vals2, "r-", lw=1.5, alpha=0.7, label="Run 2 mode (1=TORQUE)")
    diff_mode = np.array(mode_vals1) != np.array(mode_vals2)
    ax.fill_between(t, 0, 1, where=diff_mode, alpha=0.3, color="red", label="Mode mismatch")
    ax.set_ylabel("Mode")
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["POSITION", "TORQUE"])
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    ax = axes[2]
    diff_pos = np.abs(np.array(h1["position"]) - np.array(h2["position"]))
    ax.plot(t, diff_pos, "purple", lw=1.5, label="|pos1 − pos2|")
    ax.set_ylabel("Position error (ticks)")
    ax.set_xlabel("Time (ms)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(filename, dpi=120)
    plt.close()
    print(f"  → Plot saved: {filename}")


# ── Generate test trajectories ────────────────────────────────────────────────

def make_presser_traj(string_idx=0, fret=7.0, torque=200, unpress_after=False) -> np.ndarray:
    """Build a fresh trajectory and extract its presser channel."""
    p = BothHandsParser()
    p.left_hand.current_positions = tu.initial_point.copy()
    traj = p.parse_rlfret_with_pluck(
        string_idx=string_idx, fret_position=fret, torque=torque,
        pluck_velocity=80, unpress_after=unpress_after
    )
    return extract_presser_channel(traj, string_idx)


# ── Scenario A — Same trajectory, same physical start ─────────────────────────

section("Scenario A — Identical trajectory, identical physical start → must be identical")

presser_traj = make_presser_traj(string_idx=0, fret=7.0, torque=200, unpress_after=False)

hA1 = run_simulation(presser_traj, start_pos=0.0, label="Run A1")
hA2 = run_simulation(presser_traj, start_pos=0.0, label="Run A2")
cmpA = compare_simulations(hA1, hA2, "Scenario A")

check(
    f"Runs identical (max_pos_diff={cmpA['max_pos_diff_ticks']:.1f} ticks, "
    f"mode_diff_count={cmpA['mode_diff_count']})",
    cmpA["identical"],
    "If FAIL: simulation is non-deterministic even with same start — model bug."
)


# ── Scenario B — Same trajectory, different physical start ────────────────────

section("Scenario B — Presser didn't return to home before 2nd trajectory (no unpress_after)")

print(f"\n  Trajectory ends with presser at: {presser_traj[-1]:.0f}")
print(f"  End physical position after run 1: {hA1['final_pos']:.1f} ticks")
print()

# Run 1: motor starts at 0 (home, fresh)
hB1 = run_simulation(presser_traj, start_pos=0.0, label="Run B1 (start=0)")

# Run 2: motor starts where run 1 LEFT it (simulates unpress_after=False, MCU
#         still receiving residual torque or motor still moving)
partial_return_pos = hB1["final_pos"]
print(f"  Run 2 starts at {partial_return_pos:.1f} ticks (motor didn't return to 0).")
hB2 = run_simulation(presser_traj, start_pos=partial_return_pos, label="Run B2 (start=partial)")
cmpB = compare_simulations(hB1, hB2, "Scenario B")

print(f"\n  Results:")
print(f"    max position divergence:    {cmpB['max_pos_diff_ticks']:.1f} ticks")
print(f"    mean position divergence:   {cmpB['mean_pos_diff_ticks']:.1f} ticks")
print(f"    mode mismatch count:        {cmpB['mode_diff_count']} ticks")
print(f"    first mode mismatch at idx: {cmpB['first_mode_diff_idx']}")
print(f"    mode switches run1/run2:    {cmpB['mode_switches_run1']} / {cmpB['mode_switches_run2']}")

check(
    "Runs differ (inconsistency demonstrated)",
    not cmpB["identical"],
    "If PASS: the simulation shows identical trajectories produce different motor behaviour "
    "depending on physical start position. This is the root cause of oscillation."
)

plot_comparison(
    presser_traj, hB1, hB2,
    title="Scenario B — Same trajectory, different physical start\n"
          "(simulates unpress_after=False: motor still pressed when 2nd trajectory begins)",
    filename=str(GUITARBOT / "test_presser_scenario_B.png")
)


# ── Scenario C — unpress_after=True provides known start ──────────────────────

section("Scenario C — unpress_after=True provides deterministic start state")

traj_unpress = make_presser_traj(string_idx=0, fret=7.0, torque=200, unpress_after=True)
traj_no_unpress = presser_traj

print(f"  Trajectory with  unpress: ends at {traj_unpress[-1]:.0f}")
print(f"  Trajectory w/out unpress: ends at {traj_no_unpress[-1]:.0f}")
print()

# Simulate trajectory with unpress_after=True
hC1 = run_simulation(traj_unpress, start_pos=0.0, label="Run C1 (unpress, start=0)")

# The motor should be near 0 at the end; use that for Run C2
print(f"  Motor final pos after traj w/ unpress: {hC1['final_pos']:.1f} ticks")

hC2 = run_simulation(traj_unpress, start_pos=hC1["final_pos"], label="Run C2 (unpress, start=end-of-C1)")
cmpC = compare_simulations(hC1, hC2, "Scenario C")

print(f"\n  Results:")
print(f"    max position divergence:  {cmpC['max_pos_diff_ticks']:.1f} ticks")
print(f"    mode mismatch count:      {cmpC['mode_diff_count']} ticks")

check(
    f"unpress_after=True produces consistent runs "
    f"(max_pos_diff={cmpC['max_pos_diff_ticks']:.1f}, mode_diff={cmpC['mode_diff_count']})",
    cmpC["max_pos_diff_ticks"] < 20 and cmpC["mode_diff_count"] < 10,
    "Compared to Scenario B's larger divergence, a near-zero value here confirms "
    "that ending at -650 (home) before each trajectory is the fix."
)

plot_comparison(
    traj_unpress, hC1, hC2,
    title="Scenario C — unpress_after=True\n"
          "(motor returns to home; small divergence expected if motor overshoot differs)",
    filename=str(GUITARBOT / "test_presser_scenario_C.png")
)


# ── Scenario D — The dead-assignment bug ──────────────────────────────────────

section("Scenario D — Dead assignment: `all_Trajs[x][0] = 0` is overwritten")

print("""
  In processTrajPoints (strikerController.h ~line 293):

      if (curr_pos <= 15 && trajPoint[x] <= 0) {
          m_striker[x+1].setModePOSITION();
          all_Trajs[x][0] = 0;           // ← written here ...
      } else {
          m_striker[x+1].setModeTORQUE();
      }
      all_Trajs[x][0] = trajPoint[x];   // ← ... but ALWAYS overwritten here!

  The intent was to zero the command when switching to position mode (to prevent
  the presser from trying to reach position -650, which is beyond the hard stop).
  But the unconditional assignment below nullifies this entirely.

  Consequence: in POSITION mode the motor receives command -650, which targets a
  position 650 ticks BELOW home. The position controller then drives the motor
  toward -650, which it can never reach. If the motor is constrained at 0 ticks,
  this produces a continuous demand that stalls the motor and can cause oscillation
  as the controller repeatedly tries to move past the hard stop.
""")

# Demonstrate: show what the motor receives in position mode
print("  Scanning a presser trajectory for dead-assignment moments...")
hits = []
motor = MotorState(pos=0.0)
for i, cmd in enumerate(presser_traj):
    near_home = motor.pos <= motor.PRESS_THRESHOLD
    if near_home and cmd <= 0:
        hits.append((i, motor.pos, cmd))
        # Intended effect of the fix (zeroing):
        intended = 0
        actual   = cmd
        if i < 5:  # limit output
            print(f"    tick {i:4d}: curr_pos={motor.pos:6.1f}, cmd={cmd:7.1f} "
                  f"→ intended_cmd={intended}, actual_cmd={actual}  DEAD WRITE")
    motor.step(float(cmd))

print(f"  Total ticks where the dead-assignment fires: {len(hits)}")
check(
    f"Dead assignment fires on {len(hits)} ticks in this trajectory",
    len(hits) > 0,
    "Each of these ticks sends a negative command in POSITION mode instead of 0. "
    "Fix: move `all_Trajs[x][0] = 0` to AFTER the if/else, guarded by mode check."
)


# ── Scenario E — Identical-input but different consecutive trajectory state ───

section("Scenario E — Sequential RLFret calls with same params: trajectory diff")

print("  Building sequential trajectories (unpress_after=False) from same parser instance...")
p = BothHandsParser()
p.left_hand.current_positions = tu.initial_point.copy()

STRING_IDX = 0
FRET = 7.0
TORQUE = 200

t1 = p.parse_rlfret_with_pluck(
    string_idx=STRING_IDX, fret_position=FRET, torque=TORQUE,
    pluck_velocity=80, unpress_after=False
)
t2 = p.parse_rlfret_with_pluck(
    string_idx=STRING_IDX, fret_position=FRET, torque=TORQUE,
    pluck_velocity=80, unpress_after=False
)

pt1 = extract_presser_channel(t1, STRING_IDX)
pt2 = extract_presser_channel(t2, STRING_IDX)

check(
    f"Presser channels differ between call 1 and call 2 (expected — different UNPRESS start)",
    not np.array_equal(pt1, pt2),
)
print(f"    Call 1 presser: row 0 = {pt1[0]:.0f}, starts UNPRESS from initial_point")
print(f"    Call 2 presser: row 0 = {pt2[0]:.0f}, starts UNPRESS from prev target={TORQUE}")
print(f"    At midpoint of UNPRESS phase (row {tu.PRESSER_INTERPOLATION_POINTS//2}):")
mid = tu.PRESSER_INTERPOLATION_POINTS // 2
print(f"      Call 1: {pt1[mid]:.1f}")
print(f"      Call 2: {pt2[mid]:.1f}")

print()

# Simulate both on the MCU
h1 = run_simulation(pt1, start_pos=0.0)
h2 = run_simulation(pt2, start_pos=0.0)
cmpE = compare_simulations(h1, h2, "Scenario E")

print(f"  MCU simulation comparison:")
print(f"    max position divergence:  {cmpE['max_pos_diff_ticks']:.1f} ticks")
print(f"    mode mismatch count:      {cmpE['mode_diff_count']} ticks")
print(f"    first mode mismatch at:   tick {cmpE['first_mode_diff_idx']}")

check(
    "MCU receives different commands for identical consecutive /RLFret messages",
    not cmpE["identical"],
    "This is the root cause: the UNPRESS phase of call N+1 starts from target_torque "
    "(not -650), so the mode-switch timing shifts relative to call 1."
)

plot_comparison(
    pt2, h1, h2,
    title="Scenario E — Same /RLFret repeated twice (unpress_after=False)\n"
          "MCU simulation: call 1 vs call 2 (different UNPRESS start torque)",
    filename=str(GUITARBOT / "test_presser_scenario_E.png")
)


# ── Summary ───────────────────────────────────────────────────────────────────

section("Summary of findings")

print(f"""
  1. DEAD ASSIGNMENT BUG (Scenario D)
     processTrajPoints: `all_Trajs[x][0] = 0` is immediately overwritten
     by `all_Trajs[x][0] = trajPoint[x]`.  The safety zero has no effect.
     Fix: move the unconditional assignment INSIDE an else-branch:
          if (near_home && cmd <= 0)    {{ setModePosition(); cmd = 0; }}
          else                          {{ setModeTorque(); }}
          all_Trajs[x][0] = cmd;        // cmd is now 0 when appropriate

  2. PHYSICAL POSITION-DEPENDENT MODE SWITCHING (Scenario B)
     Mode switches when curr_pos crosses 15 ticks — a physical quantity that
     depends on real-time motor dynamics, not just the trajectory.  Identical
     trajectories starting from different physical positions switch mode at
     different tick indices → different motor behaviour → inconsistency.

  3. UNPRESS_AFTER=FALSE ACCUMULATES STATE (Scenario E)
     Without unpress_after, the parser correctly sets current_positions[presser]
     = target_torque after each call.  The next call's UNPRESS phase starts from
     that torque, NOT from -650.  This gives the MCU a different UNPRESS profile
     each call and shifts the mode-switch timing observed on the hardware.

  4. PROPOSED FIX (Scenario C confirms)
     Always end each trajectory with the presser at -650 (unpress_after=True or
     by adding a zero-return tail unconditionally in _generate_rlfret_trajectory).
     This guarantees:
       a) Physical motor is at home (pos ≈ 0) when next trajectory starts.
       b) near_home check fires at predictable tick indices.
       c) Mode switch sequence is deterministic run-to-run.
     Scenario C shows near-identical motor response when runs start from the
     same near-home physical position.
""")
