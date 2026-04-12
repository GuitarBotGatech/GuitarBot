"""Test-song corpus for the shootout."""
from __future__ import annotations
import json
import random
from pathlib import Path
from .model import Note


def _beat_to_seconds(beat_str: str, bpm: float, subdiv_per_beat: int = 4) -> float:
    parts = beat_str.split(".")
    bar = int(parts[0]) - 1
    b = int(parts[1]) - 1 if len(parts) > 1 else 0
    s = int(parts[2]) - 1 if len(parts) > 2 else 0
    # assume 4/4 for simplicity; real parser would consult meta
    beats = bar * 4 + b + s / subdiv_per_beat
    return beats * 60.0 / bpm


def load_song_json(path: str | Path) -> tuple[str, list[Note]]:
    data = json.loads(Path(path).read_text())
    song = data["song"]
    bpm = song.get("meta", {}).get("bpm", 120)
    name = song.get("name", Path(path).stem)
    notes: list[Note] = []
    for track in song.get("tracks", []):
        if track.get("type") != "pluck":
            continue
        for ev in track.get("events", []):
            note_val = ev.get("note")
            if note_val is None or note_val < 6:
                # chord-pluck shorthand (0..5 = string index) — skip
                continue
            t = _beat_to_seconds(str(ev["beat"]), bpm)
            dur_b = ev.get("duration_b", 1)
            dur = dur_b * 60.0 / bpm
            slide = bool(ev.get("slide", 0))
            notes.append(Note(pitch=note_val, t=t, dur=dur, slide_in=slide))
    notes.sort(key=lambda n: n.t)
    return name, notes


def synth_chromatic() -> tuple[str, list[Note]]:
    notes = [Note(40 + i, i * 0.25, 0.25, slide_in=(i > 0)) for i in range(25)]
    return "synth_chromatic", notes


def synth_wide_leaps() -> tuple[str, list[Note]]:
    pitches = [40, 64, 43, 62, 45, 60, 47, 58, 48, 55]
    notes = [Note(p, i * 0.4, 0.4) for i, p in enumerate(pitches)]
    return "synth_wide_leaps", notes


def synth_tremolo_shared() -> tuple[str, list[Note]]:
    notes = [Note(52, i * 0.05, 0.05) for i in range(40)]
    return "synth_tremolo_shared", notes


def synth_slide_chain() -> tuple[str, list[Note]]:
    pitches = [40, 42, 44, 45, 47, 49, 50, 52]
    notes = [Note(p, i * 0.3, 0.3, slide_in=(i > 0)) for i, p in enumerate(pitches)]
    return "synth_slide_chain", notes


def synth_dense_chord_roll() -> tuple[str, list[Note]]:
    # 6 notes nearly simultaneously forcing multi-string use
    base_t = 0.0
    pitches = [40, 45, 50, 55, 59, 64]
    notes = []
    for bar in range(4):
        for i, p in enumerate(pitches):
            notes.append(Note(p + bar, base_t + bar * 1.2 + i * 0.02, 0.5))
    return "synth_dense_chord", notes


def random_midi(seed: int, length: int = 64) -> tuple[str, list[Note]]:
    rng = random.Random(seed)
    notes = []
    t = 0.0
    for _ in range(length):
        p = rng.randint(40, 68)
        notes.append(Note(p, t, 0.3, slide_in=rng.random() < 0.3))
        t += rng.expovariate(1 / 0.3)
    return f"random_{seed}", notes


def build_corpus(songs_dir: Path | None = None) -> list[tuple[str, list[Note]]]:
    corpus: list[tuple[str, list[Note]]] = [
        synth_chromatic(),
        synth_wide_leaps(),
        synth_tremolo_shared(),
        synth_slide_chain(),
        synth_dense_chord_roll(),
    ]
    for seed in range(5):
        corpus.append(random_midi(seed))
    if songs_dir and songs_dir.exists():
        for fname in ["smoke_on_the_water.json", "RandomNoodle.json", "string_theory.json"]:
            p = songs_dir / fname
            if p.exists():
                try:
                    name, notes = load_song_json(p)
                    if notes:
                        corpus.append((f"real_{name}", notes))
                except Exception as e:
                    print(f"[corpus] skip {fname}: {e}")
    return corpus
