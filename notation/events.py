"""Events document: UI JSON → chord/pluck rows for the planner."""

from __future__ import annotations

import copy
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CONFIG = _REPO_ROOT / "configs" / "default.yaml"
_PLUCK_DEFAULTS = {"speed": 5, "slide": 0}


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load configs/default.yaml (pluck defaults). Falls back to built-ins."""
    config_path = Path(path) if path is not None else _DEFAULT_CONFIG
    defaults = {"pluck": dict(_PLUCK_DEFAULTS)}
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
    return defaults


def _seconds_per_beat(bpm: float, time_signature: str) -> float:
    denom = int(str(time_signature).split("/", 1)[1])
    return (60.0 / float(bpm)) * (4.0 / float(denom))


def _beats_per_measure(time_signature: str) -> int:
    return int(str(time_signature).split("/", 1)[0])


def beat_label_to_seconds(
    beat_label: str,
    *,
    bpm: float,
    time_signature: str,
    subdivisions_per_beat: int = 4,
) -> float:
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


@dataclass
class ChordEvent:
    chord: str
    timestamp: float

    def to_row(self) -> list[Any]:
        return [self.chord, self.timestamp]

    def to_dict(self) -> dict[str, Any]:
        return {"chord": self.chord, "timestamp": self.timestamp}


@dataclass
class PluckEvent:
    note: int
    duration: float
    speed: float
    slide: int
    timestamp: float
    string_index: int | None = None

    def to_row(self) -> list[Any]:
        if self.string_index is None:
            return [self.note, self.duration, self.speed, self.slide, self.timestamp]
        return [
            self.note,
            self.duration,
            self.speed,
            self.slide,
            self.string_index,
            self.timestamp,
        ]

    def to_dict(self) -> dict[str, Any]:
        data = {
            "note": self.note,
            "duration_s": self.duration,
            "speed": self.speed,
            "slide": self.slide,
            "timestamp": self.timestamp,
        }
        if self.string_index is not None:
            data["string_index"] = self.string_index
        return data


@dataclass
class SongMeta:
    key: str
    time_signature: str
    bpm: float
    tempo_curve: list[tuple[float, float]] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "key": self.key,
            "time_signature": self.time_signature,
            "bpm": self.bpm,
        }
        if self.tempo_curve is not None:
            payload["tempo_curve"] = [
                {"time": t, "bpm": b} for t, b in self.tempo_curve
            ]
        return payload


@dataclass
class SongArrangement:
    name: str
    meta: SongMeta
    chords: list[ChordEvent]
    plucks: list[PluckEvent]

    @classmethod # CONVERSION FROM UI JSON to events list
    def from_dict(cls, data: dict[str, Any], config: dict[str, Any] | None = None) -> "SongArrangement":
        song = data["song"]
        meta_raw = song["meta"]
        bpm = float(meta_raw["bpm"])
        time_signature = str(meta_raw["time_signature"])
        meta = SongMeta(
            key=str(meta_raw.get("key", "")),
            time_signature=time_signature,
            bpm=bpm,
            tempo_curve=_parse_tempo_curve(meta_raw.get("tempo_curve")),
        )
        pluck_defaults = (config if config is not None else load_config()).get(
            "pluck", _PLUCK_DEFAULTS
        )

        chords: list[ChordEvent] = []
        plucks: list[PluckEvent] = []
        for track in song.get("tracks") or []:
            track_type = track.get("type")
            if track_type == "midi":
                continue
            for raw in track.get("events") or []:
                t = _event_time(raw, bpm, time_signature)
                if track_type == "chord":
                    chords.append(ChordEvent(chord=str(raw["chord"]), timestamp=t))
                elif track_type == "pluck":
                    plucks.append(
                        PluckEvent(
                            note=int(raw["note"]),
                            duration=_pluck_duration_s(raw, bpm, time_signature),
                            speed=float(raw.get("speed", pluck_defaults.get("speed", 5))),
                            slide=int(raw.get("slide", pluck_defaults.get("slide", 0))),
                            timestamp=t,
                            string_index=(
                                int(raw["string_index"])
                                if raw.get("string_index") is not None
                                else None
                            ),
                        )
                    )

        chords.sort(key=lambda e: e.timestamp)
        plucks.sort(key=lambda e: e.timestamp)
        return cls(name=str(song.get("name", "")), meta=meta, chords=chords, plucks=plucks)

    @classmethod
    def from_json_str(cls, text: str, config: dict[str, Any] | None = None) -> "SongArrangement":
        return cls.from_dict(json.loads(text), config=config)

    @classmethod
    def from_json_file(cls, path: str | Path, config: dict[str, Any] | None = None) -> "SongArrangement":
        return cls.from_json_str(Path(path).read_text(encoding="utf-8"), config=config)

    @classmethod
    def from_json_path(cls, path: str | Path, config: dict[str, Any] | None = None) -> "SongArrangement":
        return cls.from_json_file(path, config=config)

    def to_dict(self) -> dict[str, Any]:
        tracks: list[dict[str, Any]] = []
        if self.chords:
            tracks.append(
                {
                    "name": "chords",
                    "type": "chord",
                    "events": [e.to_dict() for e in self.chords],
                }
            )
        if self.plucks:
            tracks.append(
                {
                    "name": "pluck",
                    "type": "pluck",
                    "events": [e.to_dict() for e in self.plucks],
                }
            )
        return {
            "song": {
                "name": self.name,
                "meta": self.meta.to_dict(),
                "tracks": tracks,
            }
        }

    def event_rows(
        self,
        *,
        apply_meta_tempo_curve: bool = True,
    ) -> dict[str, list[list[Any]]]:
        chords = self.chords
        plucks = self.plucks
        if apply_meta_tempo_curve and self.meta.tempo_curve:
            points = self.meta.tempo_curve
            base = self.meta.bpm

            def warp_chord(e: ChordEvent) -> ChordEvent:
                return ChordEvent(chord=e.chord, timestamp=_warp_time(e.timestamp, points, base))

            def warp_pluck(e: PluckEvent) -> PluckEvent:
                start = _warp_time(e.timestamp, points, base)
                end = _warp_time(e.timestamp + e.duration, points, base)
                return PluckEvent(
                    note=e.note,
                    duration=max(0.0, end - start),
                    speed=e.speed,
                    slide=e.slide,
                    timestamp=start,
                    string_index=e.string_index,
                )

            chords = [warp_chord(e) for e in chords]
            plucks = [warp_pluck(e) for e in plucks]

        return {
            "chords": [e.to_row() for e in chords],
            "pluck": [e.to_row() for e in plucks],
        }

    def to_planner_rows(
        self,
        *,
        apply_meta_tempo_curve: bool = True,
    ) -> tuple[list[list[Any]], list[list[Any]]]:
        rows = self.event_rows(apply_meta_tempo_curve=apply_meta_tempo_curve)
        chords = list(rows["chords"])
        pluck = list(rows["pluck"])
        if not pluck:
            raise ValueError("arrangement has no pluck events")
        if not chords:
            last_end = 0.0
            for row in pluck:
                last_end = max(last_end, float(row[-1]) + max(0.0, float(row[1])))
            chords = [["On", last_end + 1.0]]
        return chords, pluck


# Alias used by the play path.
EventDocument = SongArrangement
