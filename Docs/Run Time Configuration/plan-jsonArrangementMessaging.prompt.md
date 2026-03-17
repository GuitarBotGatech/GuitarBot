Plan: JSON Arrangement Intermediary

Define a canonical JSON “song arrangement” format as the user-facing layer, then map it to typed Python event objects and finally to OSC payloads. This keeps authoring tool-agnostic (Max/MSP, DAWs, generative systems), supports timeline editing (shift/copy/reverse/merge), and preserves current runtime compatibility. The JSON model bakes in musical context (`key`, `time_signature`, `bpm`) and separates time-based messages (`pluck`, `chord`, `midi`) from realtime control (`dyn`, `fret`, `rlfret`). Receiver-side compatibility stays intact while sender-side ergonomics improve immediately.

Steps
1. Specify a canonical JSON schema (`song`, `meta`, `tracks`, `clips`, `events`) under `Docs/Run Time Configuration`, with explicit event types for `pluck`, `chord`, `midi`.
2. Add typed Python dataclasses for arrangement + events in a new module under `parsing`, including validators for ranges/types and timestamp monotonicity per track.
3. Implement timeline transforms on typed objects: `shift_time`, `copy_range`, `paste_at`, `reverse_range`, `quantize`, `scale_tempo`.
4. Implement “track combinatrix” operations: horizontal composition (single-string lanes), vertical composition (cross-string stacks), deterministic merge/conflict rules.
5. Build JSON loader/serializer (`from_json`, `to_json`) and adapters to current wire payloads consumed by `OSC_Message_Receiver.py` and produced by `OSC_Message_Send.py`.
6. Keep `/Midi` object-first (`MidiEvent`) and serialize to nested event lists already supported by `OSC_Message_Receiver.py`; retain legacy fallback parsing.
7. Provide creator examples: one hand-authored JSON song, one algorithmically generated JSON song, both rendered to `/Chords` + `/Pluck` + `/Midi`.
8. Update runtime docs/help text to present JSON + OO flow as primary UX, raw list payloads as legacy/advanced.

Verification
- Round-trip tests: JSON → objects → JSON is stable.
- Rendering tests: objects → OSC payload matches existing parser expectations in `GuitarBotParser.py`.
- Transform tests: shift/copy/paste/reverse preserve ordering and timing invariants.
- Integration smoke: load JSON arrangement, send messages, confirm robot + MIDI sync.

Decisions
- UX intermediary: JSON (tool-agnostic and compositional).
- Authoring API: typed event objects over fluent builders.
- Compatibility: full backward compatibility during migration.
- Musical context: `key`, `time_signature`, `bpm` are first-class required metadata.

Immediate next implementation slice (MVP)
1. Define minimal JSON schema + example file.
2. Add dataclasses for `SongMeta`, `PluckEvent`, `ChordEvent`, `MidiEvent`, `Track`, `SongArrangement`.
3. Implement JSON load/validate + serialize-to-OSC for `/Chords`, `/Pluck`, `/Midi` only.
4. Add a small sender demo that loads JSON and transmits OSC.
5. Add focused tests for round-trip and render correctness.

Current status (March 2026)
- ✅ Minimal JSON schema doc added.
- ✅ Example arrangement JSON added.
- ✅ Core dataclasses + validators added.
- ✅ JSON load/render sender demo added.
- ✅ Initial tests added and passing.

Phase breakdown (implementation roadmap)

Phase 1 — Solidify MVP foundation
1. Add regression tests for interpolation-flag ambiguity and mixed int payloads.
2. Add stricter validation errors (event index + track name in exceptions).
3. Add deterministic serialization ordering for stable diffs.
4. Add `SongArrangement.from_json_path(...)/to_json_path(...)` convenience methods.

Acceptance criteria
- All arrangement and sequence-player tests pass.
- Invalid input reports clear, actionable messages (track + event index).
- `to_dict()` output is stable across repeated runs.

Phase 2 — DAW-esque timeline operations
1. Implement `shift_time(seconds)` at song/track/event scopes.
2. Implement `copy_range(start_s, end_s)` returning a clip object.
3. Implement `paste_at(clip, start_s)` with optional overwrite/merge behavior.
4. Implement `reverse_range(start_s, end_s)` preserving duration semantics.
5. Implement beat grid quantization using song BPM and time signature.
6. Add beat-wise event authoring via labels (`bar.beat[.sub]`), Ableton-style.

Acceptance criteria
- Clip copy/paste/reverse operations are fully unit-tested.
- Timestamps remain non-negative and sorted post-transform.
- Quantization aligns to expected beat subdivisions.
- Beat labels map predictably to seconds for the configured BPM and time signature.

Phase 3 — Track combinatrix (vertical + horizontal composition)
1. Introduce lane semantics (`string_lane`, `fx_lane`, `harmony_lane`).
2. Add `merge_tracks(...)` with deterministic collision rules.
3. Add vertical stack helper (same timestamp across multiple strings).
4. Add horizontal phrase helper (single string across a time span).

Acceptance criteria
- Merge behavior is deterministic and documented.
- Vertical/horizontal helpers produce valid OSC payloads.
- Conflicts produce warnings or policy-driven resolution.

Phase 4 — Runtime integration + compatibility hardening
1. Add alternate `OSC_Message_Send.py` path for JSON arrangement sending.
2. Add receiver-side optional normalization into typed events before queueing.
3. Keep legacy payload support; emit deprecation logs where applicable.
4. Add integration test fixture (JSON -> OSC -> parser compatibility).

Acceptance criteria
- Legacy senders still work unchanged.
- New JSON workflow works end-to-end.
- Deprecation warnings are clear and non-spammy.

Open design decisions to resolve before Phase 3
1. Clip identity model: immutable clips vs mutable references.
2. Track merge policy default: `append`, `overwrite`, or `blend`.
3. Quantization strategy for durations: preserve, clamp, or stretch.
4. MIDI interpolation ownership: arrangement layer vs sequence-player layer.

Immediate next sprint (recommended)
1. Add richer validation context in `parsing/song_arrangement.py`.
2. Implement `to_json_path()` and example round-trip script.
3. Add transform API skeleton (`shift_time`, `copy_range`, `paste_at`) + tests.
4. Wire optional `send_from_arrangement_json(...)` into `OSC_Message_Send.py`.
