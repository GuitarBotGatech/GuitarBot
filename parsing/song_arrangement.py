from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
from pathlib import Path
from typing import Any


TrackType = str
EventType = "ChordEvent | PluckEvent | MidiEvent"


@dataclass
class SongMeta:
    key: str
    time_signature: str
    bpm: float
    tempo_curve: list[tuple[float, float]] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SongMeta":
        tempo_curve = cls._parse_tempo_curve(data.get("tempo_curve"))
        meta = cls(
            key=str(data["key"]),
            time_signature=str(data["time_signature"]),
            bpm=float(data["bpm"]),
            tempo_curve=tempo_curve,
        )
        meta.validate()
        return meta

    @staticmethod
    def _parse_tempo_curve(raw_curve: Any) -> list[tuple[float, float]] | None:
        if raw_curve is None:
            return None
        if not isinstance(raw_curve, list):
            raise ValueError("song.meta.tempo_curve must be a list")

        points: list[tuple[float, float]] = []
        for index, point in enumerate(raw_curve):
            if isinstance(point, dict):
                if "time" not in point or "bpm" not in point:
                    raise ValueError(
                        f"song.meta.tempo_curve[{index}] dict must contain 'time' and 'bpm'"
                    )
                t_val = point["time"]
                bpm_val = point["bpm"]
            elif isinstance(point, (list, tuple)) and len(point) == 2:
                t_val, bpm_val = point
            else:
                raise ValueError(
                    f"song.meta.tempo_curve[{index}] must be {{'time': ..., 'bpm': ...}} or [time, bpm]"
                )
            points.append((float(t_val), float(bpm_val)))

        points.sort(key=lambda value: value[0])
        return points

    def validate(self) -> None:
        if self.bpm <= 0:
            raise ValueError("song.meta.bpm must be > 0")
        if not self.key:
            raise ValueError("song.meta.key must be non-empty")
        if not self.time_signature:
            raise ValueError("song.meta.time_signature must be non-empty")
        self.beats_per_measure()
        if self.tempo_curve is not None:
            for index, (time_s, bpm) in enumerate(self.tempo_curve):
                if time_s < 0:
                    raise ValueError(f"song.meta.tempo_curve[{index}].time must be >= 0")
                if bpm <= 0:
                    raise ValueError(f"song.meta.tempo_curve[{index}].bpm must be > 0")
                if index > 0 and time_s < self.tempo_curve[index - 1][0]:
                    raise ValueError("song.meta.tempo_curve times must be non-decreasing")

    def beats_per_measure(self) -> int:
        try:
            numerator_text, _denominator_text = self.time_signature.split("/", 1)
            numerator = int(numerator_text)
        except Exception as exc:
            raise ValueError(
                f"song.meta.time_signature must be in 'N/D' format; got {self.time_signature!r}"
            ) from exc
        if numerator <= 0:
            raise ValueError("song.meta.time_signature numerator must be > 0")
        return numerator

    def beat_unit_denominator(self) -> int:
        try:
            _numerator_text, denominator_text = self.time_signature.split("/", 1)
            denominator = int(denominator_text)
        except Exception as exc:
            raise ValueError(
                f"song.meta.time_signature must be in 'N/D' format; got {self.time_signature!r}"
            ) from exc
        if denominator <= 0:
            raise ValueError("song.meta.time_signature denominator must be > 0")
        return denominator

    def seconds_per_beat(self) -> float:
        denominator = self.beat_unit_denominator()
        beat_note_factor = 4.0 / float(denominator)
        return (60.0 / self.bpm) * beat_note_factor

    def beat_label_to_seconds(self, beat_label: str, subdivisions_per_beat: int = 4) -> float:
        """
        Convert an Ableton-style beat label to seconds.

        Supported forms (1-indexed components):
        - "bar.beat"         (e.g. "2.1")
        - "bar.beat.sub"     (e.g. "3.2.2")
        - "~raw_beats"       (e.g. "~9.3333", where 0.0 == "1.1")

        Notes
        -----
        - "bar.beat" is equivalent to "bar.beat.1".
        - With the default subdivisions_per_beat=4, the third component
          represents sixteenth-note slots for 4/x meters.
        """
        if subdivisions_per_beat <= 0:
            raise ValueError("subdivisions_per_beat must be > 0")

        stripped = beat_label.strip()
        if stripped.startswith("~"):
            try:
                raw_beats = float(stripped[1:])
            except ValueError as exc:
                raise ValueError(f"raw beat label must be a float after '~'; got {beat_label!r}") from exc
            if raw_beats < 0:
                raise ValueError("raw beat label must be >= 0")
            return raw_beats * self.seconds_per_beat()

        parts = [part.strip() for part in stripped.split(".")]
        if len(parts) not in (2, 3):
            raise ValueError(
                f"beat label must be 'bar.beat' or 'bar.beat.sub'; got {beat_label!r}"
            )

        try:
            bar = int(parts[0])
            beat = int(parts[1])
            subdivision = int(parts[2]) if len(parts) == 3 else 1
        except ValueError as exc:
            raise ValueError(f"beat label must contain integers; got {beat_label!r}") from exc

        if bar <= 0:
            raise ValueError("beat label bar index must be >= 1")
        if beat <= 0:
            raise ValueError("beat label beat index must be >= 1")
        if subdivision <= 0:
            raise ValueError("beat label subdivision index must be >= 1")

        beats_per_measure = self.beats_per_measure()
        if beat > beats_per_measure:
            raise ValueError(
                f"beat label beat index {beat} exceeds beats per measure {beats_per_measure}"
            )

        beat_offset = (
            (bar - 1) * beats_per_measure
            + (beat - 1)
            + (subdivision - 1) / float(subdivisions_per_beat)
        )
        return beat_offset * self.seconds_per_beat()

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "key": self.key,
            "time_signature": self.time_signature,
            "bpm": self.bpm,
        }
        if self.tempo_curve is not None:
            payload["tempo_curve"] = [
                {"time": time_s, "bpm": bpm}
                for time_s, bpm in self.tempo_curve
            ]
        return payload


@dataclass
class ChordEvent:
    chord: str
    timestamp: float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChordEvent":
        event = cls(chord=str(data["chord"]), timestamp=float(data["timestamp"]))
        event.validate()
        return event

    def validate(self) -> None:
        if not self.chord:
            raise ValueError("ChordEvent.chord must be non-empty")
        if self.timestamp < 0:
            raise ValueError("ChordEvent.timestamp must be >= 0")

    def to_dict(self) -> dict[str, Any]:
        return {"chord": self.chord, "timestamp": self.timestamp}

    def to_osc_row(self) -> list[Any]:
        return [self.chord, self.timestamp]

    def shifted(self, seconds: float) -> "ChordEvent":
        shifted_event = ChordEvent(chord=self.chord, timestamp=self.timestamp + seconds)
        shifted_event.validate()
        return shifted_event


@dataclass
class PluckEvent:
    note: int
    duration: float
    speed: float
    slide: int
    timestamp: float
    string_index: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PluckEvent":
        if "duration" not in data:
            raise ValueError("PluckEvent requires 'duration' in seconds after normalization")
        event = cls(
            note=int(data["note"]),
            duration=float(data["duration"]),
            speed=float(data["speed"]),
            slide=int(data["slide"]),
            timestamp=float(data["timestamp"]),
            string_index=(int(data["string_index"]) if "string_index" in data and data["string_index"] is not None else None),
        )
        event.validate()
        return event

    def validate(self) -> None:
        if self.duration <= 0:
            raise ValueError("PluckEvent.duration must be > 0")
        if self.timestamp < 0:
            raise ValueError("PluckEvent.timestamp must be >= 0")
        if self.slide not in (0, 1):
            raise ValueError("PluckEvent.slide must be 0 or 1")
        if self.string_index is not None and self.string_index < 0:
            raise ValueError("PluckEvent.string_index must be >= 0 when provided")

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

    def to_osc_row(self) -> list[Any]:
        if self.string_index is None:
            return [self.note, self.duration, self.speed, self.slide, self.timestamp]
        return [self.note, self.duration, self.speed, self.slide, self.string_index, self.timestamp]

    def shifted(self, seconds: float) -> "PluckEvent":
        shifted_event = PluckEvent(
            note=self.note,
            duration=self.duration,
            speed=self.speed,
            slide=self.slide,
            timestamp=self.timestamp + seconds,
            string_index=self.string_index,
        )
        shifted_event.validate()
        return shifted_event


@dataclass
class MidiEvent:
    address: str
    args: list[Any]
    timestamp: float
    interp: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MidiEvent":
        event = cls(
            address=str(data["address"]),
            args=list(data.get("args", [])),
            timestamp=float(data["timestamp"]),
            interp=(int(data["interp"]) if "interp" in data and data["interp"] is not None else None),
        )
        event.validate()
        return event

    def validate(self) -> None:
        if not self.address.startswith("/"):
            raise ValueError("MidiEvent.address must start with '/'")
        if self.timestamp < 0:
            raise ValueError("MidiEvent.timestamp must be >= 0")
        if self.interp is not None and self.interp not in (0, 1):
            raise ValueError("MidiEvent.interp must be 0 or 1 when provided")

    def to_dict(self) -> dict[str, Any]:
        data = {
            "address": self.address,
            "args": self.args,
            "timestamp": self.timestamp,
        }
        if self.interp is not None:
            data["interp"] = self.interp
        return data

    def to_osc_row(self) -> list[Any]:
        row = [self.address, *self.args]
        if self.interp is not None:
            row.append(self.interp)
        row.append(self.timestamp)
        return row

    def shifted(self, seconds: float) -> "MidiEvent":
        shifted_event = MidiEvent(
            address=self.address,
            args=list(self.args),
            timestamp=self.timestamp + seconds,
            interp=self.interp,
        )
        shifted_event.validate()
        return shifted_event


@dataclass
class Track:
    name: str
    type: TrackType
    events: list[ChordEvent | PluckEvent | MidiEvent] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any], meta: SongMeta) -> "Track":
        track_type = str(data["type"])
        track_name = str(data["name"])
        raw_events = data.get("events", [])

        events: list[ChordEvent | PluckEvent | MidiEvent] = []
        if track_type not in ("chord", "pluck", "midi"):
            raise ValueError(f"Unsupported track type: {track_type}")

        for event_index, raw_event in enumerate(raw_events):
            try:
                event_with_time = cls._resolve_event_time(raw_event, meta)
                if track_type == "chord":
                    events.append(ChordEvent.from_dict(event_with_time))
                elif track_type == "pluck":
                    event_with_time = cls._resolve_pluck_duration(event_with_time, meta)
                    events.append(PluckEvent.from_dict(event_with_time))
                else:
                    events.append(MidiEvent.from_dict(event_with_time))
            except Exception as exc:
                raise ValueError(
                    f"Invalid event in track '{track_name}' (type={track_type}) at index {event_index}: {exc}"
                ) from exc

        track = cls(name=track_name, type=track_type, events=events)
        track.validate()
        return track

    def validate(self) -> None:
        if self.type not in ("chord", "pluck", "midi"):
            raise ValueError(f"Unsupported track type: {self.type}")
        if not self.name:
            raise ValueError("Track.name must be non-empty")

        timestamps = [event.timestamp for event in self.events]
        for index, (previous, current) in enumerate(zip(timestamps, timestamps[1:]), start=1):
            if current < previous:
                raise ValueError(
                    f"Track '{self.name}' has non-monotonic timestamps between event {index - 1} ({previous}) and event {index} ({current})"
                )

    @staticmethod
    def _resolve_event_time(raw_event: dict[str, Any], meta: SongMeta) -> dict[str, Any]:
        if "timestamp" in raw_event:
            resolved = dict(raw_event)
            resolved["timestamp"] = float(raw_event["timestamp"])
            return resolved

        if "beat" in raw_event:
            resolved = dict(raw_event)
            beat_label = str(raw_event["beat"])
            resolved["timestamp"] = meta.beat_label_to_seconds(beat_label)
            return resolved

        raise ValueError("event requires either 'timestamp' (seconds) or 'beat' (bar.beat[.sub])")

    @staticmethod
    def _resolve_pluck_duration(raw_event: dict[str, Any], meta: SongMeta) -> dict[str, Any]:
        has_s = "duration_s" in raw_event
        has_b = "duration_b" in raw_event
        has_legacy = "duration" in raw_event

        provided = int(has_s) + int(has_b) + int(has_legacy)
        if provided == 0:
            raise ValueError("pluck event requires one of: duration_s, duration_b, or legacy duration")
        if provided > 1:
            raise ValueError("pluck event must provide only one duration field: duration_s, duration_b, or legacy duration")

        normalized = dict(raw_event)
        if has_s:
            duration_seconds = float(raw_event["duration_s"])
        elif has_b:
            duration_seconds = float(raw_event["duration_b"]) * meta.seconds_per_beat()
        else:
            duration_seconds = float(raw_event["duration"]) * meta.seconds_per_beat()

        normalized["duration"] = duration_seconds
        return normalized

    def sorted_events(self) -> list[ChordEvent | PluckEvent | MidiEvent]:
        return sorted(self.events, key=lambda event: float(event.timestamp))

    @staticmethod
    def _event_with_timestamp(event: ChordEvent | PluckEvent | MidiEvent, timestamp: float) -> ChordEvent | PluckEvent | MidiEvent:
        if isinstance(event, ChordEvent):
            updated = ChordEvent(chord=event.chord, timestamp=timestamp)
        elif isinstance(event, PluckEvent):
            updated = PluckEvent(
                note=event.note,
                duration=event.duration,
                speed=event.speed,
                slide=event.slide,
                timestamp=timestamp,
                string_index=event.string_index,
            )
        else:
            updated = MidiEvent(
                address=event.address,
                args=list(event.args),
                timestamp=timestamp,
                interp=event.interp,
            )
        updated.validate()
        return updated

    @staticmethod
    def _event_scaled(event: ChordEvent | PluckEvent | MidiEvent, factor: float) -> ChordEvent | PluckEvent | MidiEvent:
        if isinstance(event, PluckEvent):
            updated = PluckEvent(
                note=event.note,
                duration=event.duration * factor,
                speed=event.speed,
                slide=event.slide,
                timestamp=event.timestamp * factor,
                string_index=event.string_index,
            )
            updated.validate()
            return updated
        return Track._event_with_timestamp(event, event.timestamp * factor)

    def shift_time(self, seconds: float) -> "Track":
        shifted_events = [event.shifted(seconds) for event in self.events]
        shifted_track = Track(name=self.name, type=self.type, events=shifted_events)
        shifted_track.validate()
        return shifted_track

    def copy_range(self, start_s: float, end_s: float) -> "Track":
        if end_s < start_s:
            raise ValueError("copy_range requires end_s >= start_s")
        clip_events: list[ChordEvent | PluckEvent | MidiEvent] = []
        for event in self.events:
            if start_s <= event.timestamp <= end_s:
                clip_events.append(event.shifted(-start_s))
        clip_track = Track(name=self.name, type=self.type, events=clip_events)
        clip_track.validate()
        return clip_track

    def reverse_range(self, start_s: float, end_s: float, duration_policy: str = "preserve") -> "Track":
        if end_s < start_s:
            raise ValueError("reverse_range requires end_s >= start_s")
        if duration_policy not in ("preserve", "mirror_end"):
            raise ValueError("reverse_range duration_policy must be 'preserve' or 'mirror_end'")

        reversed_events: list[ChordEvent | PluckEvent | MidiEvent] = []
        for event in self.events:
            if start_s <= event.timestamp <= end_s:
                mirrored_time = start_s + end_s - event.timestamp
                if duration_policy == "mirror_end" and isinstance(event, PluckEvent):
                    mirrored_time = start_s + end_s - (event.timestamp + event.duration)
                reversed_events.append(self._event_with_timestamp(event, mirrored_time))
            else:
                reversed_events.append(event)

        reversed_track = Track(name=self.name, type=self.type, events=sorted(reversed_events, key=lambda event: event.timestamp))
        reversed_track.validate()
        return reversed_track

    def quantize(
        self,
        grid_seconds: float,
        start_s: float | None = None,
        end_s: float | None = None,
        strength: float = 1.0,
        swing: float = 0.0,
        subdivisions_per_beat: int | None = None,
    ) -> "Track":
        if grid_seconds <= 0:
            raise ValueError("quantize grid_seconds must be > 0")
        if not (0.0 <= strength <= 1.0):
            raise ValueError("quantize strength must be between 0.0 and 1.0")
        if not (-1.0 <= swing <= 1.0):
            raise ValueError("quantize swing must be between -1.0 and 1.0")

        quantized_events: list[ChordEvent | PluckEvent | MidiEvent] = []
        for event in self.events:
            should_quantize = True
            if start_s is not None and event.timestamp < start_s:
                should_quantize = False
            if end_s is not None and event.timestamp > end_s:
                should_quantize = False

            if should_quantize:
                q_time = round(event.timestamp / grid_seconds) * grid_seconds
                if swing != 0.0 and subdivisions_per_beat and subdivisions_per_beat > 1:
                    grid_index = int(round(q_time / grid_seconds))
                    beat_sub_index = grid_index % subdivisions_per_beat
                    if beat_sub_index % 2 == 1:
                        q_time += swing * (grid_seconds * 0.5)
                q_time = event.timestamp + (q_time - event.timestamp) * strength
                q_time = max(0.0, q_time)
                quantized_events.append(self._event_with_timestamp(event, q_time))
            else:
                quantized_events.append(event)

        quantized_track = Track(name=self.name, type=self.type, events=sorted(quantized_events, key=lambda event: event.timestamp))
        quantized_track.validate()
        return quantized_track

    def scale_time(self, factor: float) -> "Track":
        if factor <= 0:
            raise ValueError("scale_time factor must be > 0")
        scaled_events = [self._event_scaled(event, factor) for event in self.events]
        scaled_track = Track(name=self.name, type=self.type, events=scaled_events)
        scaled_track.validate()
        return scaled_track

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "events": [event.to_dict() for event in self.sorted_events()],
        }


@dataclass
class SongArrangement:
    name: str
    meta: SongMeta
    tracks: list[Track]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SongArrangement":
        song_data = data["song"]
        meta = SongMeta.from_dict(song_data["meta"])
        arrangement = cls(
            name=str(song_data["name"]),
            meta=meta,
            tracks=[Track.from_dict(track, meta=meta) for track in song_data.get("tracks", [])],
        )
        arrangement.validate()
        return arrangement

    @classmethod
    def from_json_str(cls, text: str) -> "SongArrangement":
        return cls.from_dict(json.loads(text))

    @classmethod
    def from_json_file(cls, path: str | Path) -> "SongArrangement":
        return cls.from_json_str(Path(path).read_text(encoding="utf-8"))

    @classmethod
    def from_json_path(cls, path: str | Path) -> "SongArrangement":
        return cls.from_json_file(path)

    def validate(self) -> None:
        if not self.name:
            raise ValueError("song.name must be non-empty")
        self.meta.validate()
        for track in self.tracks:
            track.validate()

    def to_dict(self) -> dict[str, Any]:
        return {
            "song": {
                "name": self.name,
                "meta": self.meta.to_dict(),
                "tracks": [track.to_dict() for track in self.tracks],
            }
        }

    def to_json_str(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    def to_json_path(self, path: str | Path, indent: int = 2) -> None:
        Path(path).write_text(self.to_json_str(indent=indent) + "\n", encoding="utf-8")

    def clone(self) -> "SongArrangement":
        return SongArrangement.from_dict(self.to_dict())

    def shift_time(self, seconds: float) -> "SongArrangement":
        shifted_tracks = [track.shift_time(seconds) for track in self.tracks]
        arrangement = SongArrangement(name=self.name, meta=self.meta, tracks=shifted_tracks)
        arrangement.validate()
        return arrangement

    def copy_range(self, start_s: float, end_s: float) -> "SongArrangement":
        if end_s < start_s:
            raise ValueError("copy_range requires end_s >= start_s")
        clip_tracks = [track.copy_range(start_s, end_s) for track in self.tracks]
        arrangement = SongArrangement(
            name=f"{self.name} [clip {start_s:.3f}-{end_s:.3f}]",
            meta=self.meta,
            tracks=clip_tracks,
        )
        arrangement.validate()
        return arrangement

    def paste_at(self, clip: "SongArrangement", start_s: float) -> "SongArrangement":
        if start_s < 0:
            raise ValueError("paste_at start_s must be >= 0")

        base = self.clone()
        track_by_name = {track.name: track for track in base.tracks}

        for clip_track in clip.tracks:
            shifted_track = clip_track.shift_time(start_s)
            if clip_track.name in track_by_name:
                target_track = track_by_name[clip_track.name]
                if target_track.type != clip_track.type:
                    raise ValueError(
                        f"Cannot paste track '{clip_track.name}' with type {clip_track.type} into existing type {target_track.type}"
                    )
                target_track.events.extend(shifted_track.events)
                target_track.events = target_track.sorted_events()
                target_track.validate()
            else:
                base.tracks.append(shifted_track)
                track_by_name[shifted_track.name] = shifted_track

        base.validate()
        return base

    def reverse_range(self, start_s: float, end_s: float, duration_policy: str = "preserve") -> "SongArrangement":
        if end_s < start_s:
            raise ValueError("reverse_range requires end_s >= start_s")
        reversed_tracks = [
            track.reverse_range(start_s, end_s, duration_policy=duration_policy)
            for track in self.tracks
        ]
        arrangement = SongArrangement(name=self.name, meta=self.meta, tracks=reversed_tracks)
        arrangement.validate()
        return arrangement

    def quantize(
        self,
        subdivisions_per_beat: int = 4,
        start_s: float | None = None,
        end_s: float | None = None,
        strength: float = 1.0,
        swing: float = 0.0,
    ) -> "SongArrangement":
        if subdivisions_per_beat <= 0:
            raise ValueError("subdivisions_per_beat must be > 0")
        if start_s is not None and end_s is not None and end_s < start_s:
            raise ValueError("quantize requires end_s >= start_s")

        grid_seconds = self.meta.seconds_per_beat() / float(subdivisions_per_beat)
        quantized_tracks = [
            track.quantize(
                grid_seconds=grid_seconds,
                start_s=start_s,
                end_s=end_s,
                strength=strength,
                swing=swing,
                subdivisions_per_beat=subdivisions_per_beat,
            )
            for track in self.tracks
        ]
        arrangement = SongArrangement(name=self.name, meta=self.meta, tracks=quantized_tracks)
        arrangement.validate()
        return arrangement

    def scale_tempo(self, new_bpm: float) -> "SongArrangement":
        if new_bpm <= 0:
            raise ValueError("scale_tempo new_bpm must be > 0")

        factor = self.meta.bpm / float(new_bpm)
        scaled_tracks = [track.scale_time(factor) for track in self.tracks]
        scaled_meta = SongMeta(
            key=self.meta.key,
            time_signature=self.meta.time_signature,
            bpm=float(new_bpm),
        )
        scaled_meta.validate()

        arrangement = SongArrangement(name=self.name, meta=scaled_meta, tracks=scaled_tracks)
        arrangement.validate()
        return arrangement

    def scale_tempo_curve(
        self,
        control_points: list[tuple[float, float]],
        keep_tempo_curve_in_meta: bool = False,
    ) -> "SongArrangement":
        """
        Apply a dynamic tempo curve (rubato) to the arrangement timeline.

        Parameters
        ----------
        control_points:
            List of (time_s, bpm) points defined on the *current* timeline.
            BPM is linearly interpolated between points. If the first point is
            after t=0, an implicit (0.0, base_bpm) point is inserted.
        """
        if not control_points:
            raise ValueError("scale_tempo_curve requires at least one control point")

        points = sorted((float(t), float(bpm)) for t, bpm in control_points)
        if points[0][0] > 0.0:
            points.insert(0, (0.0, self.meta.bpm))

        for index, (time_s, bpm) in enumerate(points):
            if time_s < 0:
                raise ValueError("scale_tempo_curve control point times must be >= 0")
            if bpm <= 0:
                raise ValueError("scale_tempo_curve bpm values must be > 0")
            if index > 0 and time_s < points[index - 1][0]:
                raise ValueError("scale_tempo_curve control points must be non-decreasing in time")

        def _integral_scale(t_end: float) -> float:
            if t_end <= 0:
                return 0.0

            acc = 0.0
            for idx, (t0, bpm0) in enumerate(points):
                t1, bpm1 = points[idx + 1] if idx + 1 < len(points) else (t_end, bpm0)
                if t_end <= t0:
                    break
                seg_end = min(t_end, t1)
                if seg_end <= t0:
                    continue

                dt = seg_end - t0
                if t1 == t0:
                    bpm_at = bpm0
                    acc += self.meta.bpm * dt / bpm_at
                    continue

                slope = (bpm1 - bpm0) / (t1 - t0)
                if abs(slope) < 1e-12:
                    acc += self.meta.bpm * dt / bpm0
                else:
                    b0 = bpm0
                    b1 = bpm0 + slope * dt
                    if b0 <= 0 or b1 <= 0:
                        raise ValueError("scale_tempo_curve produced non-positive BPM within a segment")
                    acc += self.meta.bpm / slope * math.log(b1 / b0)

                if seg_end >= t_end:
                    break

            return acc

        def _warp_event(event: ChordEvent | PluckEvent | MidiEvent) -> ChordEvent | PluckEvent | MidiEvent:
            warped_start = _integral_scale(event.timestamp)
            if isinstance(event, PluckEvent):
                warped_end = _integral_scale(event.timestamp + event.duration)
                warped_duration = max(0.0, warped_end - warped_start)
                warped = PluckEvent(
                    note=event.note,
                    duration=warped_duration,
                    speed=event.speed,
                    slide=event.slide,
                    timestamp=warped_start,
                    string_index=event.string_index,
                )
                warped.validate()
                return warped
            return Track._event_with_timestamp(event, warped_start)

        warped_tracks: list[Track] = []
        for track in self.tracks:
            warped_events = [_warp_event(event) for event in track.events]
            warped_track = Track(name=track.name, type=track.type, events=warped_events)
            warped_track.validate()
            warped_tracks.append(warped_track)

        warped_meta = SongMeta(
            key=self.meta.key,
            time_signature=self.meta.time_signature,
            bpm=self.meta.bpm,
            tempo_curve=(list(points) if keep_tempo_curve_in_meta else None),
        )
        warped_meta.validate()

        arrangement = SongArrangement(name=self.name, meta=warped_meta, tracks=warped_tracks)
        arrangement.validate()
        return arrangement

    def render_osc_payloads(self, apply_meta_tempo_curve: bool = True) -> dict[str, list[list[Any]]]:
        source = self
        if apply_meta_tempo_curve and self.meta.tempo_curve:
            source = self.scale_tempo_curve(self.meta.tempo_curve, keep_tempo_curve_in_meta=False)

        chord_rows: list[list[Any]] = []
        pluck_rows: list[list[Any]] = []
        midi_rows: list[list[Any]] = []

        for track in source.tracks:
            if track.type == "chord":
                chord_rows.extend(event.to_osc_row() for event in track.events if isinstance(event, ChordEvent))
            elif track.type == "pluck":
                pluck_rows.extend(event.to_osc_row() for event in track.events if isinstance(event, PluckEvent))
            elif track.type == "midi":
                midi_rows.extend(event.to_osc_row() for event in track.events if isinstance(event, MidiEvent))

        chord_rows.sort(key=lambda row: float(row[-1]))
        pluck_rows.sort(key=lambda row: float(row[-1]))
        midi_rows.sort(key=lambda row: float(row[-1]))

        return {
            "/Chords": chord_rows,
            "/Pluck": pluck_rows,
            "/Midi": midi_rows,
        }
