from __future__ import annotations

import argparse
import json
from pathlib import Path

from trajectory_harness import OscPayload, TrajectoryHarness


def _build_pluck_rows(
    note_a: int,
    note_b: int,
    interval_s: float,
    middle_duration_s: float,
    slide_on_middle: int,
) -> list[list[float | int]]:
    start = 4.0
    second = start + float(interval_s)
    third = second + 1.0
    return [
        [int(note_a), 0.25, 6, 0, round(start, 3)],
        [int(note_b), float(middle_duration_s), 6, int(slide_on_middle), round(second, 3)],
        [int(note_a), 0.25, 6, 0, round(third, 3)],
    ]


def _run_case(rows: list[list[float | int]]) -> dict:
    payload = OscPayload(chords=[], pluck=rows, midi=[])
    report = TrajectoryHarness(quiet_parser_output=True).run(python_payload=payload, json_payload=payload)
    readiness = report["analyses"].get("tremolo_readiness", {})
    return {
        "pass": bool(readiness.get("pass", False)),
        "checked": int(readiness.get("python", {}).get("checked_tremolo_events", 0)),
        "python_violations": int(readiness.get("python", {}).get("violation_count", 0)),
        "json_violations": int(readiness.get("json", {}).get("violation_count", 0)),
        "python_examples": readiness.get("python", {}).get("violations", [])[:3],
        "json_examples": readiness.get("json", {}).get("violations", [])[:3],
    }


def run_sweep() -> dict:
    note_pairs = [
        (43, 45),
        (45, 43),
        (43, 47),
        (47, 43),
    ]
    intervals = [0.5, 1.0, 1.5]
    middle_durations = [0.6, 1.0, 2.0]
    slide_options = [0, 1]

    cases = []
    for note_a, note_b in note_pairs:
        for interval_s in intervals:
            for middle_duration_s in middle_durations:
                for slide_on_middle in slide_options:
                    rows = _build_pluck_rows(note_a, note_b, interval_s, middle_duration_s, slide_on_middle)
                    case_result = _run_case(rows)
                    cases.append(
                        {
                            "note_a": note_a,
                            "note_b": note_b,
                            "interval_s": interval_s,
                            "middle_duration_s": middle_duration_s,
                            "slide_on_middle": slide_on_middle,
                            "rows": rows,
                            "result": case_result,
                        }
                    )

    failed = [case for case in cases if not case["result"]["pass"]]
    return {
        "total_cases": len(cases),
        "failed_cases": len(failed),
        "pass_rate": round((len(cases) - len(failed)) / max(1, len(cases)), 4),
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run tremolo/slide readiness sweep over multiple note combinations")
    parser.add_argument(
        "--output",
        default="Songs/trajectory_tremolo_sweep_report.json",
        help="Path to write the sweep report JSON",
    )
    args = parser.parse_args()

    report = run_sweep()
    output_path = Path(args.output)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "total_cases": report["total_cases"],
        "failed_cases": report["failed_cases"],
        "pass_rate": report["pass_rate"],
        "output": str(output_path),
    }, indent=2))


if __name__ == "__main__":
    main()
