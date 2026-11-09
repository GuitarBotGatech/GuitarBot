"""UDP listener for OpenCR motor encoder telemetry.

OpenCR sends little-endian float32[18] encoder ticks to TELEM_PORT at ~50 Hz.
Capture around a play/reset send and write CSV + npy under logs/telemetry/.
"""

from __future__ import annotations

import csv
import socket
import struct
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

NUM_MOTORS = 18
TELEM_PORT = 8889
PACKET_BYTES = NUM_MOTORS * 4
PACKET_FMT = f"<{NUM_MOTORS}f"
DEFAULT_LOG_DIR = Path(__file__).resolve().parents[1] / "logs" / "telemetry"
DRAIN_S = 0.5


class TelemetryRecorder:
    """Background UDP listener that saves one run's encoder samples on stop."""

    def __init__(
        self,
        *,
        port: int = TELEM_PORT,
        log_dir: Path | str | None = None,
        label: str = "run",
    ) -> None:
        self.port = int(port)
        self.log_dir = Path(DEFAULT_LOG_DIR if log_dir is None else log_dir)
        self.label = label
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._rows: list[tuple[float, ...]] = []
        self._lock = threading.Lock()
        self.csv_path: Path | None = None
        self.npy_path: Path | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._rows = []
        self._thread = threading.Thread(
            target=self._listen,
            name="guitarbot-telemetry",
            daemon=True,
        )
        self._thread.start()

    def stop(self, *, drain_s: float = DRAIN_S) -> Path | None:
        if self._thread is None:
            return None
        if drain_s > 0:
            time.sleep(drain_s)
        self._stop.set()
        self._thread.join(timeout=2.0)
        self._thread = None
        return self._save()

    def __enter__(self) -> "TelemetryRecorder":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        path = self.stop()
        if path is not None:
            print(f"Saved motor telemetry: {path}")

    def _listen(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", self.port))
        sock.settimeout(0.2)
        try:
            while not self._stop.is_set():
                try:
                    data, _addr = sock.recvfrom(1024)
                except socket.timeout:
                    continue
                except OSError:
                    break
                if len(data) != PACKET_BYTES:
                    continue
                positions = struct.unpack(PACKET_FMT, data)
                row = (time.time(),) + positions
                with self._lock:
                    self._rows.append(row)
        finally:
            sock.close()

    def _save(self) -> Path | None:
        with self._lock:
            rows = list(self._rows)
        if not rows:
            print("No motor telemetry packets received.")
            return None

        self.log_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        stem = f"{stamp}_{self.label}"
        self.csv_path = self.log_dir / f"{stem}.csv"
        self.npy_path = self.log_dir / f"{stem}.npy"

        header = ["t_unix"] + [f"m{i}" for i in range(1, NUM_MOTORS + 1)]
        with self.csv_path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)

        arr = np.asarray(rows, dtype=np.float64)
        np.save(self.npy_path, arr)
        print(f"Recorded {len(rows)} telemetry samples -> {self.csv_path}")
        return self.csv_path


def capture_telemetry(*, label: str = "run", log_dir: Path | str | None = None) -> TelemetryRecorder:
    return TelemetryRecorder(label=label, log_dir=log_dir)
