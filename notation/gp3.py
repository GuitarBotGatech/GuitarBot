"""Compile a Guitar Pro 3 tab into the song dict ``SongArrangement`` plans.

The decoder is ``pyguitarpro``. This module turns one guitar track into pluck
events: MIDI pitch, duration, time, and the string the robot should use.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tuning import tune as tu

# Guitar Pro timelines are in ticks; a quarter note is 960 ticks.
_QUARTER = 960

# Slides that land on the next note, and slides that arrive at this note.
_SLIDE_TO_NEXT = ("shiftSlideTo", "legatoSlideTo")
_SLIDE_INTO = ("intoFromAbove", "intoFromBelow")


@dataclass
class Gp3Compile:
    """One compiled track and how many tab notes became plucks."""

    song: dict[str, Any]
    track_name: str
    track_index: int
    events: int
    moved: int
    skipped: int


@dataclass
class _Pluck:
    midi: int
    timestamp: float
    duration_s: float
    slide: int
    preferred: int | None
    string_index: int | None = None


def gp3_to_song_dict(path: str | Path, *, track=None) -> dict[str, Any]:
    """``.gp3`` file → the song dict ``SongArrangement.from_dict`` expects."""
    return compile_gp3(path, track=track).song


def compile_gp3(path: str | Path, *, track=None) -> Gp3Compile:
    """Read ``path`` and compile one track into pluck events.

    The tab string is kept when the left hand can reach that fret in time.
    Otherwise the note moves to another string that can sound it. Notes outside
    the robot's range, or too fast for every string, are left out.
    """
    guitarpro = _guitarpro()
    source = Path(path)
    song = guitarpro.parse(str(source))
    chosen, index = _select_track(song, track)
    plucks, moved, skipped = _compile_track(song, chosen)
    if not plucks:
        raise ValueError(f"No playable notes on track {chosen.name!r}")

    title = (song.title or source.stem).strip() or source.stem
    track_name = chosen.name.strip() or f"track {index}"
    name = title if track_name.casefold() in title.casefold() else f"{title} ({track_name})"
    payload = {
        "song": {
            "name": name,
            "meta": {
                "key": _key_name(song.key),
                "time_signature": _time_signature(song),
                "bpm": _song_bpm(song),
            },
            "tracks": [
                {
                    "name": track_name,
                    "type": "pluck",
                    "events": [_event_dict(pluck) for pluck in plucks],
                }
            ],
        }
    }
    return Gp3Compile(
        song=payload,
        track_name=track_name,
        track_index=index,
        events=len(plucks),
        moved=moved,
        skipped=skipped,
    )


def list_tracks(path: str | Path) -> list[dict[str, Any]]:
    """Name, index, and how well each track fits the robot's fretboard."""
    song = _guitarpro().parse(str(path))
    rows = []
    for index, track in enumerate(song.tracks):
        rows.append(
            {
                "index": index,
                "name": track.name.strip(),
                "percussion": bool(track.isPercussionTrack),
                "strings": [int(string.value) for string in track.strings],
                "score": _track_score(track),
            }
        )
    return rows


def playback_measure_indices(headers) -> list[int]:
    """Measure indices in the order they are played, with repeats unfolded.

    ``repeatClose`` is the total number of times that group plays (the count
    written in the tab). Alternate endings use the bitmask Guitar Pro stores
    after a repeat opens: bit 0 is the first ending.
    """
    count = len(headers)
    order: list[int] = []
    index = 0
    # Each open repeat remembers where it started and which pass is playing.
    stack: list[list[int]] = []
    returns_left: dict[int, int] = {}
    entered_by_jump = False
    guard = 0
    limit = count * 256 + 1
    while index < count:
        guard += 1
        if guard > limit:
            raise ValueError("Guitar Pro repeats did not finish unfolding")
        header = headers[index]
        if bool(header.isRepeatOpen) and not entered_by_jump:
            stack.append([index, 1])
        entered_by_jump = False

        alternative = int(header.repeatAlternative or 0)
        if alternative and stack:
            bit = 1 << (stack[-1][1] - 1)
            if alternative & bit == 0:
                index += 1
                continue

        order.append(index)
        close = header.repeatClose
        close = -1 if close is None else int(close)
        if close > 0 and stack:
            left = returns_left.get(index)
            if left is None:
                left = close - 1
            if left > 0:
                returns_left[index] = left - 1
                start = stack[-1][0]
                for key in [key for key in returns_left if start <= key < index]:
                    del returns_left[key]
                stack[-1][1] += 1
                index = start
                entered_by_jump = True
                continue
            returns_left[index] = 0
            stack.pop()
        index += 1
    return order


def _compile_track(song, track) -> tuple[list[_Pluck], int, int]:
    guitarpro = _guitarpro()
    tempo_at = _tempo_changes(song)
    bpm = _song_bpm(song)
    seconds = 0.0
    last_tick = 0
    cursor = 0
    slide_into: set[int] = set()
    # Last real pluck on each Guitar Pro string, so a tie can lengthen it.
    held: dict[int, _Pluck] = {}
    raw: list[_Pluck] = []

    for measure_index in playback_measure_indices(song.measureHeaders):
        measure = track.measures[measure_index]
        origin = int(measure.start)
        beats = []
        for voice in measure.voices:
            for beat in voice.beats:
                beats.append((int(beat.start - origin), beat))
        beats.sort(key=lambda item: item[0])

        for local, beat in beats:
            tick = cursor + local
            if tick > last_tick:
                seconds += _seconds(tick - last_tick, bpm)
                last_tick = tick
            bpm = tempo_at.get((measure_index, local), bpm)
            _emit_beat(
                guitarpro,
                track,
                beat,
                tick,
                seconds,
                bpm,
                slide_into,
                held,
                raw,
            )
        cursor += int(measure.length)
    return _fit_strings(raw)


def _emit_beat(guitarpro, track, beat, tick, seconds, bpm, slide_into, held, raw) -> None:
    notes = list(beat.notes)
    if not notes:
        return
    # Grace notes sit just before the chord they decorate, on the same string.
    for note in notes:
        grace = note.effect.grace
        if grace is None:
            continue
        grace_ticks = int(grace.durationTime)
        grace_tick = tick if grace.isOnBeat else max(0, tick - grace_ticks)
        grace_time = seconds + _seconds(grace_tick - tick, bpm)
        open_midi = int(track.strings[note.string - 1].value)
        _emit_pitch(
            track,
            note.string,
            open_midi + int(grace.fret) + int(track.offset),
            grace_time,
            _seconds(max(grace_ticks, 1), bpm),
            0,
            slide_into,
            held,
            raw,
            is_tie=False,
            hammer_or_slide_to_next=grace.transition.name in ("slide", "hammer"),
        )

    for note in notes:
        if note.type == guitarpro.NoteType.rest:
            continue
        is_tie = note.type == guitarpro.NoteType.tie
        slides = {slide.name for slide in note.effect.slides}
        slide_flag = 1 if slides & set(_SLIDE_INTO) else 0
        duration_ticks = float(beat.duration.time) * float(note.durationPercent)
        _emit_pitch(
            track,
            note.string,
            int(note.realValue) + int(track.offset),
            seconds,
            _seconds(max(duration_ticks, 1), bpm),
            slide_flag,
            slide_into,
            held,
            raw,
            is_tie=is_tie,
            hammer_or_slide_to_next=bool(note.effect.hammer) or bool(slides & set(_SLIDE_TO_NEXT)),
        )


def _emit_pitch(
    track,
    gp_string,
    midi,
    timestamp,
    duration_s,
    slide,
    slide_into,
    held,
    raw,
    *,
    is_tie,
    hammer_or_slide_to_next,
) -> None:
    gp_string = int(gp_string)
    if is_tie:
        previous = held.get(gp_string)
        if previous is not None and previous.midi == int(midi):
            previous.duration_s = round(previous.duration_s + float(duration_s), 6)
        return

    arriving = 1 if gp_string in slide_into else 0
    slide_into.discard(gp_string)
    if hammer_or_slide_to_next:
        slide_into.add(gp_string)

    open_midi = int(track.strings[gp_string - 1].value)
    robot = _robot_string(open_midi)
    fret = int(midi) - open_midi
    preferred = robot if robot is not None and _fret_in_range(robot, fret) else None
    pluck = _Pluck(
        midi=int(midi),
        timestamp=float(timestamp),
        duration_s=float(duration_s),
        slide=1 if slide or arriving else 0,
        preferred=preferred,
    )
    held[gp_string] = pluck
    raw.append(pluck)


def _fit_strings(raw: list[_Pluck]) -> tuple[list[_Pluck], int, int]:
    """Pin each note to a string the left hand can reach before the pluck."""
    from control.path_planner.model import Note, StringState, candidates, viable

    ordered = sorted(raw, key=lambda pluck: pluck.timestamp)
    frets = [0] * len(tu.STRING_MIDI_RANGES)
    free_at = [-0.5] * len(tu.STRING_MIDI_RANGES)
    kept: list[_Pluck] = []
    moved = 0
    skipped = 0
    for pluck in ordered:
        probe = Note(
            pitch=pluck.midi,
            t=pluck.timestamp,
            dur=pluck.duration_s,
            slide_in=bool(pluck.slide),
            forced_string=None,
        )
        options = candidates(probe)
        chosen = None
        if pluck.preferred is not None:
            for string, fret in options:
                state = StringState(frets[string], free_at[string])
                if string == pluck.preferred and viable(state, probe, fret):
                    chosen = (string, fret)
                    break
        if chosen is None:
            ranked = []
            for string, fret in options:
                state = StringState(frets[string], free_at[string])
                if viable(state, probe, fret):
                    ranked.append((abs(fret - frets[string]), string, fret))
            if ranked:
                ranked.sort()
                _, string, fret = ranked[0]
                chosen = (string, fret)
                moved += 1
        if chosen is None:
            skipped += 1
            continue
        string, fret = chosen
        pluck.string_index = string
        frets[string] = fret
        free_at[string] = pluck.timestamp
        kept.append(pluck)
    return kept, moved, skipped


def _event_dict(pluck: _Pluck) -> dict[str, Any]:
    event = {
        "note": pluck.midi,
        "duration_s": round(pluck.duration_s, 6),
        "slide": int(pluck.slide),
        "timestamp": round(pluck.timestamp, 6),
    }
    if pluck.string_index is not None:
        event["string_index"] = int(pluck.string_index)
    return event


def _tempo_changes(song) -> dict[tuple[int, int], float]:
    found: dict[tuple[int, int], float] = {}
    for track in song.tracks:
        for measure_index, measure in enumerate(track.measures):
            for voice in measure.voices:
                for beat in voice.beats:
                    change = beat.effect.mixTableChange
                    if change is None or change.tempo is None or change.tempo.value <= 0:
                        continue
                    local = int(beat.start - measure.start)
                    found[(measure_index, local)] = float(change.tempo.value)
    return found


def _select_track(song, track) -> tuple[Any, int]:
    tracks = list(song.tracks)
    if track is None:
        scored = [(_track_score(item), index, item) for index, item in enumerate(tracks)]
        playable = [item for item in scored if item[0] > 0]
        if not playable:
            names = ", ".join(item.name.strip() or f"track {index}" for index, item in enumerate(tracks))
            raise ValueError(f"No guitar track fits the robot. Tracks: {names or '(none)'}")
        playable.sort(key=lambda item: (-item[0], item[1]))
        _, index, chosen = playable[0]
        return chosen, index

    if isinstance(track, int):
        return _track_at(tracks, track), track

    text = str(track).strip()
    matches = [(index, item) for index, item in enumerate(tracks) if item.name.strip().casefold() == text.casefold()]
    if len(matches) == 1:
        index, chosen = matches[0]
        _reject_drums(chosen)
        return chosen, index
    if len(matches) > 1:
        raise ValueError(f"More than one track is named {text!r}")
    if text.isdigit():
        index = int(text)
        return _track_at(tracks, index), index
    names = ", ".join(item.name.strip() or f"track {index}" for index, item in enumerate(tracks))
    raise ValueError(f"No track named {text!r}. Tracks: {names}")


def _track_at(tracks, index: int):
    if index < 0 or index >= len(tracks):
        raise ValueError(f"Track index {index} is outside 0..{len(tracks) - 1}")
    chosen = tracks[index]
    _reject_drums(chosen)
    return chosen


def _reject_drums(track) -> None:
    if track.isPercussionTrack:
        raise ValueError(f"Track {track.name.strip()!r} is drums, not a guitar part")


def _track_score(track) -> int:
    if track.isPercussionTrack:
        return -1
    guitarpro = _guitarpro()
    capo = int(track.offset)
    score = 0
    for measure in track.measures:
        for voice in measure.voices:
            for beat in voice.beats:
                for note in beat.notes:
                    if note.type == guitarpro.NoteType.tie:
                        continue
                    open_midi = int(track.strings[note.string - 1].value)
                    midi = open_midi + int(note.value) + capo
                    robot = _robot_string(open_midi)
                    if robot is not None and _fret_in_range(robot, int(note.value) + capo):
                        score += 2
                    elif _playable(midi):
                        score += 1
    return score


def _robot_string(open_midi: int) -> int | None:
    for index, (low, _high) in enumerate(tu.STRING_MIDI_RANGES):
        if low == int(open_midi):
            return index
    return None


def _fret_in_range(string: int, fret: int) -> bool:
    low, high = tu.STRING_MIDI_RANGES[string]
    return 0 <= int(fret) <= high - low


def _playable(midi: int) -> bool:
    return any(low <= int(midi) <= high for low, high in tu.STRING_MIDI_RANGES)


def _song_bpm(song) -> float:
    tempo = song.tempo
    value = getattr(tempo, "value", tempo)
    bpm = float(value)
    if bpm <= 0:
        raise ValueError(f"Song tempo must be positive, got {bpm}")
    return bpm


def _time_signature(song) -> str:
    counts: Counter[str] = Counter()
    for header in song.measureHeaders:
        signature = header.timeSignature
        counts[f"{signature.numerator}/{signature.denominator.value}"] += 1
    if not counts:
        return "4/4"
    return counts.most_common(1)[0][0]


def _key_name(signature) -> str:
    name = getattr(signature, "name", None) or str(signature)
    for suffix, replacement in (
        ("MinorSharp", "# minor"),
        ("MajorSharp", "#"),
        ("MinorFlat", "b minor"),
        ("MajorFlat", "b"),
        ("Minor", " minor"),
        ("Major", ""),
    ):
        if name.endswith(suffix):
            return name[: -len(suffix)] + replacement
    return name


def _seconds(ticks: float, bpm: float) -> float:
    return float(ticks) * 60.0 / (float(bpm) * _QUARTER)


def _guitarpro():
    try:
        import guitarpro
    except ImportError as exc:
        raise ImportError(
            "Reading .gp3 files requires pyguitarpro. Install it with: pip install pyguitarpro"
        ) from exc
    return guitarpro


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compile a Guitar Pro 3 file into GuitarBot pluck events")
    parser.add_argument("path", help="Path to a .gp3 file")
    parser.add_argument("--track", default=None, help="Track name or zero-based index. Default: the guitar part that fits the robot")
    parser.add_argument("--list", action="store_true", help="List tracks and exit")
    parser.add_argument("--output", "-o", help="Write the song JSON here")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    if args.list:
        for row in list_tracks(args.path):
            kind = "drums" if row["percussion"] else "guitar"
            print(f"{row['index']}: {row['name']} ({kind}, score {row['score']})")
        return
    compiled = compile_gp3(args.path, track=args.track)
    print(
        f"{compiled.song['song']['name']}: {compiled.events} plucks "
        f"on {compiled.track_name!r} ({compiled.moved} moved, {compiled.skipped} skipped)"
    )
    if args.output:
        destination = Path(args.output)
        destination.write_text(json.dumps(compiled.song, indent=2), encoding="utf-8")
        print(f"Wrote {destination}")


if __name__ == "__main__":
    main()
