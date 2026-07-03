"""
Generate MicroController/LeftArm/Strikers/src/tune.h from tune.py values.

Usage:
  - python gen_tune_h.py   # runs generate_tune_h() with defaults

This keeps Arduino firmware constants in sync with the Python config without
needing runtime JSON or filesystems on the board.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent
DEFAULT_TUNE_PY = ROOT / "tune.py"
DEFAULT_HEADER_OUT = ROOT / "MicroController" / "LeftArm" / "Strikers" / "src" / "tune.h"


def _load_module_from_path(path: Path):
    spec = importlib.util.spec_from_file_location("_tune_module", str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


def _fmt_scalar(val: Any, ctype: str) -> str:
    if ctype == "float":
        return f"{float(val)}f"
    elif ctype in {"int", "uint32_t"}:
        return str(int(val))
    else:
        return str(val)


def _fmt_array(vals: Iterable[Any], ctype: str) -> str:
    parts = ( _fmt_scalar(v, ctype) for v in vals )
    return "{" + ", ".join(parts) + "}"


def generate_tune_h(tune_py_path: Path | str = DEFAULT_TUNE_PY,
                    header_out_path: Path | str = DEFAULT_HEADER_OUT) -> Path:
    """Generate the C header from tune.py variables and write it to disk.

    Returns the output path.
    """
    tune_py_path = Path(tune_py_path)
    header_out_path = Path(header_out_path)

    mod = _load_module_from_path(tune_py_path)

    # Map header names -> (python var name, c type, is_array)
    mapping = {
        "start_state_PICK": ("START_STATE_PICK", "float", True),
        "motor_id_PICK": ("MOTOR_ID_PICK", "int", True),
        "home_offset_SLIDE": ("HOME_OFFSET_SLIDE", "int", False),
        "home_offset_PRESS": ("HOME_OFFSET_PRESS", "int", False),
        "home_offset_PICK": ("HOME_OFFSET_PICK", "int", False),
        "current_control_SLIDE": ("CURRENT_CONTROL_SLIDE", "uint32_t", True),
        "current_control_PICK": ("CURRENT_CONTROL_PICK", "uint32_t", True),
        "current_control_PRESS": ("CURRENT_CONTROL_PRESS", "uint32_t", True),
        "pos_control_SLIDE": ("POS_CONTROL_SLIDE", "uint32_t", True),
        "pos_control_PICK": ("POS_CONTROL_PICK", "uint32_t", True),
        "pos_control_PRESS": ("POS_CONTROL_PRESS", "uint32_t", True),
        "mm_to_enc_conversion_factor": ("MM_TO_ENC_CONVERSION_FACTOR", "float", False),
    }

    lines: list[str] = []
    lines.append("#ifndef TUNE_H")
    lines.append("#define TUNE_H")
    lines.append("")
    lines.append("// Auto-generated from tune.py — DO NOT EDIT BY HAND")
    lines.append("// Run gen_tune_h.py or tune.py to regenerate.")
    lines.append("")

    for header_name, (py_name, ctype, is_array) in mapping.items():
        if not hasattr(mod, py_name):
            # Skip missing values but leave a breadcrumb comment.
            lines.append(f"// Missing in tune.py: {py_name} -> {header_name}")
            continue
        val = getattr(mod, py_name)
        if is_array:
            lines.append(f"const {ctype} {header_name}[{len(val)}] = {_fmt_array(val, ctype)};")
        else:
            lines.append(f"const {ctype} {header_name} = {_fmt_scalar(val, ctype)};")

    lines.append("")
    lines.append("#endif // TUNE_H")

    header_out_path.parent.mkdir(parents=True, exist_ok=True)
    header_out_path.write_text("\n".join(lines))
    return header_out_path


if __name__ == "__main__":
    out = generate_tune_h()
    print(f"Generated: {out}")
