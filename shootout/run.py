"""Run the path-planning shootout."""
from __future__ import annotations
import time
from pathlib import Path
import sys

if __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shootout.corpus import build_corpus
from shootout.model import PlanResult
from shootout.planners import ALL
from shootout.report import markdown_table, write_csv, verdict


def run_one(planner_fn, notes):
    t0 = time.perf_counter()
    assignments = planner_fn(notes)
    dt = (time.perf_counter() - t0) * 1000.0
    res = PlanResult.from_plan(notes, assignments)
    return res, dt


def main():
    here = Path(__file__).resolve().parent
    songs_dir = here.parent / "Songs"
    corpus = build_corpus(songs_dir)
    rows = []
    for song_name, notes in corpus:
        if not notes:
            continue
        for pname, fn in ALL.items():
            try:
                res, dt = run_one(fn, notes)
                rows.append({
                    "planner": pname,
                    "song": song_name,
                    "notes": len(notes),
                    "travel": res.total_travel,
                    "violations": res.violations,
                    "peak_vel": res.peak_velocity,
                    "runtime_ms": dt,
                })
            except Exception as e:
                rows.append({
                    "planner": pname,
                    "song": song_name,
                    "notes": len(notes),
                    "travel": float("nan"),
                    "violations": -1,
                    "peak_vel": float("nan"),
                    "runtime_ms": -1,
                })
                print(f"[error] {pname} on {song_name}: {e}")

    print(markdown_table(rows))
    print(verdict(rows))
    out_csv = here / "results.csv"
    write_csv(rows, out_csv)
    print(f"\nWrote {out_csv}")


if __name__ == "__main__":
    main()
