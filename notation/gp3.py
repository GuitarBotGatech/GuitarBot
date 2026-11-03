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
    lowered: int
    skipped: int


@dataclass
class _Pluck:
    midi: int
    timestamp: float
    duration_s: float
    slide: int
    preferred: int | None
    lowered: bool = False
    string_index: int | None = None


def gp3_to_song_dict(path: str | Path, *, track=None) -> dict[str, Any]:
    """``.gp3`` file → the song dict ``SongArrangement.from_dict`` expects."""
    return compile_gp3(path, track=track).song


def compile_gp3(path: str | Path, *, track=None) -> Gp3Compile:
    """Read ``path`` and compile one track into pluck events.

    A pitch above every string drops by octaves until one can sound it. The tab
    string is kept when the left hand can reach that fret in time. Otherwise the
    note moves to another string that can sound it. If a fret change is still
    too soon, the whole song slows until the hand can make it. Two pitches that
    need the same string at the same instant are left out.
    """
    guitarpro = _guitarpro()
    source = Path(path)
    song = guitarpro.parse(str(source))
    chosen, index = _select_track(song, track)
    plucks, moved, skipped, bpm = _compile_track(song, chosen)
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
                "bpm": bpm,
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
        lowered=sum(1 for pluck in plucks if pluck.lowered),
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


def _compile_track(song, track) -> tuple[list[_Pluck], int, int, float]:
    guitarpro = _guitarpro()
    tempo_at = _tempo_changes(song)
    initial_bpm = _song_bpm(song)
    bpm = initial_bpm
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
    kept, moved, skipped, timing = _fit_strings(raw)
    if timing == 0:
        return kept, moved, skipped, initial_bpm

    # Place every note the fretboard can sound, then stretch the song so each
    # fret change has the left hand's prep window. The written tempo already
    # failed that test, so keep this assignment instead of letting a slower
    # tempo pick a busier string.
    for pluck in raw:
        pluck.string_index = None
    moved = _place_without_time(raw)
    scale = _hand_scale(raw)
    if scale > 1.0:
        for pluck in raw:
            pluck.timestamp *= scale
            pluck.duration_s *= scale
    # The planner will not start a fret change before time 0, so the first
    # fretted note has to sit a full prep window into the song.
    lead = _lead_in(raw)
    if lead:
        for pluck in raw:
            pluck.timestamp += lead
    for pluck in raw:
        if pluck.string_index is not None:
            pluck.preferred = pluck.string_index
            pluck.string_index = None
    kept, _, skipped, _timing = _fit_strings(raw)
    return kept, moved, skipped, initial_bpm / scale


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
    written = int(midi)
    sounding = _lower_into_range(written)
    if is_tie:
        previous = held.get(gp_string)
        if previous is not None and previous.midi == sounding:
            previous.duration_s = round(previous.duration_s + float(duration_s), 6)
        return

    arriving = 1 if gp_string in slide_into else 0
    slide_into.discard(gp_string)
    if hammer_or_slide_to_next:
        slide_into.add(gp_string)

    open_midi = int(track.strings[gp_string - 1].value)
    robot = _robot_string(open_midi)
    fret = sounding - open_midi
    preferred = robot if robot is not None and _fret_in_range(robot, fret) else None
    pluck = _Pluck(
        midi=sounding,
        timestamp=float(timestamp),
        duration_s=float(duration_s),
        slide=1 if slide or arriving else 0,
        preferred=preferred,
        lowered=sounding != written,
    )
    held[gp_string] = pluck
    raw.append(pluck)


def _fit_strings(raw: list[_Pluck]) -> tuple[list[_Pluck], int, int, int]:
    """Pin each note to a string the left hand can reach before the pluck.

    The last count is how many skipped notes a slower tempo could still reach.
    """
    from control.path_planner.model import Note, StringState, candidates, viable

    ordered = sorted(raw, key=lambda pluck: pluck.timestamp)
    frets = [0] * len(tu.STRING_MIDI_RANGES)
    free_at = [-0.5] * len(tu.STRING_MIDI_RANGES)
    kept: list[_Pluck] = []
    moved = 0
    skipped = 0
    timing = 0
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
        if chosen is None:
            busy = {
                other.string_index
                for other in kept
                if abs(other.timestamp - pluck.timestamp) < 1e-6
            }
            if any(string not in busy for string, _fret in options):
                timing += 1
            skipped += 1
            continue
        string, fret = chosen
        # Octave-lowering can stack two written notes on one pitch. One pluck sounds it.
        if any(
            other.string_index == string
            and other.midi == pluck.midi
            and abs(other.timestamp - pluck.timestamp) < 1e-6
            for other in kept
        ):
            continue
        if pluck.preferred != string:
            moved += 1
        pluck.string_index = string
        frets[string] = fret
        free_at[string] = pluck.timestamp
        kept.append(pluck)
    return kept, moved, skipped, timing


def _place_without_time(raw: list[_Pluck]) -> int:
    """Give every note a string, ignoring how soon the hand must move.

    A string already used at that instant is taken. The return value is how
    many notes left their tab string.
    """
    from control.path_planner.model import Note, candidates

    ordered = sorted(raw, key=lambda pluck: pluck.timestamp)
    frets = [0] * len(tu.STRING_MIDI_RANGES)
    moved = 0
    for pluck in ordered:
        pluck.string_index = None
        probe = Note(
            pitch=pluck.midi,
            t=pluck.timestamp,
            dur=pluck.duration_s,
            slide_in=bool(pluck.slide),
            forced_string=None,
        )
        busy = {
            other.string_index
            for other in ordered
            if other.string_index is not None and abs(other.timestamp - pluck.timestamp) < 1e-6
        }
        ranked = []
        for string, fret in candidates(probe):
            if string in busy:
                continue
            prefer = 0 if string == pluck.preferred else 1
            ranked.append((prefer, abs(fret - frets[string]), string, fret))
        if not ranked:
            continue
        ranked.sort()
        _, _, string, fret = ranked[0]
        if pluck.preferred != string:
            moved += 1
        pluck.string_index = string
        frets[string] = fret
    return moved


def _lead_in(notes: list[_Pluck]) -> float:
    """Delay so the first fret change's prep starts at time 0."""
    prep = float(tu.LH_PREP_TIME_BEFORE_PICK)
    earliest = 0.0
    for note in notes:
        if note.string_index is None:
            continue
        fret = note.midi - tu.STRING_MIDI_RANGES[note.string_index][0]
        if fret == 0 and not note.slide:
            continue
        earliest = min(earliest, note.timestamp - prep)
    if earliest >= -1e-9:
        return 0.0
    return -earliest + 1e-4


def _hand_scale(notes: list[_Pluck]) -> float:
    """Stretch factor so every assigned fret change gets the prep window."""
    from control.path_planner.model import _MAX_FRETS_PER_S

    prep = float(tu.LH_PREP_TIME_BEFORE_PICK)
    scale = 1.0
    groups: dict[int, list[_Pluck]] = {}
    for note in notes:
        if note.string_index is None:
            continue
        groups.setdefault(note.string_index, []).append(note)
    for string, group in groups.items():
        group.sort(key=lambda note: note.timestamp)
        fret = 0
        last_t = -0.5
        open_pitch = tu.STRING_MIDI_RANGES[string][0]
        for note in group:
            target = note.midi - open_pitch
            if last_t >= 0 and (target != fret or note.slide):
                gap = note.timestamp - last_t
                if gap > 1e-9:
                    need = prep
                    travel = abs(target - fret)
                    if travel:
                        need = max(need, travel / float(_MAX_FRETS_PER_S))
                    scale = max(scale, (need + 1e-4) / gap)
            fret = target
            last_t = note.timestamp
    return scale


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
                    midi = _lower_into_range(open_midi + int(note.value) + capo)
                    robot = _robot_string(open_midi)
                    if robot is not None and _fret_in_range(robot, midi - open_midi):
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


def _lower_into_range(midi: int) -> int:
    """Drop a pitch by octaves until a robot string can sound it.

    Notes that already fit, and notes below the fretboard, stay where they are.
    One octave below the top fret is still inside the fretboard, so a high note
    always lands on a playable pitch.
    """
    pitch = int(midi)
    high = max(top for _low, top in tu.STRING_MIDI_RANGES)
    while pitch > high:
        pitch -= 12
    return pitch


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
    bpm = compiled.song["song"]["meta"]["bpm"]
    print(
        f"{compiled.song['song']['name']}: {compiled.events} plucks "
        f"on {compiled.track_name!r} at {bpm:g} bpm "
        f"({compiled.moved} moved, {compiled.lowered} lowered, {compiled.skipped} skipped)"
    )
    if args.output:
        destination = Path(args.output)
        destination.write_text(json.dumps(compiled.song, indent=2), encoding="utf-8")
        print(f"Wrote {destination}")


if __name__ == "__main__":
    main()
