# Song Arrangement JSON Schema (MVP)

This schema is the **user-facing intermediary** for DAW-like composition.
It maps to OSC payloads for:
- `/Chords`
- `/Pluck`
- `/Midi`

## Top-level

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
      {
        "name": "pluck_main",
        "type": "pluck",
        "events": []
      }
    ]
  }
}
```

## Track types

### `pluck` track events

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

Fields:
- `note` (int): MIDI note number
- `duration_b` (float, beats): explicit duration in beats (recommended)
- `duration_s` (float, sec): explicit duration in seconds
- `duration` (legacy): still accepted, interpreted as **beats** by default
- `speed` (int): pluck speed scalar
- `slide` (int): 0/1 slide toggle
- `timestamp` (float, sec): absolute arrangement time
- `beat` (optional string): Ableton-style beat label (`bar.beat` or `bar.beat.sub`), alternative to `timestamp`
- `string_index` (optional int): explicit string override

### `chord` track events

```json
{
  "chord": "Em",
  "timestamp": 0.0
}
```

Fields:
- `chord` (string): chord token accepted by parser (e.g. `Em`, `D`, `On`)
- `timestamp` (float, sec)
- `beat` (optional string): Ableton-style beat label (`bar.beat` or `bar.beat.sub`), alternative to `timestamp`

### `midi` track events

```json
{
  "address": "/cc",
  "args": [7, 30],
  "interp": 1,
  "timestamp": 0.0
}
```

Fields:
- `address` (string): OSC-style MIDI address (`/cc`, `/note`, `/noteoff`, ...)
- `args` (array): MIDI args excluding timestamp
- `interp` (optional int): interpolation flag for supported message types (0/1)
- `timestamp` (float, sec)
- `beat` (optional string): Ableton-style beat label (`bar.beat` or `bar.beat.sub`), alternative to `timestamp`

## Beat labels (Phase 2)

Beat labels mimic DAW arrangements (Ableton-style):

- `1.1` = first measure, first beat
- `2.1` = second measure, first beat
- `3.2.1` = third measure, second beat (same as `3.2`)
- `3.2.2` = third measure, second beat, second subdivision

By default, subdivision index is quarter-beat (4 subdivisions per beat).
So in `4/4 @ 120 BPM`, `3.2.2` is `0.125s` after `3.2.1`.

## Invariants (MVP)

- `song.meta.bpm > 0`
- `song.meta.tempo_curve` points (if present) must have non-negative time and positive BPM
- Timestamps are non-negative and non-decreasing inside each track
- Each event must include either `timestamp` or `beat`
- Event shape is validated by track `type`

## OSC rendering (MVP)

- `pluck` track -> list of rows for `/Pluck`
- `chord` track -> list of rows for `/Chords`
- `midi` track -> list of rows for `/Midi`

Merged output is ordered by timestamp per address.

## DAW-style timeline controls (Phase 2)

The arrangement model now supports transformation-style editing operations:

- `shift_time(seconds)`
- `copy_range(start_s, end_s)`
- `paste_at(clip, start_s)`
- `reverse_range(start_s, end_s, duration_policy=...)`
- `quantize(subdivisions_per_beat=..., strength=..., swing=...)`
- `scale_tempo(new_bpm)`
- `scale_tempo_curve(control_points)`

### Reverse duration policies

- `preserve` (default): mirrors event start timestamps only.
- `mirror_end`: for pluck events, mirrors note end-points (duration-aware reversal).

### Quantize controls

- `subdivisions_per_beat`: beat-grid resolution (e.g. 4 = quarter-beat grid)
- `strength` in `[0.0, 1.0]`: blend between original timing and snapped timing
- `swing` in `[-1.0, 1.0]`: offsets odd subdivisions for groove feel

### Rubato / fluctuating tempo curves

Use `scale_tempo_curve([(time_s, bpm), ...])` to warp timeline timing dynamically,
as if drawing a tempo automation lane in a DAW.

- Control points define BPM over time (piecewise linear interpolation).
- Event timestamps are remapped by integrating the tempo curve.
- Pluck durations are remapped using warped start/end times, preserving musical phrasing under tempo flux.

When `song.meta.tempo_curve` is present in JSON, `render_osc_payloads()` applies it automatically.
Pass `apply_meta_tempo_curve=False` to render raw, unwarped timing.
