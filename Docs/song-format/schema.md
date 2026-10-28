# Events JSON Schema

Canonical document for the robot play path.

- UI posts this to `POST /play`
- Python: `SongArrangement.from_dict` → `to_plan()`
- `configs/default.yaml` fills missing pluck `speed` / `slide`
- Legacy `type: "midi"` tracks are ignored

## Shape

```json
{
  "song": {
    "name": "string",
    "meta": {
      "key": "E minor",
      "time_signature": "4/4",
      "bpm": 120,
      "tempo_curve": [
        {"time": 0.0, "bpm": 120},
        {"time": 4.0, "bpm": 90}
      ]
    },
    "tracks": [
      {"name": "chords_main", "type": "chord", "events": []},
      {"name": "pluck_main", "type": "pluck", "events": []}
    ]
  }
}
```

## Pluck event

```json
{
  "note": 52,
  "duration_b": 0.5,
  "speed": 5,
  "slide": 0,
  "timestamp": 1.5,
  "string_index": 2
}
```

- `duration_b` (beats), `duration_s` (seconds), or legacy `duration` (beats)
- `timestamp` (seconds) or `beat` (`bar.beat[.sub]` / `~raw_beats`)
- `speed` / `slide` optional (config defaults)
- `string_index` optional, **0-based** (`0` = low E … `5` = high e); omit to let the planner choose

## Chord event

```json
{ "chord": "Em", "timestamp": 0.0 }
```

`chord` + `timestamp` or `beat`.

A chord sounds nothing by itself. A pluck whose `note` is `0`–`5` is a string
index: it plays that string at the fret the active chord gives it, pinned to
that string. Before the first chord the string plays open. A string the chord
mutes is not plucked; the presser damps it instead, and the slider stays put.

## Planner rows

`to_plan()` → pluck rows for `GuitarBotParser`, with chord-string plucks
resolved to pitches, plus a mute for each string the chord damps.
`meta.tempo_curve` is applied when present.
