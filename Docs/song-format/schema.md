# Events JSON Schema

Canonical document for the robot play path.

- UI posts this to `POST /play`
- Python: `SongArrangement.from_dict` / `from_json_path` → `to_planner_rows()`
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

## Chord event

```json
{ "chord": "Em", "timestamp": 0.0 }
```

`chord` + `timestamp` or `beat`.

## Planner rows

`to_planner_rows()` → `(chord_rows, pluck_rows)` for `GuitarBotParser`.
Missing chords → default `On` after last pluck.
`meta.tempo_curve` is applied when present.
