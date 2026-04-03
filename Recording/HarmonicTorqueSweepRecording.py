#!/usr/bin/env python3
"""Record harmonic torque sweeps with paired trajectory and audio artifacts.

This script targets natural harmonics on string 0 at fret 7 by default.
For each torque datapoint it:
1) Generates the expected trajectory using BothHandsParser.
2) Saves trajectory as .npy and .csv with a labeled filename.
3) Records audio while sending /RLFret to the receiver.
4) Stores metadata linking torque, trajectory file, and audio file.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from BothHandsParser import BothHandsParser
from RecordingTestSession import RecordingTestSession


def _parse_torque_list(raw: str) -> list[int]:
    values: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        values.append(int(float(part)))
    if not values:
        raise ValueError("No torque values parsed from --torques")
    return values


def _torques_from_args(args: argparse.Namespace) -> list[int]:
    if args.torques:
        return _parse_torque_list(args.torques)

    if args.step <= 0:
        raise ValueError("--step must be > 0")

    values = list(range(int(args.start), int(args.stop) + 1, int(args.step)))
    if not values:
        raise ValueError("Generated torque sweep is empty")
    return values


def _save_trajectory_artifacts(
    trajectory: np.ndarray,
    output_dir: Path,
    label: str,
) -> tuple[str, str, int, float]:
    output_dir.mkdir(parents=True, exist_ok=True)

    npy_name = f"{label}_trajectory.npy"
    csv_name = f"{label}_trajectory.csv"
    npy_path = output_dir / npy_name
    csv_path = output_dir / csv_name

    np.save(npy_path, trajectory)
    np.savetxt(csv_path, trajectory, delimiter=",", fmt="%.6f")

    duration_s = float(trajectory.shape[0] * 0.005)
    return npy_name, csv_name, int(trajectory.shape[0]), duration_s


def run_harmonic_torque_sweep(args: argparse.Namespace) -> dict:
    torques = _torques_from_args(args)

    session = RecordingTestSession(
        osc_ip=args.osc_ip,
        osc_port=args.osc_port,
        sample_rate=args.sample_rate,
        output_dir=args.output_dir,
        session_name=args.session_name,
    )

    # Disable runtime trajectory plotting for unattended sweep stability/speed.
    session.send_osc_message("/Config", ["graph", False])
    # Match runtime fretting behavior to the sweep profile under test.
    session.send_osc_message("/Config", ["direct_press", bool(args.direct_press)])
    session.send_osc_message("/Config", ["unpress_after", bool(args.unpress_after)])
    time.sleep(1)

    # Allow script-level control of recording window.
    session.pre_trigger_time = args.pre_trigger
    session.post_trigger_time = args.post_trigger

    trajectories_dir = session.session_dir / "trajectories"
    trajectories_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 64)
    print("HARMONIC TORQUE SWEEP RECORDING")
    print(f"String index: {args.string_index}")
    print(f"Fret: {args.fret_position}")
    print(f"Torques: {torques}")
    print(f"Repetitions per torque: {args.repetitions}")
    print(f"Output session: {session.session_dir}")
    print("=" * 64 + "\n")

    total_tests = len(torques) * args.repetitions
    completed = 0

    sweep_rows: list[dict] = []

    for rep in range(1, args.repetitions + 1):
        rep_torques = list(torques)
        if args.randomize_torques:
            random.shuffle(rep_torques)

        for torque in rep_torques:
            completed += 1
            label = (
                f"harm_s{args.string_index}_f{args.fret_position:.2f}"
                f"_t{int(torque):03d}_r{rep:02d}"
            )

            print(f"[{completed}/{total_tests}] {label}")

            parser = BothHandsParser()
            trajectory = parser.parse_rlfret_with_pluck(
                string_idx=args.string_index,
                fret_position=float(args.fret_position),
                torque=float(torque),
                pluck_velocity=(None if args.pluck_velocity < 0 else int(args.pluck_velocity)),
                timestamp=0.0,
                unpress_after=bool(args.unpress_after),
                direct_press=bool(args.direct_press),
            )

            if trajectory.size == 0:
                raise RuntimeError(f"Failed to generate trajectory for {label}")

            traj_npy, traj_csv, traj_points, traj_duration_s = _save_trajectory_artifacts(
                trajectory=trajectory,
                output_dir=trajectories_dir,
                label=label,
            )

            osc_data = [
                int(args.string_index),
                float(args.fret_position),
                float(torque),
            ]
            if args.pluck_velocity >= 0:
                osc_data.append(int(args.pluck_velocity))

            test_info = {
                "test_type": "harmonic_torque_sweep",
                "parameter": label,
                "string_index": int(args.string_index),
                "fret_position": float(args.fret_position),
                "torque": float(torque),
                "repetition": int(rep),
                "total_repetitions": int(args.repetitions),
                "sweep_progress": f"{completed}/{total_tests}",
                "trajectory_npy_file": traj_npy,
                "trajectory_csv_file": traj_csv,
                "trajectory_points": traj_points,
                "trajectory_duration_s": traj_duration_s,
                "direct_press": bool(args.direct_press),
                "unpress_after": bool(args.unpress_after),
            }

            result = session.execute_test("/RLFret", osc_data, test_info)

            sweep_rows.append(
                {
                    "label": label,
                    "string_index": args.string_index,
                    "fret_position": args.fret_position,
                    "torque": torque,
                    "repetition": rep,
                    "trajectory_npy_file": traj_npy,
                    "trajectory_csv_file": traj_csv,
                    "audio_file": result.get("audio_file", ""),
                    "metadata_file": result.get("metadata_file", ""),
                    "trajectory_points": traj_points,
                    "trajectory_duration_s": traj_duration_s,
                    "direct_press": bool(args.direct_press),
                    "unpress_after": bool(args.unpress_after),
                }
            )

            if completed < total_tests and args.delay_between > 0:
                print(f"Waiting {args.delay_between:.2f}s before next datapoint...")
                time.sleep(args.delay_between)

    # Export standard session summary files.
    session.close_session()

    # Export a compact sweep manifest linking trajectory/audio by label.
    manifest_json = session.session_dir / "harmonic_torque_manifest.json"
    manifest_csv = session.session_dir / "harmonic_torque_manifest.csv"

    manifest = {
        "session_name": session.session_name,
        "session_dir": str(session.session_dir),
        "string_index": int(args.string_index),
        "fret_position": float(args.fret_position),
        "torques": torques,
        "repetitions": int(args.repetitions),
        "rows": sweep_rows,
    }

    with open(manifest_json, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    with open(manifest_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(sweep_rows[0].keys()))
        writer.writeheader()
        writer.writerows(sweep_rows)

    print("\nSweep complete")
    print(f"Manifest JSON: {manifest_json}")
    print(f"Manifest CSV:  {manifest_csv}")

    return manifest


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record harmonic audio+trajectory sweep over /RLFret torques"
    )
    parser.add_argument("--osc-ip", default="127.0.0.1", help="OSC receiver IP")
    parser.add_argument("--osc-port", type=int, default=12000, help="OSC receiver port")
    parser.add_argument("--sample-rate", type=int, default=44100, help="Audio sample rate")
    parser.add_argument("--output-dir", default=None, help="Optional output root directory")
    parser.add_argument(
        "--session-name",
        default="harmonic_torque_sweep_e_string_fret7",
        help="Session name prefix",
    )

    parser.add_argument("--string-index", type=int, default=0, help="Playable string index")
    parser.add_argument("--fret-position", type=float, default=7.0, help="Target fret position")
    parser.add_argument(
        "--pluck-velocity",
        type=int,
        default=65,
        help="Optional pluck velocity (set <0 to omit velocity field)",
    )

    parser.add_argument(
        "--torques",
        default="",
        help="Comma-separated torques, e.g. '30,50,70,90'. If empty, uses start/stop/step.",
    )
    parser.add_argument("--start", type=int, default=35, help="Start torque (inclusive)")
    parser.add_argument("--stop", type=int, default=80, help="Stop torque (inclusive)")
    parser.add_argument("--step", type=int, default=2, help="Torque step")

    parser.add_argument("--repetitions", type=int, default=3, help="Repetitions per torque")
    parser.add_argument(
        "--randomize-torques",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Randomize torque order each repetition to reduce drift/heating bias",
    )
    parser.add_argument(
        "--direct-press",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Use direct presser ramp mode (default: off for harmonic consistency sweeps)",
    )
    parser.add_argument(
        "--unpress-after",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Unpress after pluck (default: on)",
    )
    parser.add_argument("--delay-between", type=float, default=3.0, help="Delay between datapoints (s)")
    parser.add_argument("--pre-trigger", type=float, default=0.5, help="Audio pre-trigger duration (s)")
    parser.add_argument("--post-trigger", type=float, default=5.0, help="Audio post-trigger duration (s)")
    return parser


if __name__ == "__main__":
    args = _build_arg_parser().parse_args()
    run_harmonic_torque_sweep(args)
