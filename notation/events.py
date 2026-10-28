"""Events document: UI JSON → pluck rows for the planner."""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from notation.chords import plan_parts

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CONFIG = _REPO_ROOT / "configs" / "default.yaml"
_PLUCK_DEFAULTS = {"speed": 5, "slide": 0}


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load configs/default.yaml (pluck defaults). Falls back to built-ins."""
    config_path = Path(path) if path is not None else _DEFAULT_CONFIG
    defaults = {"pluck": dict(_PLUCK_DEFAULTS), "planner": "astar"}
    if not config_path.is_file():
        return copy.deepcopy(defaults)
    text = config_path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text)
    except Exception:
        data = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, _, value = line.partition(":")
            key, value = key.strip(), value.strip()
            if value == "":
                continue
            if key == "planner":
                defaults["planner"] = value
                continue
            try:
                defaults.setdefault("pluck", {})[key] = (
                    int(value) if "." not in value else float(value)
                )
            except ValueError:
                pass
        return defaults
    if isinstance(data, dict):
        pluck = data.get("pluck")
        if isinstance(pluck, dict):
            defaults["pluck"].update(pluck)
        planner = data.get("planner")
        if isinstance(planner, str) and planner:
            defaults["planner"] = planner
    return defaults


def _seconds_per_beat(bpm: float, time_signature: str) -> float:
    denom = int(str(time_signature).split("/", 1)[1])
    return (60.0 / float(bpm)) * (4.0 / float(denom))


def _beats_per_measure(time_signature: str) -> int:
    return int(str(time_signature).split("/", 1)[0])


def beat_label_to_seconds(beat_label: str, *, bpm: float, time_signature: str, subdivisions_per_beat: int = 4) -> float:
    """Ableton-style ``bar.beat[.sub]`` or ``~raw_beats`` → seconds."""
    stripped = beat_label.strip()
    spb = _seconds_per_beat(bpm, time_signature)
    if stripped.startswith("~"):
        return float(stripped[1:]) * spb
    parts = [p.strip() for p in stripped.split(".")]
    bar = int(parts[0])
    beat = int(parts[1])
    sub = int(parts[2]) if len(parts) == 3 else 1
    offset = (
        (bar - 1) * _beats_per_measure(time_signature)
        + (beat - 1)
        + (sub - 1) / float(subdivisions_per_beat)
    )
    return offset * spb


def _event_time(raw: dict[str, Any], bpm: float, time_signature: str) -> float:
    if "timestamp" in raw:
        return float(raw["timestamp"])
    return beat_label_to_seconds(str(raw["beat"]), bpm=bpm, time_signature=time_signature)


def _pluck_duration_s(raw: dict[str, Any], bpm: float, time_signature: str) -> float:
    if "duration_s" in raw:
        return float(raw["duration_s"])
    if "duration_b" in raw:
        return float(raw["duration_b"]) * _seconds_per_beat(bpm, time_signature)
    # Legacy ``duration`` is beats.
    return float(raw["duration"]) * _seconds_per_beat(bpm, time_signature)


def _parse_tempo_curve(raw: Any) -> list[tuple[float, float]] | None:
    if not raw:
        return None
    points = []
    for point in raw:
        if isinstance(point, dict):
            points.append((float(point["time"]), float(point["bpm"])))
        else:
            points.append((float(point[0]), float(point[1])))
    points.sort(key=lambda p: p[0])
    return points


def _warp_time(t: float, points: list[tuple[float, float]], base_bpm: float) -> float:
    """Integrate tempo curve: map original-timeline ``t`` to warped seconds."""
    if t <= 0 or not points:
        return max(0.0, t)
    pts = list(points)
    if pts[0][0] > 0.0:
        pts.insert(0, (0.0, base_bpm))
    acc = 0.0
    for i, (t0, bpm0) in enumerate(pts):
        t1, bpm1 = pts[i + 1] if i + 1 < len(pts) else (t, bpm0)
        if t <= t0:
            break
        seg_end = min(t, t1)
        dt = seg_end - t0
        if dt <= 0:
            continue
        if t1 == t0 or abs(bpm1 - bpm0) < 1e-12:
            acc += base_bpm * dt / bpm0
        else:
            slope = (bpm1 - bpm0) / (t1 - t0)
            b1 = bpm0 + slope * dt
            acc += base_bpm / slope * math.log(b1 / bpm0)
        if seg_end >= t:
            break
    return acc


def _pluck_row(note, duration, speed, slide, timestamp, string_index) -> list[Any]:
    """``[note, duration_s, speed, slide, timestamp]``, with ``string_index`` inserted when pinned."""
    if string_index is None:
        return [note, duration, speed, slide, timestamp]
    return [note, duration, speed, slide, string_index, timestamp]


def _warp_pluck_row(row: list[Any], points: list[tuple[float, float]], base_bpm: float) -> list[Any]:
    start = _warp_time(float(row[-1]), points, base_bpm)
    end = _warp_time(float(row[-1]) + float(row[1]), points, base_bpm)
    string_index = row[4] if len(row) == 6 else None
    return _pluck_row(row[0], max(0.0, end - start), row[2], row[3], start, string_index)


def _pluck_to_dict(row: list[Any]) -> dict[str, Any]:
    data = {
        "note": row[0],
        "duration_s": row[1],
        "speed": row[2],
        "slide": row[3],
        "timestamp": row[-1],
    }
    if len(row) == 6:
        data["string_index"] = row[4]
    return data


@dataclass
class SongArrangement:
    """UI song JSON, normalized to chord rows and pluck rows."""

    name: str
    key: str
    time_signature: str
    bpm: float
    chords: list[list[Any]]
    plucks: list[list[Any]]
    tempo_curve: list[tuple[float, float]] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], config: dict[str, Any] | None = None) -> "SongArrangement":
        song = data["song"]
        meta_raw = song["meta"]
        bpm = float(meta_raw["bpm"])
        time_signature = str(meta_raw["time_signature"])
        pluck_defaults = (config if config is not None else load_config()).get(
            "pluck", _PLUCK_DEFAULTS
        )

        chords: list[list[Any]] = []
        plucks: list[list[Any]] = []
        for track in song.get("tracks") or []:
            track_type = track.get("type")
            if track_type == "midi":
                continue
            for raw in track.get("events") or []:
                t = _event_time(raw, bpm, time_signature)
                if track_type == "chord":
                    chords.append([str(raw["chord"]), t])
                elif track_type == "pluck":
                    string_index = (
                        int(raw["string_index"]) if raw.get("string_index") is not None else None
                    )
                    plucks.append(
                        _pluck_row(
                            int(raw["note"]),
                            _pluck_duration_s(raw, bpm, time_signature),
                            float(raw.get("speed", pluck_defaults.get("speed", 5))),
                            int(raw.get("slide", pluck_defaults.get("slide", 0))),
                            t,
                            string_index,
                        )
                    )

        chords.sort(key=lambda row: row[1])
        plucks.sort(key=lambda row: row[-1])
        return cls(
            name=str(song.get("name", "")),
            key=str(meta_raw.get("key", "")),
            time_signature=time_signature,
            bpm=bpm,
            chords=chords,
            plucks=plucks,
            tempo_curve=_parse_tempo_curve(meta_raw.get("tempo_curve")),
        )

    def to_dict(self) -> dict[str, Any]:
        tracks: list[dict[str, Any]] = []
        if self.chords:
            tracks.append(
                {
                    "name": "chords",
                    "type": "chord",
                    "events": [{"chord": row[0], "timestamp": row[1]} for row in self.chords],
                }
            )
        if self.plucks:
            tracks.append(
                {
                    "name": "pluck",
                    "type": "pluck",
                    "events": [_pluck_to_dict(row) for row in self.plucks],
                }
            )
        meta: dict[str, Any] = {
            "key": self.key,
            "time_signature": self.time_signature,
            "bpm": self.bpm,
        }
        if self.tempo_curve is not None:
            meta["tempo_curve"] = [{"time": t, "bpm": b} for t, b in self.tempo_curve]
        return {"song": {"name": self.name, "meta": meta, "tracks": tracks}}

    def to_plan(self):
        """Pluck rows and mute actions for ``GuitarBotParser``.

        Applies ``tempo_curve`` when present, then resolves chord-string plucks
        to pinned pitches and emits a mute for each string a chord damps.
        """
        if not self.plucks:
            raise ValueError("arrangement has no pluck events")
        chords = [list(row) for row in self.chords]
        plucks = [list(row) for row in self.plucks]
        if self.tempo_curve:
            points = self.tempo_curve
            base = self.bpm
            chords = [[row[0], _warp_time(float(row[1]), points, base)] for row in chords]
            plucks = [_warp_pluck_row(row, points, base) for row in plucks]
        return plan_parts(chords, plucks)
