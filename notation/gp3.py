"""Compile a Guitar Pro tab into the song dict ``SongArrangement`` plans.

The decoder is ``pyguitarpro`` (``.gp3``, ``.gp4``, and ``.gp5``). This module
turns one guitar track into pluck events: MIDI pitch, duration, time, and the
string the robot should use. Eighth-note and sixteenth-note triplet feel is
played as swing, and repeats are unfolded with their alternate endings.
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
    thinned: int = 0
    absorbed: int = 0


@dataclass
class _Pluck:
    midi: int
    timestamp: float
    duration_s: float
    slide: int
    preferred: int | None
    string_index: int | None = None


def gp3_to_song_dict(path: str | Path, *, track=None) -> dict[str, Any]:
    """Guitar Pro file → the song dict ``SongArrangement.from_dict`` expects."""
    return compile_gp3(path, track=track).song


def compile_gp3(path: str | Path, *, track=None) -> Gp3Compile:
    """Read ``path`` and compile one track into pluck events.

    Each attack is placed on a fret the left hand can reach, moving a fast run
    onto another string when the written one is still in motion. Hammer-ons and
    slides are plucked. Inner chord tones are left out unless a finger is
    already on that fret. A note that still will not fit is rolled into a
    tremolo on the previous melody or bass note.
    """
    guitarpro = _guitarpro()
    source = Path(path)
    song = guitarpro.parse(str(source))
    chosen, index = _select_track(song, track)
    plucks, moved, skipped, thinned, absorbed = _compile_track(song, chosen)
    if not plucks:
        raise ValueError(f"No playable notes on track {chosen.name!r}")

    title = (song.title or source.stem).strip() or source.stem
    track_name = _track_label(chosen, index)
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
        thinned=thinned,
        absorbed=absorbed,
    )


def list_tracks(path: str | Path) -> list[dict[str, Any]]:
    """Name, index, and how well each track fits the robot's fretboard."""
    song = _guitarpro().parse(str(path))
    rows = []
    for index, track in enumerate(song.tracks):
        rows.append(
            {
                "index": index,
                "name": _track_label(track, index),
                "percussion": bool(track.isPercussionTrack),
                "strings": [int(string.value) for string in track.strings],
                "score": _track_score(track),
            }
        )
    return rows


def playback_measure_indices(headers) -> list[int]:
    """Measure indices in the order they are played, with repeats unfolded.

    ``repeatClose`` is how many times playback jumps back to the opening
    repeat. A repeat sign with no extra count is 1, so the group plays twice.
    Guitar Pro 5 stores one more than that in the file; pyguitarpro has
    already subtracted it, and the same number comes out of a GP3 file.
    Alternate endings use the bitmask stored after a repeat opens: bit 0 is
    the first ending. A repeat that closes on a skipped ending still jumps.
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
                if _repeat_jumps(header, index, stack, returns_left):
                    index = stack[-1][0]
                    entered_by_jump = True
                    continue
                index += 1
                continue

        order.append(index)
        if _repeat_jumps(header, index, stack, returns_left):
            index = stack[-1][0]
            entered_by_jump = True
            continue
        index += 1
    return order


def _repeat_jumps(header, index: int, stack: list[list[int]], returns_left: dict[int, int]) -> bool:
    """Jump back when this bar still owes repeats. Pop the group on the last pass."""
    close = header.repeatClose
    close = -1 if close is None else int(close)
    if close <= 0 or not stack:
        return False
    left = returns_left.get(index)
    if left is None:
        left = close
    if left > 0:
        returns_left[index] = left - 1
        start = stack[-1][0]
        for key in [key for key in returns_left if start <= key < index]:
            del returns_left[key]
        stack[-1][1] += 1
        return True
    returns_left[index] = 0
    stack.pop()
    return False


def _compile_track(song, track) -> tuple[list[_Pluck], int, int, int, int]:
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
        feel = song.measureHeaders[measure_index].tripletFeel
        origin = int(measure.start)
        beats = []
        for voice in measure.voices:
            for beat in voice.beats:
                beats.append((int(beat.start - origin), beat))
        beats.sort(key=lambda item: item[0])

        for local, beat in beats:
            swung = cursor + _swing_offset(local, feel)
            if swung > last_tick:
                seconds += _seconds(swung - last_tick, bpm)
                last_tick = swung
            bpm = tempo_at.get((measure_index, local), bpm)
            _emit_beat(
                guitarpro,
                track,
                beat,
                local,
                cursor,
                feel,
                seconds,
                bpm,
                slide_into,
                held,
                raw,
            )
        cursor += int(measure.length)
    return _arrange(raw)


def _emit_beat(guitarpro, track, beat, local, cursor, feel, seconds, bpm, slide_into, held, raw) -> None:
    notes = list(beat.notes)
    if not notes:
        return
    # Grace notes sit just before the chord they decorate, on the same string.
    for note in notes:
        grace = note.effect.grace
        if grace is None:
            continue
        grace_ticks = int(grace.durationTime)
        grace_local = _grace_local(local, grace_ticks, bool(grace.isOnBeat), cursor)
        # The grace sounds before this beat, so the offset is negative.
        grace_time = seconds + _seconds(
            _swing_offset(grace_local, feel) - _swing_offset(float(local), feel),
            bpm,
        )
        open_midi = int(track.strings[note.string - 1].value)
        _emit_pitch(
            track,
            note.string,
            open_midi + int(grace.fret) + int(track.offset),
            max(0.0, grace_time),
            _span_seconds(grace_local, grace_local + max(grace_ticks, 1), feel, bpm),
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
            _span_seconds(local, local + max(duration_ticks, 1), feel, bpm),
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


def _arrange(raw: list[_Pluck]) -> tuple[list[_Pluck], int, int, int, int]:
    """Place every attack on a fret the hand can reach before the pluck.

    The written string is kept when it is free. A run that comes back before
    that slider can move is searched across the other frets of the same pitch,
    including an octave when the written one does not fit. Chords keep their
    bass and melody; an inner voice is played only when a finger is already
    standing on it. Anything still too fast lengthens the previous melody or
    bass note into a tremolo instead of leaving a hole. Hammer-ons and slides
    are ordinary plucks.
    """
    strings = len(tu.STRING_MIDI_RANGES)
    frets = [0] * strings
    # Free long enough before the first beat that any fret is in reach at t = 0.
    free_at = [-float(tu.LH_PREP_TIME_BEFORE_PICK)] * strings
    kept: list[_Pluck] = []
    moved = 0
    skipped = 0
    thinned = 0
    absorbed = 0
    melody: _Pluck | None = None
    bass: _Pluck | None = None

    for group in _chords(raw):
        hi = max(group, key=lambda pluck: pluck.midi)
        lo = min(group, key=lambda pluck: pluck.midi)
        roles = [hi] if lo.midi == hi.midi else [hi, lo]
        roles.sort(key=lambda pluck: (len(_frettings(_folded(pluck.midi))), -pluck.midi))
        used: set[int] = set()
        placed: dict[int, _Pluck] = {}
        for pluck in roles:
            choice = _place(pluck, frets, free_at, used)
            if choice is None:
                anchor = melody if pluck is hi else bass
                if anchor is not None and _roll_into(anchor, pluck, free_at):
                    absorbed += 1
                else:
                    skipped += 1
                continue
            pitch, string, fret, retuned = choice
            _commit(pluck, pitch, string, fret, frets, free_at)
            used.add(string)
            placed[id(pluck)] = pluck
            kept.append(pluck)
            if retuned:
                moved += 1
        if id(hi) in placed:
            melody = hi
        if lo is not hi and id(lo) in placed:
            bass = lo
        for pluck in group:
            if pluck is hi or pluck is lo:
                continue
            if _place_parked(pluck, frets, free_at, used):
                kept.append(pluck)
                continue
            thinned += 1
    kept.sort(key=lambda pluck: pluck.timestamp)
    return kept, moved, skipped, thinned, absorbed


def _chords(raw: list[_Pluck]):
    """Notes that sound together, in time order."""
    ordered = sorted(raw, key=lambda pluck: (pluck.timestamp, -pluck.midi))
    group: list[_Pluck] = []
    for pluck in ordered:
        if group and pluck.timestamp - group[0].timestamp > 1e-4:
            yield group
            group = []
        group.append(pluck)
    if group:
        yield group


def _pitches(midi: int) -> list[int]:
    """Written pitch folded onto the fretboard, then the neighboring octave."""
    low = min(bottom for bottom, _top in tu.STRING_MIDI_RANGES)
    high = max(top for _bottom, top in tu.STRING_MIDI_RANGES)
    shifted = int(midi)
    while shifted > high:
        shifted -= 12
    while shifted < low:
        shifted += 12
    if shifted < low or shifted > high:
        return []
    found = [shifted]
    for alt in (shifted + 12, shifted - 12):
        if low <= alt <= high and alt not in found:
            found.append(alt)
    return found


def _folded(midi: int) -> int | None:
    pitches = _pitches(midi)
    return pitches[0] if pitches else None


def _frettings(midi: int | None) -> list[tuple[int, int]]:
    if midi is None:
        return []
    found = []
    for string, (open_midi, top) in enumerate(tu.STRING_MIDI_RANGES):
        fret = int(midi) - open_midi
        if 0 <= fret <= top - open_midi:
            found.append((string, fret))
    return found


def _hand_ready(current: int, free: float, fret: int, when: float) -> bool:
    """The slider can be on `fret` at `when` without rushing the prep window."""
    if current == fret:
        return when + 1e-9 >= free
    prep = float(tu.LH_PREP_TIME_BEFORE_PICK)
    if when - prep + 1e-9 < free:
        return False
    dt = when - free
    travel = abs(fret - current)
    return not travel or (dt > 0 and travel / dt <= 80.0)


def _ready(midi: int, when: float, frets: list[int], free_at: list[float], used: set[int]):
    ready = []
    for string, fret in _frettings(midi):
        if string in used:
            continue
        if _hand_ready(frets[string], free_at[string], fret, when):
            ready.append((string, fret))
    return ready


def _choose(options, frets, free_at, when: float, preferred: int | None):
    """Written string first, then a fret a finger is already on, then the string left idle longest."""

    def key(item):
        string, fret = item
        home = preferred is not None and string == preferred
        parked = frets[string] == fret
        return (
            0 if home else 1,
            0 if parked else 1,
            -(when - free_at[string]),
            abs(fret - frets[string]),
            string,
        )

    return min(options, key=key)


def _place(pluck: _Pluck, frets, free_at, used: set[int]):
    for index, pitch in enumerate(_pitches(pluck.midi)):
        options = _ready(pitch, pluck.timestamp, frets, free_at, used)
        if not options:
            continue
        preferred = pluck.preferred if index == 0 else None
        string, fret = _choose(options, frets, free_at, pluck.timestamp, preferred)
        retuned = pitch != int(pluck.midi) or string != pluck.preferred
        return pitch, string, fret, retuned
    return None


def _commit(pluck: _Pluck, pitch: int, string: int, fret: int, frets, free_at) -> None:
    pluck.midi = int(pitch)
    pluck.string_index = int(string)
    pluck.slide = 0
    frets[string] = int(fret)
    end = pluck.timestamp
    if pluck.duration_s >= float(tu.TREMOLO_DURATION_THRESHOLD):
        end = pluck.timestamp + pluck.duration_s
    free_at[string] = end


def _place_parked(pluck: _Pluck, frets, free_at, used: set[int]) -> bool:
    """Pluck an inner voice only where a slider is already standing on that pitch."""
    pitch = _folded(pluck.midi)
    for string, fret in _frettings(pitch):
        if string in used or frets[string] != fret:
            continue
        if not _hand_ready(frets[string], free_at[string], fret, pluck.timestamp):
            continue
        _commit(pluck, pitch, string, fret, frets, free_at)
        used.add(string)
        return True
    return False


def _roll_into(anchor: _Pluck, missed: _Pluck, free_at: list[float]) -> bool:
    """Lengthen `anchor` so the picker rolls through an attack the hand cannot fret."""
    if anchor.string_index is None:
        return False
    if missed.timestamp <= anchor.timestamp + 1e-4:
        return False
    if missed.timestamp > anchor.timestamp + 1.0:
        return False
    threshold = float(tu.TREMOLO_DURATION_THRESHOLD)
    end = max(missed.timestamp, anchor.timestamp + threshold)
    end = min(end, anchor.timestamp + 1.0)
    if end - anchor.timestamp + 1e-9 < threshold:
        return False
    anchor.duration_s = round(max(anchor.duration_s, end - anchor.timestamp), 6)
    free_at[anchor.string_index] = anchor.timestamp + anchor.duration_s
    return True


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


def _swing_offset(offset: float, feel) -> float:
    """Straight tick offset → where it sounds under this measure's triplet feel.

    Eighth feel plays two written eighths as a quarter-note triplet, long then
    short. Sixteenth feel does the same inside each eighth. Barlines stay put,
    and no feel returns the offset unchanged.
    """
    kind = _feel_name(feel)
    if kind == "eighth":
        group = float(_QUARTER)
    elif kind == "sixteenth":
        group = float(_QUARTER // 2)
    else:
        return float(offset)
    pivot = group / 2.0
    group_index, rem = divmod(float(offset), group)
    long = group * 2.0 / 3.0
    short = group / 3.0
    if rem <= pivot:
        swung = rem * long / pivot
    else:
        swung = long + (rem - pivot) * short / pivot
    return group_index * group + swung


def _span_seconds(start: float, end: float, feel, bpm: float) -> float:
    """Seconds between two straight tick positions after triplet feel."""
    return _seconds(max(_swing_offset(end, feel) - _swing_offset(start, feel), 1), bpm)


def _grace_local(local: float, grace_ticks: float, on_beat: bool, cursor: float) -> float:
    """Tick offset of a grace note. One that would fall before the song starts at 0."""
    if on_beat:
        return float(local)
    grace_at = float(cursor) + float(local) - float(grace_ticks)
    if grace_at < 0:
        return -float(cursor)
    return float(local) - float(grace_ticks)


def _feel_name(feel) -> str:
    name = getattr(feel, "name", None)
    if name:
        return str(name)
    text = str(feel or "none")
    return text.rsplit(".", 1)[-1]


# General MIDI program numbers pyguitarpro leaves on the channel. Empty track
# names in a GP5 file fall back to these.
_INSTRUMENT_NAMES = {
    24: "Nylon Guitar",
    25: "Steel Guitar",
    26: "Jazz Guitar",
    27: "Clean Guitar",
    32: "Acoustic Bass",
    33: "Finger Bass",
}


def _track_label(track, index: int) -> str:
    name = track.name.strip()
    if name:
        return name
    instrument = int(getattr(track.channel, "instrument", -1))
    if instrument in _INSTRUMENT_NAMES:
        return _INSTRUMENT_NAMES[instrument]
    if len(track.strings) >= 6:
        return "Guitar"
    if track.strings and int(track.strings[-1].value) < 40:
        return "Bass"
    return f"track {index}"


def _guitarpro():
    try:
        import guitarpro
    except ImportError as exc:
        raise ImportError(
            "Reading Guitar Pro files requires pyguitarpro. Install it with: pip install pyguitarpro"
        ) from exc
    return guitarpro


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compile a Guitar Pro file into GuitarBot pluck events")
    parser.add_argument("path", help="Path to a .gp3, .gp4, or .gp5 file")
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
        f"on {compiled.track_name!r} ({compiled.moved} retuned, "
        f"{compiled.thinned} inner voices left out, "
        f"{compiled.absorbed} rolled into tremolo, {compiled.skipped} dropped)"
    )
    if args.output:
        destination = Path(args.output)
        destination.write_text(json.dumps(compiled.song, indent=2), encoding="utf-8")
        print(f"Wrote {destination}")


if __name__ == "__main__":
    main()
