from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Iterable


PluckRow = list[float | int]


def _row_to_event(row: list | tuple, index: int) -> dict:
    if not isinstance(row, (list, tuple)):
        raise ValueError(f"pluck_message[{index}] must be a list/tuple; got {type(row).__name__}")
    if len(row) not in (5, 6):
        raise ValueError(
            f"pluck_message[{index}] must have 5 fields [note, duration_s, speed, slide, timestamp] "
            f"or 6 fields [note, duration_s, speed, slide, string_index, timestamp]; got {len(row)}"
        )

    note = int(row[0])
    duration_s = float(row[1])
    speed = float(row[2])
    slide = int(row[3])

    if len(row) == 5:
        timestamp = float(row[4])
        string_index = None
    else:
        string_index = int(row[4])
        timestamp = float(row[5])

    if duration_s <= 0:
        raise ValueError(f"pluck_message[{index}] duration_s must be > 0")
    if timestamp < 0:
        raise ValueError(f"pluck_message[{index}] timestamp must be >= 0")
    if slide not in (0, 1):
        raise ValueError(f"pluck_message[{index}] slide must be 0 or 1")
    if string_index is not None and string_index < 0:
        raise ValueError(f"pluck_message[{index}] string_index must be >= 0")

    event = {
        "note": note,
        "duration_s": duration_s,
        "speed": speed,
        "slide": slide,
        "timestamp": timestamp,
    }
    if string_index is not None:
        event["string_index"] = string_index
    return event


def pluck_message_to_song_dict(
    pluck_message: Iterable[list | tuple],
    *,
    song_name: str = "Pluck Message Song",
    key: str = "C",
    time_signature: str = "4/4",
    bpm: float = 120,
    track_name: str = "pluck_main",
) -> dict:
    rows = list(pluck_message)
    events = [_row_to_event(row, index) for index, row in enumerate(rows)]
    events.sort(key=lambda event: float(event["timestamp"]))

    return {
        "song": {
            "name": song_name,
            "meta": {
                "key": key,
                "time_signature": time_signature,
                "bpm": float(bpm),
            },
            "tracks": [
                {
                    "name": track_name,
                    "type": "pluck",
                    "events": events,
                }
            ],
        }
    }


def pluck_message_to_json(
    pluck_message: Iterable[list | tuple],
    *,
    song_name: str = "Pluck Message Song",
    key: str = "C",
    time_signature: str = "4/4",
    bpm: float = 120,
    track_name: str = "pluck_main",
    indent: int = 2,
) -> str:
    payload = pluck_message_to_song_dict(
        pluck_message,
        song_name=song_name,
        key=key,
        time_signature=time_signature,
        bpm=bpm,
        track_name=track_name,
    )
    return json.dumps(payload, indent=indent)


def _load_python_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(path.stem, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_pluck_message_from_python_file(path: str | Path, variable_name: str = "pluck_message") -> list:
    file_path = Path(path).resolve()
    module = _load_python_module(file_path)
    if not hasattr(module, variable_name):
        raise ValueError(f"{file_path} does not define variable {variable_name!r}")
    value = getattr(module, variable_name)
    if not isinstance(value, list):
        raise ValueError(f"{variable_name!r} in {file_path} must be a list")
    return value


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert pluck_message list-of-lists into GuitarBot arrangement JSON")
    parser.add_argument("--input", required=True, help="Path to Python file containing pluck_message variable")
    parser.add_argument("--var", default="pluck_message", help="Variable name in the input file (default: pluck_message)")
    parser.add_argument("--output", required=True, help="Output JSON path")
    parser.add_argument("--song-name", default="Pluck Message Song", help="song.name")
    parser.add_argument("--key", default="C", help="song.meta.key")
    parser.add_argument("--time-signature", default="4/4", help="song.meta.time_signature")
    parser.add_argument("--bpm", type=float, default=120.0, help="song.meta.bpm")
    parser.add_argument("--track-name", default="pluck_main", help="pluck track name")
    return parser


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()

    pluck_message = load_pluck_message_from_python_file(args.input, variable_name=args.var)
    json_text = pluck_message_to_json(
        pluck_message,
        song_name=args.song_name,
        key=args.key,
        time_signature=args.time_signature,
        bpm=args.bpm,
        track_name=args.track_name,
    )

    output_path = Path(args.output)
    output_path.write_text(json_text, encoding="utf-8")
    print(f"Wrote arrangement JSON: {output_path}")


if __name__ == "__main__":
    main()
