"""Record the AudioBox pickup while a song is sent.

Uses PipeWire (`pw-dump` + `pw-record`). With ``--record-audio``, one play
writes a dated folder under logs/ containing the song JSON, telemetry CSV,
48 kHz stereo WAV, and a left-channel spectrogram. The guitar pickup is the
left channel. A missing interface or a failed recorder does not stop playback.
"""

from __future__ import annotations

import json
import subprocess
import wave
from array import array
from datetime import datetime
from pathlib import Path

from control.telemetry import TelemetryRecorder

RATE = 48000
CHANNELS = 2
SAMPLE_FORMAT = "s16"
DEVICE_MATCH = "audiobox"
LOG_ROOT = Path(__file__).resolve().parents[1] / "logs"
SPECTROGRAM_FMAX_HZ = 4000


class AudioRecorder:
    """PipeWire capture that saves one song's WAV on stop."""

    def __init__(
        self,
        *,
        label: str = "play",
        log_dir: Path | str | None = None,
        wav_path: Path | str | None = None,
        device_match: str = DEVICE_MATCH,
    ) -> None:
        self.label = label
        self.device_match = device_match
        self.wav_path = Path(wav_path) if wav_path is not None else None
        if self.wav_path is not None:
            self.log_dir = self.wav_path.parent
        else:
            self.log_dir = Path(LOG_ROOT if log_dir is None else log_dir)
        self._proc: subprocess.Popen[bytes] | None = None

    def start(self) -> None:
        if self._proc is not None:
            return
        try:
            source = find_source(self.device_match)
        except Exception as exc:
            print(f"Audio recording skipped: {exc}")
            return
        if source is None:
            print(f"Audio recording skipped: no PipeWire source matching {self.device_match!r}")
            return

        self.log_dir.mkdir(parents=True, exist_ok=True)
        if self.wav_path is None:
            stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            self.wav_path = self.log_dir / f"{stamp}_{self.label}.wav"
        cmd = [
            "pw-record",
            "--target",
            source,
            "--rate",
            str(RATE),
            "--channels",
            str(CHANNELS),
            "--format",
            SAMPLE_FORMAT,
            str(self.wav_path),
        ]
        try:
            self._proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        except OSError as exc:
            print(f"Audio recording skipped: {exc}")
            self._proc = None
            self.wav_path = None

    def stop(self) -> Path | None:
        proc = self._proc
        self._proc = None
        if proc is None:
            return None
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
        err = b""
        if proc.stderr is not None:
            err = proc.stderr.read()
        path = self.wav_path
        if path is None or not path.is_file() or path.stat().st_size < 44:
            message = err.decode(errors="replace").strip()
            detail = f": {message}" if message else ""
            print(f"Audio recording failed{detail}")
            return None
        print(f"Saved audio recording: {path}")
        return path

    def __enter__(self) -> "AudioRecorder":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()


def find_source(device_match: str = DEVICE_MATCH) -> str | None:
    """PipeWire node name for the first Audio/Source matching ``device_match``."""
    raw = subprocess.check_output(["pw-dump"], text=True)
    needle = device_match.lower()
    for obj in json.loads(raw):
        if obj.get("type") != "PipeWire:Interface:Node":
            continue
        props = (obj.get("info") or {}).get("props") or {}
        if props.get("media.class") != "Audio/Source":
            continue
        name = str(props.get("node.name") or "")
        desc = str(props.get("node.description") or "")
        if needle in name.lower() or needle in desc.lower():
            return name
    return None


def capture_audio(
    *,
    label: str = "play",
    log_dir: Path | str | None = None,
    wav_path: Path | str | None = None,
) -> AudioRecorder:
    return AudioRecorder(label=label, log_dir=log_dir, wav_path=wav_path)


def new_session_dir(root: Path | str | None = None, when: datetime | None = None) -> Path:
    """Create ``logs/YYYY-MM-DD_HH-MM-SS`` for one recorded song."""
    parent = Path(LOG_ROOT if root is None else root)
    parent.mkdir(parents=True, exist_ok=True)
    moment = datetime.now() if when is None else when
    base = moment.strftime("%Y-%m-%d_%H-%M-%S")
    path = parent / base
    suffix = 1
    while True:
        try:
            path.mkdir()
            return path
        except FileExistsError:
            suffix += 1
            path = parent / f"{base}_{suffix}"


def write_spectrogram(wav_path: Path, png_path: Path) -> None:
    """Left-channel waveform and spectrogram for one take."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from scipy.signal import spectrogram

    with wave.open(str(wav_path), "rb") as handle:
        channels = handle.getnchannels()
        rate = handle.getframerate()
        raw = handle.readframes(handle.getnframes())
    samples = array("h")
    samples.frombytes(raw[: len(raw) - (len(raw) % (2 * channels))])
    left = np.asarray(samples[0::channels], dtype=np.float32) / 32768.0
    if left.size == 0:
        raise ValueError(f"no samples in {wav_path}")

    nperseg = min(2048, left.size)
    noverlap = min(1536, max(0, nperseg // 2))
    freqs, times, spectrum = spectrogram(
        left,
        fs=rate,
        window="hann",
        nperseg=nperseg,
        noverlap=noverlap,
        scaling="spectrum",
        mode="magnitude",
    )
    db = 20.0 * np.log10(np.maximum(spectrum, 1e-12))
    mask = freqs <= SPECTROGRAM_FMAX_HZ

    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True, gridspec_kw={"height_ratios": [1, 2.2]})
    axes[0].plot(np.arange(left.size) / rate, left, color="#1f4e79", lw=0.6)
    axes[0].set_ylabel("amplitude")
    axes[0].set_title("AudioBox left channel")
    axes[0].set_ylim(-1.05, 1.05)
    axes[0].grid(True, alpha=0.25)
    image = axes[1].pcolormesh(times, freqs[mask], db[mask], shading="auto", cmap="magma", vmin=-90, vmax=0)
    axes[1].set_ylabel("Hz")
    axes[1].set_xlabel("time (s)")
    axes[1].set_ylim(0, SPECTROGRAM_FMAX_HZ)
    colorbar = fig.colorbar(image, ax=axes[1], pad=0.01)
    colorbar.set_label("dB")
    fig.tight_layout()
    fig.savefig(png_path, dpi=140)
    plt.close(fig)


class PerformanceLog:
    """One dated folder: song.json, telemetry.csv, audio.wav, spectrogram.png."""

    def __init__(
        self,
        *,
        song: dict | None = None,
        label: str = "play",
        log_root: Path | str | None = None,
    ) -> None:
        self.song = song
        self.label = label
        self.log_root = log_root
        self.directory: Path | None = None
        self._audio: AudioRecorder | None = None
        self._telemetry: TelemetryRecorder | None = None

    def __enter__(self) -> "PerformanceLog":
        self.directory = new_session_dir(self.log_root)
        song_path = self.directory / "song.json"
        song_path.write_text(json.dumps(self.song if self.song is not None else {}, indent=2) + "\n", encoding="utf-8")
        self._telemetry = TelemetryRecorder(log_dir=self.directory, label=self.label, csv_name="telemetry.csv")
        self._telemetry.start()
        self._audio = AudioRecorder(label=self.label, wav_path=self.directory / "audio.wav")
        self._audio.start()
        print(f"Recording performance to {self.directory}")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        audio_path = self._audio.stop() if self._audio is not None else None
        if self._telemetry is not None:
            self._telemetry.stop()
        if self.directory is None:
            return
        if audio_path is not None:
            png_path = self.directory / "spectrogram.png"
            try:
                write_spectrogram(audio_path, png_path)
                print(f"Saved spectrogram: {png_path}")
            except Exception as exc:
                print(f"Spectrogram failed: {exc}")
        print(f"Saved performance log: {self.directory}")


def capture_performance(
    *,
    song: dict | None = None,
    label: str = "play",
    log_root: Path | str | None = None,
) -> PerformanceLog:
    return PerformanceLog(song=song, label=label, log_root=log_root)
