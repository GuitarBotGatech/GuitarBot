from __future__ import annotations

import argparse
import contextlib
import copy
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np

import tune as tu
from GuitarBotParser import GuitarBotParser
from parsing.song_arrangement import SongArrangement
from pluck_message_to_json import load_pluck_message_from_python_file


@dataclass
class OscPayload:
    chords: list[list[Any]]
    pluck: list[list[Any]]
    midi: list[list[Any]]


@dataclass
class HarnessContext:
    python_payload: OscPayload
    json_payload: OscPayload
    python_trajectory: np.ndarray
    json_trajectory: np.ndarray


class Analyzer(Protocol):
    name: str

    def analyze(self, context: HarnessContext) -> dict[str, Any]:
        ...


def _round_num(value: Any, digits: int = 6) -> float:
    return round(float(value), digits)


def normalize_pluck_row(row: list[Any]) -> tuple[int, float, float, int, int | None, float]:
    if len(row) == 5:
        note, duration, speed, slide, timestamp = row
        string_index = None
    elif len(row) == 6:
        note, duration, speed, slide, string_index, timestamp = row
        string_index = int(string_index)
    else:
        raise ValueError(f"Expected pluck row with 5 or 6 elements, got {len(row)}: {row!r}")

    return (
        int(note),
        _round_num(duration),
        _round_num(speed),
        int(slide),
        string_index,
        _round_num(timestamp),
    )


def normalize_pluck_rows(rows: list[list[Any]]) -> list[tuple[int, float, float, int, int | None, float]]:
    normalized = [normalize_pluck_row(row) for row in rows]
    return sorted(normalized, key=lambda row: (row[5], row[0], row[1], row[3], -1 if row[4] is None else row[4]))


def load_json_payload(path: str | Path) -> OscPayload:
    data = Path(path).read_text(encoding="utf-8")
    arrangement = SongArrangement.from_json_str(data)
    payload = arrangement.render_osc_payloads()
    return OscPayload(
        chords=payload.get("/Chords", []),
        pluck=payload.get("/Pluck", []),
        midi=payload.get("/Midi", []),
    )


def load_python_payload(path: str | Path, variable_name: str = "pluck_message") -> OscPayload:
    pluck_rows = load_pluck_message_from_python_file(path, variable_name=variable_name)
    return OscPayload(chords=[], pluck=pluck_rows, midi=[])


def compute_trajectory(payload: OscPayload, *, quiet: bool = True) -> np.ndarray:
    parser = GuitarBotParser(initial_point=copy.deepcopy(tu.initial_point), graph=False)
    if quiet:
        with contextlib.redirect_stdout(io.StringIO()):
            return parser.parseAllMIDI(payload.chords, payload.pluck, midi_events=None)
    return parser.parseAllMIDI(payload.chords, payload.pluck, midi_events=None)


def _derive_lh_pick_events(payload: OscPayload, *, quiet: bool = True) -> list[list[Any]]:
    parser = GuitarBotParser(initial_point=copy.deepcopy(tu.initial_point), graph=False)
    if quiet:
        with contextlib.redirect_stdout(io.StringIO()):
            lh_positions = parser.parseleftMIDI(payload.chords)
            pick_positions, slide_toggles = parser.parsePickMIDI(payload.pluck)
            pick_positions_adj = parser.prepPicker(lh_positions, pick_positions)
            _, lh_pick_events = parser.interpPick(pick_positions_adj, slide_toggles, copy.deepcopy(tu.initial_point))
            return lh_pick_events
    lh_positions = parser.parseleftMIDI(payload.chords)
    pick_positions, slide_toggles = parser.parsePickMIDI(payload.pluck)
    pick_positions_adj = parser.prepPicker(lh_positions, pick_positions)
    _, lh_pick_events = parser.interpPick(pick_positions_adj, slide_toggles, copy.deepcopy(tu.initial_point))
    return lh_pick_events


def _derive_pick_and_lh_pick_events(
    payload: OscPayload, *, quiet: bool = True
) -> tuple[list[list[Any]], list[list[Any]]]:
    parser = GuitarBotParser(initial_point=copy.deepcopy(tu.initial_point), graph=False)
    if quiet:
        with contextlib.redirect_stdout(io.StringIO()):
            lh_positions = parser.parseleftMIDI(payload.chords)
            pick_positions, slide_toggles = parser.parsePickMIDI(payload.pluck)
            pick_positions_adj = parser.prepPicker(lh_positions, pick_positions)
            _, lh_pick_events = parser.interpPick(pick_positions_adj, slide_toggles, copy.deepcopy(tu.initial_point))
            return pick_positions_adj, lh_pick_events

    lh_positions = parser.parseleftMIDI(payload.chords)
    pick_positions, slide_toggles = parser.parsePickMIDI(payload.pluck)
    pick_positions_adj = parser.prepPicker(lh_positions, pick_positions)
    _, lh_pick_events = parser.interpPick(pick_positions_adj, slide_toggles, copy.deepcopy(tu.initial_point))
    return pick_positions_adj, lh_pick_events


class PayloadFidelityAnalyzer:
    name = "payload_fidelity"

    def analyze(self, context: HarnessContext) -> dict[str, Any]:
        py_rows = normalize_pluck_rows(context.python_payload.pluck)
        json_rows = normalize_pluck_rows(context.json_payload.pluck)

        mismatches: list[dict[str, Any]] = []
        min_len = min(len(py_rows), len(json_rows))
        for index in range(min_len):
            if py_rows[index] != json_rows[index]:
                mismatches.append(
                    {
                        "index": index,
                        "python": py_rows[index],
                        "json": json_rows[index],
                    }
                )
                if len(mismatches) >= 10:
                    break

        pass_check = len(py_rows) == len(json_rows) and not mismatches
        return {
            "pass": pass_check,
            "python_events": len(py_rows),
            "json_events": len(json_rows),
            "mismatch_count": 0 if pass_check else max(abs(len(py_rows) - len(json_rows)), len(mismatches)),
            "mismatch_examples": mismatches,
            "python_slide_events": sum(1 for row in py_rows if row[3] == 1),
            "json_slide_events": sum(1 for row in json_rows if row[3] == 1),
        }


class TrajectoryDiffAnalyzer:
    name = "trajectory_diff"

    def __init__(self, *, tolerance: float = 1e-6):
        self.tolerance = tolerance

    def analyze(self, context: HarnessContext) -> dict[str, Any]:
        py = context.python_trajectory
        js = context.json_trajectory

        py_shape = tuple(int(value) for value in py.shape)
        json_shape = tuple(int(value) for value in js.shape)

        rows = min(py_shape[0], json_shape[0])
        cols = min(py_shape[1], json_shape[1])

        overlap = np.abs(py[:rows, :cols] - js[:rows, :cols]) if rows and cols else np.array([], dtype=float)
        max_abs_diff = float(np.max(overlap)) if overlap.size else 0.0
        mean_abs_diff = float(np.mean(overlap)) if overlap.size else 0.0

        pass_check = py_shape == json_shape and max_abs_diff <= self.tolerance
        return {
            "pass": pass_check,
            "tolerance": self.tolerance,
            "python_shape": py_shape,
            "json_shape": json_shape,
            "overlap_shape": (rows, cols),
            "max_abs_diff": max_abs_diff,
            "mean_abs_diff": mean_abs_diff,
        }


class SlideContinuityAnalyzer:
    name = "slide_continuity"

    def __init__(self, *, unpress_tolerance: float = 1e-6, quiet_parser_output: bool = True):
        self.unpress_tolerance = unpress_tolerance
        self.quiet_parser_output = quiet_parser_output

    def _analyze_payload(self, label: str, payload: OscPayload, trajectory: np.ndarray) -> dict[str, Any]:
        lh_pick_events = _derive_lh_pick_events(payload, quiet=self.quiet_parser_output)
        violations: list[dict[str, Any]] = []

        window_points = (2 * tu.PRESSER_INTERPOLATION_POINTS) + tu.LH_SINGLE_NOTE_MOTION_POINTS
        threshold = tu.LH_PRESSER_UNPRESSED_POS + self.unpress_tolerance

        for event in lh_pick_events:
            motor_id, _, slide_toggle, timestamp = event
            if int(slide_toggle) != 1:
                continue
            presser_column = int(motor_id) * 2 + 6
            start_idx = max(0, int(float(timestamp) / tu.TIME_STEP))
            end_idx = min(trajectory.shape[0], start_idx + window_points)
            if start_idx >= end_idx:
                continue

            segment = trajectory[start_idx:end_idx, presser_column]
            if segment.size == 0:
                continue

            min_value = float(np.min(segment))
            if min_value <= threshold:
                violations.append(
                    {
                        "motor_id": int(motor_id),
                        "timestamp": round(float(timestamp), 6),
                        "segment_start": start_idx,
                        "segment_end": end_idx,
                        "segment_min": min_value,
                    }
                )
                if len(violations) >= 20:
                    break

        slide_count = sum(1 for event in lh_pick_events if int(event[2]) == 1)
        return {
            "label": label,
            "slide_events_checked": slide_count,
            "violations": violations,
            "violation_count": len(violations),
            "pass": len(violations) == 0,
        }

    def analyze(self, context: HarnessContext) -> dict[str, Any]:
        python_result = self._analyze_payload("python", context.python_payload, context.python_trajectory)
        json_result = self._analyze_payload("json", context.json_payload, context.json_trajectory)
        return {
            "pass": python_result["pass"] and json_result["pass"],
            "python": python_result,
            "json": json_result,
        }


class TremoloReadinessAnalyzer:
    name = "tremolo_readiness"

    def __init__(
        self,
        *,
        slider_tolerance: int = 3,
        presser_ready_pos: int = tu.LH_PRESSER_PRESSED_POS,
        quiet_parser_output: bool = True,
    ):
        self.slider_tolerance = int(slider_tolerance)
        self.presser_ready_pos = int(presser_ready_pos)
        self.quiet_parser_output = quiet_parser_output

    def _analyze_payload(self, label: str, payload: OscPayload, trajectory: np.ndarray) -> dict[str, Any]:
        pick_events, lh_pick_events = _derive_pick_and_lh_pick_events(payload, quiet=self.quiet_parser_output)
        pick_by_timestamp = {round(float(ts), 3): event for event, ts in pick_events}

        checked = 0
        violations: list[dict[str, Any]] = []

        for motor_id, target_slider_pos, _, lh_start_ts in lh_pick_events:
            pick_ts = round(float(lh_start_ts) + float(tu.LH_PREP_TIME_BEFORE_PICK), 3)
            pick_event = pick_by_timestamp.get(round(pick_ts, 3))
            if pick_event is None:
                continue

            _, note, _, duration, _ = pick_event
            if float(duration) < float(tu.TREMOLO_DURATION_THRESHOLD):
                continue
            if int(note) <= 5:
                continue

            checked += 1

            slider_col = int(motor_id) * 2
            presser_col = int(motor_id) * 2 + 6
            start_idx = max(0, int(float(lh_start_ts) / tu.TIME_STEP))

            target_slider = int(target_slider_pos)
            if target_slider == -1:
                continue

            ready_idx = None
            for idx in range(start_idx, trajectory.shape[0]):
                slider_ok = abs(int(trajectory[idx, slider_col]) - target_slider) <= self.slider_tolerance
                presser_ok = float(trajectory[idx, presser_col]) >= float(self.presser_ready_pos)
                if slider_ok and presser_ok:
                    ready_idx = idx
                    break

            if ready_idx is None:
                violations.append(
                    {
                        "motor_id": int(motor_id),
                        "note": int(note),
                        "pick_timestamp": round(float(pick_ts), 6),
                        "reason": "never_ready",
                    }
                )
                continue

            ready_ts = ready_idx * tu.TIME_STEP
            delta_ms = (float(pick_ts) - float(ready_ts)) * 1000.0
            if delta_ms < 0:
                violations.append(
                    {
                        "motor_id": int(motor_id),
                        "note": int(note),
                        "pick_timestamp": round(float(pick_ts), 6),
                        "ready_timestamp": round(float(ready_ts), 6),
                        "early_by_ms": round(abs(float(delta_ms)), 3),
                    }
                )

        return {
            "label": label,
            "checked_tremolo_events": checked,
            "violation_count": len(violations),
            "violations": violations,
            "pass": len(violations) == 0,
            "config": {
                "slider_tolerance": self.slider_tolerance,
                "presser_ready_pos": self.presser_ready_pos,
                "tremolo_duration_threshold": tu.TREMOLO_DURATION_THRESHOLD,
            },
        }

    def analyze(self, context: HarnessContext) -> dict[str, Any]:
        python_result = self._analyze_payload("python", context.python_payload, context.python_trajectory)
        json_result = self._analyze_payload("json", context.json_payload, context.json_trajectory)
        return {
            "pass": python_result["pass"] and json_result["pass"],
            "python": python_result,
            "json": json_result,
        }


class TrajectoryHarness:
    def __init__(self, analyzers: list[Analyzer] | None = None, *, quiet_parser_output: bool = True):
        self.quiet_parser_output = quiet_parser_output
        self.analyzers = analyzers or [
            PayloadFidelityAnalyzer(),
            TrajectoryDiffAnalyzer(),
            SlideContinuityAnalyzer(quiet_parser_output=quiet_parser_output),
            TremoloReadinessAnalyzer(quiet_parser_output=quiet_parser_output),
        ]

    def run(self, *, python_payload: OscPayload, json_payload: OscPayload) -> dict[str, Any]:
        context = HarnessContext(
            python_payload=python_payload,
            json_payload=json_payload,
            python_trajectory=compute_trajectory(python_payload, quiet=self.quiet_parser_output),
            json_trajectory=compute_trajectory(json_payload, quiet=self.quiet_parser_output),
        )

        analyses: dict[str, dict[str, Any]] = {}
        for analyzer in self.analyzers:
            analyses[analyzer.name] = analyzer.analyze(context)

        overall_pass = all(result.get("pass", False) for result in analyses.values())
        return {
            "pass": overall_pass,
            "analyses": analyses,
            "python_payload": {
                "chords": len(python_payload.chords),
                "pluck": len(python_payload.pluck),
                "midi": len(python_payload.midi),
            },
            "json_payload": {
                "chords": len(json_payload.chords),
                "pluck": len(json_payload.pluck),
                "midi": len(json_payload.midi),
            },
        }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare GuitarBot trajectories generated from a Python pluck list and a JSON arrangement, "
            "with pluck-payload fidelity and slide continuity checks."
        )
    )
    parser.add_argument("--python-file", required=True, help="Path to Python song file containing pluck list variable")
    parser.add_argument("--python-var", default="pluck_message", help="Variable name in python file (default: pluck_message)")
    parser.add_argument("--json-file", required=True, help="Path to arrangement JSON file")
    parser.add_argument("--output", help="Optional output report path (.json)")
    parser.add_argument("--verbose-parser", action="store_true", help="Print parser debug output while running analyses")
    return parser


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()

    python_payload = load_python_payload(args.python_file, variable_name=args.python_var)
    json_payload = load_json_payload(args.json_file)

    report = TrajectoryHarness(quiet_parser_output=not args.verbose_parser).run(
        python_payload=python_payload,
        json_payload=json_payload,
    )

    print(json.dumps(report, indent=2))
    if args.output:
        out_path = Path(args.output)
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Wrote trajectory harness report: {out_path}")


if __name__ == "__main__":
    main()
