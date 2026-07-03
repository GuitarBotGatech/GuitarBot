from __future__ import annotations
import csv
from pathlib import Path


def markdown_table(rows: list[dict]) -> str:
    if not rows:
        return "(no results)"
    cols = ["planner", "song", "notes", "travel", "violations", "peak_vel", "runtime_ms"]
    out = ["| " + " | ".join(cols) + " |",
           "|" + "|".join("---" for _ in cols) + "|"]
    for r in rows:
        out.append("| " + " | ".join(_fmt(r.get(c)) for c in cols) + " |")
    return "\n".join(out)


def _fmt(v):
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def write_csv(rows: list[dict], path: Path):
    if not rows:
        return
    cols = list(rows[0].keys())
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def verdict(rows: list[dict]) -> str:
    """Short per-song winner summary + overall averages."""
    by_song: dict[str, list[dict]] = {}
    for r in rows:
        by_song.setdefault(r["song"], []).append(r)
    lines = ["", "## Verdict", ""]
    planner_scores: dict[str, list[float]] = {}
    planner_viols: dict[str, int] = {}
    for song, rs in by_song.items():
        valid = [r for r in rs if r["violations"] >= 0 and r["travel"] == r["travel"]]
        if not valid:
            lines.append(f"- **{song}**: all planners failed"); continue
        win = min(valid, key=lambda r: (r["violations"], r["travel"]))
        lines.append(f"- **{song}** ({rs[0]['notes']} notes): {win['planner']}  "
                     f"(travel={win['travel']:.1f}, viol={win['violations']})")
        for r in valid:
            planner_scores.setdefault(r["planner"], []).append(r["travel"])
            planner_viols[r["planner"]] = planner_viols.get(r["planner"], 0) + r["violations"]
    lines.append("")
    lines.append("### Overall")
    for p, travels in planner_scores.items():
        avg = sum(travels) / len(travels)
        lines.append(f"- {p}: mean travel {avg:.1f}, total violations {planner_viols[p]}")
    return "\n".join(lines)
