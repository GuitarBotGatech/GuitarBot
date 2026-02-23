"""
rlfret_recording.py - Systematic audio data collection using /RLFret commands.

Records audio across all 3 playable strings (0, 2, 4) for many combinations
of fret position and pressing torque. Outputs WAV files + metadata CSV
compatible with retraining the HarmonicsClassifier CNN.

Two modes:
    1. Real-time labeling  — researcher annotates each recording live
    2. Offline labeling    — batch record everything, label later

Requirements:
    - arm_list_recieverNN.py must be running (UDP listener on 127.0.0.1:12000)
    - Audio interface connected (Scarlett preferred)
    - Robot powered and homed

Usage:
    # Real-time labeling mode
    python rlfret_recording.py --mode realtime

    # Offline (batch) recording mode
    python rlfret_recording.py --mode offline

    # Label a previous offline session
    python rlfret_recording.py --mode label --session <session_dir>

    # Custom grid
    python rlfret_recording.py --mode realtime --frets 4.0 5.0 7.0 --torques 100 300 500

    # Quick test: record one sample
    python rlfret_recording.py --mode test
"""

import argparse
import csv
import json
import socket
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import scipy.io.wavfile as wavfile
import scipy.signal as signal
import sounddevice as sd

# ─── OSC imports ──────────────────────────────────────────────────────────────
from pythonosc.osc_message_builder import OscMessageBuilder

# ─── Constants ────────────────────────────────────────────────────────────────

# Playable strings (strings that have pluckers)
PLAYABLE_STRINGS = [0, 2, 4]

# String names for display
STRING_NAMES = {0: "Low-E (string 0)", 2: "A (string 2)", 4: "D (string 4)"}

# Harmonic fret positions (known to produce natural harmonics)
HARMONIC_FRETS = [4.0, 5.0, 7.0]

# Default recording grid
DEFAULT_FRET_POSITIONS = [4.0, 4.1, 4.2, 5.0, 5.1, 5.2, 7.0, 7.1, 7.2, 9.0, 9.1, 9.2]

DEFAULT_TORQUES = [50, 60, 70, 80, 90, 100, 110, 120, 150, 300, 400, 500]

# Torque constraints (must match action_space.py)
TORQUE_SAFE_MIN = 16
TORQUE_MAX = 650
TORQUE_UNPRESSED = -650

# Audio recording parameters
SAMPLE_RATE = 44100
BIT_DEPTH = 24
RECORDING_DURATION = 4.0  # seconds — enough for pluck transient + ring-out

# Timing parameters
PRE_COMMAND_DELAY = 0.2     # seconds — start recording, then wait before sending command
POST_COMMAND_WAIT = 0.5     # seconds — extra wait after trajectory expected to finish
INTER_SAMPLE_PAUSE = 1.0   # seconds — pause between samples for string damping

# OSC target (arm_list_recieverNN.py listener)
OSC_IP = "127.0.0.1"
OSC_PORT = 12000

# CNN-compatible label categories (from HarmonicsClassifier/dataset_builder/config.py)
LABEL_HARMONIC = "harmonic"
LABEL_DEAD_NOTE = "dead_note"
LABEL_GENERAL_NOTE = "general_note"
LABEL_UNLABELED = "unlabeled"
VALID_LABELS = [LABEL_HARMONIC, LABEL_DEAD_NOTE, LABEL_GENERAL_NOTE]

# Metadata CSV columns
METADATA_COLUMNS = [
    "filename",
    "source_audio",
    "label_category",
    "string_idx",
    "fret_position",
    "torque",
    "onset_sec",
    "offset_sec",
    "duration_sec",
    "sample_rate",
    "recording_timestamp",
    "session_name",
    "is_harmonic_fret",
    "notes",
]


class RLFretRecorder:
    """
    Systematic audio recorder that drives the GuitarBot via /RLFret messages
    and captures the resulting sounds for CNN training data.
    """

    def __init__(
        self,
        output_dir: Optional[str] = None,
        session_name: Optional[str] = None,
        sample_rate: int = SAMPLE_RATE,
        bit_depth: int = BIT_DEPTH,
        recording_duration: float = RECORDING_DURATION,
        pluck_velocity: int = 1,
    ):
        self.sample_rate = sample_rate
        self.bit_depth = bit_depth
        self.recording_duration = recording_duration
        self.pluck_velocity = pluck_velocity

        # Bit-depth configuration
        if bit_depth == 16:
            self.dtype = np.int16
            self.scale = 32767
        elif bit_depth == 24:
            self.dtype = np.int32  # 24-bit stored in 32-bit container
            self.scale = 8388607
        else:
            self.dtype = np.int32
            self.scale = 2147483647

        # Output directory
        if output_dir is None:
            repo_root = Path(__file__).parent.parent
            output_dir = repo_root.parent / "GuitarBot_Data" / "rlfret_recordings"

        self.output_dir = Path(output_dir)
        self.session_name = session_name or datetime.now().strftime("%Y%m%d_%H%M%S")

        date_str = datetime.now().strftime("%Y_%m_%d")
        self.session_dir = self.output_dir / date_str / self.session_name
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # Audio subdirectory
        self.audio_dir = self.session_dir / "audio"
        self.audio_dir.mkdir(exist_ok=True)

        # Metadata CSV path
        self.metadata_path = self.session_dir / "metadata.csv"

        # Recording counters
        self.recordings_completed = 0
        self.recordings_skipped = 0

        # OSC socket (raw UDP — matches arm_list_recieverNN.py's listener)
        self.osc_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.osc_target = (OSC_IP, OSC_PORT)

        # Audio device
        self.selected_input_device = None
        self.selected_input_device_name = None

        # Initialize metadata CSV
        self._init_metadata_csv()

        # Print session info
        self._print_banner()

        # Configure audio input
        self._configure_audio_device()

    # ── Setup helpers ─────────────────────────────────────────────────────

    def _print_banner(self):
        print(f"\n{'=' * 70}")
        print(f"  RLFRET SYSTEMATIC RECORDING SESSION")
        print(f"{'=' * 70}")
        print(f"Session:    {self.session_name}")
        print(f"Output:     {self.session_dir}")
        print(f"Audio:      {self.sample_rate} Hz, {self.bit_depth}-bit")
        print(f"Duration:   {self.recording_duration}s per sample")
        print(f"Pluck vel:  {self.pluck_velocity}")
        print(f"OSC target: {OSC_IP}:{OSC_PORT}")
        print(f"{'=' * 70}\n")

    def _init_metadata_csv(self):
        """Create the metadata CSV with headers if it doesn't exist."""
        if not self.metadata_path.exists():
            with open(self.metadata_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=METADATA_COLUMNS)
                writer.writeheader()

    def _configure_audio_device(self, preferred: str = "Scarlett"):
        """Select audio input device, preferring Scarlett interface."""
        devices = sd.query_devices()
        preferred_l = preferred.lower()

        for idx, dev in enumerate(devices):
            name = dev.get("name", "")
            max_in = dev.get("max_input_channels", 0)
            if max_in > 0 and preferred_l in name.lower():
                sd.default.device = (
                    idx,
                    sd.default.device[1]
                    if isinstance(sd.default.device, tuple)
                    else None,
                )
                sd.default.samplerate = self.sample_rate
                self.selected_input_device = idx
                self.selected_input_device_name = name
                print(f"Audio input: [{idx}] {name}  (auto-selected)\n")
                return

        # Fallback: list devices and prompt
        print(f"No '{preferred}' device found. Available inputs:")
        input_indices = []
        for idx, dev in enumerate(devices):
            name = dev.get("name", "")
            max_in = dev.get("max_input_channels", 0)
            if max_in > 0:
                input_indices.append(idx)
                print(f"  [{idx}] {name}  ({max_in} ch)")

        if not input_indices:
            print("  (none — using system default)\n")
            return

        while True:
            sel = input("\nDevice index (Enter for default): ").strip()
            if sel == "":
                print("Using system default.\n")
                return
            try:
                sel_idx = int(sel)
                if sel_idx in input_indices:
                    dev = devices[sel_idx]
                    sd.default.device = (
                        sel_idx,
                        sd.default.device[1]
                        if isinstance(sd.default.device, tuple)
                        else None,
                    )
                    sd.default.samplerate = self.sample_rate
                    self.selected_input_device = sel_idx
                    self.selected_input_device_name = dev.get("name", "")
                    print(f"Selected: [{sel_idx}] {self.selected_input_device_name}\n")
                    return
                print("Invalid index.")
            except ValueError:
                print("Enter a number.")

    # ── OSC Communication ─────────────────────────────────────────────────

    def send_rlfret(
        self,
        string_idx: int,
        fret_position: float,
        torque: float,
        pluck_velocity: Optional[int] = None,
    ):
        """
        Send an /RLFret OSC message to arm_list_recieverNN.py.

        Args:
            string_idx: 0, 2, or 4 (playable strings)
            fret_position: 0.0 – 9.0 fractional frets
            torque: pressing force (TORQUE_SAFE_MIN – TORQUE_MAX)
            pluck_velocity: optional pluck velocity (default: self.pluck_velocity)
        """
        if pluck_velocity is None:
            pluck_velocity = self.pluck_velocity

        builder = OscMessageBuilder(address="/RLFret")
        builder.add_arg(int(string_idx))
        builder.add_arg(float(fret_position))
        builder.add_arg(float(torque))
        msg = builder.build()

        self.osc_sock.sendto(msg.dgram, self.osc_target)

    def send_unpress(self, string_idx: int):
        """Release the presser for a string (torque = TORQUE_UNPRESSED)."""
        builder = OscMessageBuilder(address="/RLFret")
        builder.add_arg(int(string_idx))
        builder.add_arg(float(0.0))
        builder.add_arg(float(TORQUE_UNPRESSED))
        # No pluck — just unpress
        msg = builder.build()
        self.osc_sock.sendto(msg.dgram, self.osc_target)

    # ── Audio Recording ───────────────────────────────────────────────────

    def record_audio(self) -> Optional[np.ndarray]:
        """
        Record a single audio clip.

        Returns:
            float32 audio array (range -1..1), or None on failure.
        """
        try:
            num_samples = int(self.recording_duration * self.sample_rate)
            audio = sd.rec(num_samples, samplerate=self.sample_rate,
                           channels=1, dtype="float32")
            sd.wait()
            return audio.flatten()
        except Exception as e:
            print(f"  [ERROR] Recording failed: {e}")
            return None

    def record_with_command(
        self,
        string_idx: int,
        fret_position: float,
        torque: float,
    ) -> Optional[np.ndarray]:
        """
        Start recording, send /RLFret command, wait for recording to finish.

        This captures the full trajectory: silence → mechanical movement →
        pluck transient → ring-out.
        """
        # Start async recording
        num_samples = int(self.recording_duration * self.sample_rate)
        try:
            audio = sd.rec(num_samples, samplerate=self.sample_rate,
                           channels=1, dtype="float32")
        except Exception as e:
            print(f"  [ERROR] Could not start recording: {e}")
            return None

        # Brief delay so recording stream is stable
        time.sleep(PRE_COMMAND_DELAY)

        # Send the /RLFret command
        self.send_rlfret(string_idx, fret_position, torque)

        # Wait for recording to complete
        sd.wait()

        return audio.flatten()

    # ── File I/O ──────────────────────────────────────────────────────────

    def _make_filename(
        self, string_idx: int, fret_position: float, torque: float
    ) -> str:
        """Generate a descriptive WAV filename."""
        ts = datetime.now().strftime("%H%M%S_%f")[:13]  # HH:MM:SS_mmm
        fret_str = f"{fret_position:.1f}".replace(".", "p")
        torque_str = f"{int(torque)}"
        return f"GB_RLFret_s{string_idx}_f{fret_str}_t{torque_str}_{ts}.wav"

    def save_wav(self, audio: np.ndarray, filename: str) -> Optional[Path]:
        """Save float32 audio to WAV at configured bit depth."""
        filepath = self.audio_dir / filename
        try:
            audio_int = np.clip(audio * self.scale, -self.scale - 1, self.scale).astype(
                self.dtype
            )
            wavfile.write(str(filepath), self.sample_rate, audio_int)
            if filepath.exists():
                return filepath
        except Exception as e:
            print(f"  [ERROR] Save failed: {e}")
        return None

    def append_metadata(self, row: dict):
        """Append a single row to the metadata CSV."""
        with open(self.metadata_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=METADATA_COLUMNS)
            writer.writerow(row)

    def _build_metadata_row(
        self,
        filename: str,
        string_idx: int,
        fret_position: float,
        torque: float,
        label: str = LABEL_UNLABELED,
        notes: str = "",
    ) -> dict:
        return {
            "filename": filename,
            "source_audio": str(self.audio_dir / filename),
            "label_category": label,
            "string_idx": string_idx,
            "fret_position": fret_position,
            "torque": torque,
            "onset_sec": 0.0,
            "offset_sec": self.recording_duration,
            "duration_sec": self.recording_duration,
            "sample_rate": self.sample_rate,
            "recording_timestamp": datetime.now().isoformat(),
            "session_name": self.session_name,
            "is_harmonic_fret": fret_position in HARMONIC_FRETS,
            "notes": notes,
        }

    # ── Visualization ─────────────────────────────────────────────────────

    def show_waveform_and_spectrogram(self, audio: np.ndarray, title: str = ""):
        """Display waveform + spectrogram side by side for researcher review."""
        fig, axes = plt.subplots(2, 1, figsize=(12, 7))

        # Waveform
        t = np.linspace(0, len(audio) / self.sample_rate, len(audio))
        axes[0].plot(t, audio, linewidth=0.4, color="steelblue")
        axes[0].set_ylabel("Amplitude")
        axes[0].set_xlabel("Time (s)")
        axes[0].set_title(f"Waveform — {title}")
        axes[0].set_xlim(0, t[-1])
        peak = np.max(np.abs(audio))
        axes[0].set_ylim(-max(peak * 1.1, 0.01), max(peak * 1.1, 0.01))

        # Spectrogram
        freqs, times, Sxx = signal.spectrogram(
            audio, fs=self.sample_rate, nperseg=2048, noverlap=1536
        )
        axes[1].pcolormesh(
            times, freqs, 10 * np.log10(Sxx + 1e-10),
            shading="gouraud", cmap="viridis",
        )
        axes[1].set_ylabel("Frequency (Hz)")
        axes[1].set_xlabel("Time (s)")
        axes[1].set_title("Spectrogram")
        axes[1].set_ylim(0, min(5000, self.sample_rate / 2))

        plt.tight_layout()
        plt.show(block=True)
        plt.close(fig)

    # ── Interactive labeling prompt ───────────────────────────────────────

    @staticmethod
    def prompt_label() -> str:
        """
        Ask researcher for a label.

        Returns one of: harmonic, dead_note, general_note, or 'skip'.
        """
        print("\n  Label this recording:")
        print("    [1] harmonic      — natural harmonic tone")
        print("    [2] dead_note     — muted / buzzing / dead sound")
        print("    [3] general_note  — normal fretted note")
        print("    [s] skip          — discard and re-record")
        print("    [q] quit          — stop session")

        while True:
            choice = input("  > ").strip().lower()
            if choice == "1":
                return LABEL_HARMONIC
            elif choice == "2":
                return LABEL_DEAD_NOTE
            elif choice == "3":
                return LABEL_GENERAL_NOTE
            elif choice == "s":
                return "skip"
            elif choice == "q":
                raise KeyboardInterrupt
            else:
                print("  Invalid — enter 1, 2, 3, s, or q.")

    # ── Recording modes ───────────────────────────────────────────────────

    def run_realtime_session(
        self,
        strings: List[int],
        fret_positions: List[float],
        torques: List[float],
    ):
        """
        Real-time labeling mode.

        For each (string, fret, torque) combination:
          1. Send /RLFret + record audio
          2. Show waveform & spectrogram
          3. Researcher labels: harmonic / dead_note / general_note / skip
          4. Save WAV + metadata row
        """
        grid = [
            (s, f, t) for s in strings for f in fret_positions for t in torques
        ]
        total = len(grid)

        print(f"\n{'=' * 70}")
        print(f"  REAL-TIME LABELING MODE")
        print(f"{'=' * 70}")
        print(f"  Grid: {len(strings)} strings × {len(fret_positions)} frets"
              f" × {len(torques)} torques = {total} samples")
        print(f"  Strings:  {strings}")
        print(f"  Frets:    {fret_positions}")
        print(f"  Torques:  {torques}")
        print(f"\n  Instructions:")
        print(f"    - Each sample: robot plays → you see waveform → you label")
        print(f"    - Press Enter to begin each recording")
        print(f"    - Label: 1=harmonic  2=dead_note  3=general_note  s=skip  q=quit")
        print(f"{'=' * 70}\n")

        input("Press ENTER to start the session...")

        try:
            for idx, (string_idx, fret, torque) in enumerate(grid):
                self._realtime_single(idx, total, string_idx, fret, torque)

            self._print_summary()

        except KeyboardInterrupt:
            print(f"\n\n  Session interrupted after {self.recordings_completed} recordings.")
            self._print_summary()

    def _realtime_single(
        self, idx: int, total: int,
        string_idx: int, fret: float, torque: float,
    ):
        """Record + label a single sample in real-time mode."""
        attempt = 0
        while True:
            attempt += 1
            print(f"\n{'─' * 70}")
            print(f"  [{idx + 1}/{total}]  "
                  f"String {string_idx} ({STRING_NAMES.get(string_idx, '?')})  |  "
                  f"Fret {fret:.1f}  |  Torque {torque}")
            if fret in HARMONIC_FRETS:
                print(f"  ★ Known harmonic fret position")
            if attempt > 1:
                print(f"  (attempt {attempt})")
            print(f"{'─' * 70}")

            input("  Press ENTER to record...")

            # Record
            print(f"  Recording {self.recording_duration}s ...")
            audio = self.record_with_command(string_idx, fret, torque)

            if audio is None:
                print("  Recording failed — retrying.")
                continue

            peak = np.max(np.abs(audio))
            print(f"  Done.  Peak level: {peak:.4f}")

            # Show plots
            title = (f"String {string_idx} | Fret {fret:.1f} | "
                     f"Torque {torque}")
            self.show_waveform_and_spectrogram(audio, title)

            # Label
            label = self.prompt_label()
            if label == "skip":
                print("  Skipped — retrying this sample.")
                self.recordings_skipped += 1
                continue

            # Save
            filename = self._make_filename(string_idx, fret, torque)
            filepath = self.save_wav(audio, filename)
            if filepath is None:
                print("  Save failed — retrying.")
                continue

            row = self._build_metadata_row(
                filename, string_idx, fret, torque, label=label,
            )
            self.append_metadata(row)
            self.recordings_completed += 1
            print(f"  Saved: {filename}  label={label}  "
                  f"({self.recordings_completed} total)")

            # Pause for string damping
            time.sleep(INTER_SAMPLE_PAUSE)
            break

    def run_offline_session(
        self,
        strings: List[int],
        fret_positions: List[float],
        torques: List[float],
        repetitions: int = 1,
    ):
        """
        Offline (batch) recording mode.

        Iterates the full grid automatically. All recordings saved as
        'unlabeled' — use run_labeling_session() afterwards to annotate.
        """
        grid = [
            (s, f, t, rep)
            for s in strings
            for f in fret_positions
            for t in torques
            for rep in range(1, repetitions + 1)
        ]
        total = len(grid)

        print(f"\n{'=' * 70}")
        print(f"  OFFLINE (BATCH) RECORDING MODE")
        print(f"{'=' * 70}")
        print(f"  Grid: {len(strings)} strings × {len(fret_positions)} frets"
              f" × {len(torques)} torques × {repetitions} reps = {total} samples")
        print(f"  Estimated time: ~{total * (self.recording_duration + INTER_SAMPLE_PAUSE + 1):.0f}s"
              f"  ({total * (self.recording_duration + INTER_SAMPLE_PAUSE + 1) / 60:.1f} min)")
        print(f"\n  All recordings will be saved as '{LABEL_UNLABELED}'.")
        print(f"  Use  --mode label --session {self.session_dir}")
        print(f"  to annotate them later.")
        print(f"{'=' * 70}\n")

        confirm = input("Start batch recording? (y/n): ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            return

        try:
            for idx, (string_idx, fret, torque, rep) in enumerate(grid):
                pct = (idx + 1) / total * 100
                print(f"\n  [{idx + 1}/{total}] ({pct:.0f}%)  "
                      f"s={string_idx}  f={fret:.1f}  t={torque}  rep={rep}")

                audio = self.record_with_command(string_idx, fret, torque)

                if audio is None:
                    print(f"    FAILED — skipping")
                    self.recordings_skipped += 1
                    time.sleep(INTER_SAMPLE_PAUSE)
                    continue

                peak = np.max(np.abs(audio))
                print(f"    peak={peak:.4f}", end="")

                filename = self._make_filename(string_idx, fret, torque)
                filepath = self.save_wav(audio, filename)
                if filepath is None:
                    print(f"  SAVE FAILED")
                    self.recordings_skipped += 1
                    time.sleep(INTER_SAMPLE_PAUSE)
                    continue

                row = self._build_metadata_row(
                    filename, string_idx, fret, torque,
                    label=LABEL_UNLABELED,
                    notes=f"rep={rep}",
                )
                self.append_metadata(row)
                self.recordings_completed += 1
                print(f"  saved ({self.recordings_completed} total)")

                time.sleep(INTER_SAMPLE_PAUSE)

        except KeyboardInterrupt:
            print(f"\n\n  Batch interrupted after {self.recordings_completed} recordings.")

        self._print_summary()

    def run_labeling_session(self, session_dir: Optional[str] = None):
        """
        Offline labeling mode — load an existing session and label
        all unlabeled recordings by playing them back.

        Args:
            session_dir: Path to session directory (must contain metadata.csv
                         and audio/ subdirectory). If None, uses current session.
        """
        import pandas as pd

        if session_dir:
            meta_path = Path(session_dir) / "metadata.csv"
        else:
            meta_path = self.metadata_path

        if not meta_path.exists():
            print(f"No metadata.csv found at {meta_path}")
            return

        df = pd.read_csv(meta_path)
        unlabeled = df[df["label_category"] == LABEL_UNLABELED]

        if unlabeled.empty:
            print("All recordings are already labeled!")
            self._print_label_distribution(df)
            return

        total = len(unlabeled)
        labeled_count = 0

        print(f"\n{'=' * 70}")
        print(f"  OFFLINE LABELING MODE")
        print(f"{'=' * 70}")
        print(f"  Session: {meta_path.parent}")
        print(f"  Total recordings: {len(df)}")
        print(f"  Already labeled:  {len(df) - total}")
        print(f"  Unlabeled:        {total}")
        print(f"\n  For each recording you will see waveform + spectrogram")
        print(f"  and hear the audio playback.")
        print(f"  Label: 1=harmonic  2=dead_note  3=general_note  s=skip  q=quit")
        print(f"{'=' * 70}\n")

        input("Press ENTER to start labeling...")

        try:
            for i, (row_idx, row) in enumerate(unlabeled.iterrows()):
                audio_path = Path(row["source_audio"])
                if not audio_path.exists():
                    print(f"  [{i+1}/{total}] MISSING: {audio_path}")
                    continue

                # Load audio
                sr, audio_int = wavfile.read(str(audio_path))
                audio = audio_int.astype(np.float32)
                if audio.dtype == np.int16:
                    audio = audio_int.astype(np.float32) / 32767.0
                elif audio.dtype == np.int32:
                    audio = audio_int.astype(np.float32) / 2147483647.0
                else:
                    # Normalize
                    amax = np.max(np.abs(audio))
                    if amax > 0:
                        audio /= amax

                fret = row["fret_position"]
                torque = row["torque"]
                string_idx = row["string_idx"]

                print(f"\n{'─' * 70}")
                print(f"  [{i+1}/{total}]  "
                      f"String {int(string_idx)}  |  Fret {fret:.1f}  |  Torque {int(torque)}")
                print(f"  File: {row['filename']}")
                if fret in HARMONIC_FRETS:
                    print(f"  ★ Known harmonic fret position")
                print(f"{'─' * 70}")

                # Play audio
                try:
                    print("  Playing audio...")
                    sd.play(audio, samplerate=sr)
                except Exception as e:
                    print(f"  (playback error: {e})")

                # Show plots
                title = f"String {int(string_idx)} | Fret {fret:.1f} | Torque {int(torque)}"
                self.show_waveform_and_spectrogram(audio, title)

                # Stop playback
                try:
                    sd.stop()
                except Exception:
                    pass

                # Label
                label = self.prompt_label()
                if label == "skip":
                    print("  Skipped.")
                    continue

                # Update the DataFrame
                df.at[row_idx, "label_category"] = label
                labeled_count += 1
                print(f"  Labeled: {label}  ({labeled_count}/{total})")

            # Save updated metadata
            df.to_csv(meta_path, index=False)
            print(f"\n  Metadata saved to {meta_path}")
            print(f"  Labeled {labeled_count} recordings this session.")
            self._print_label_distribution(df)

        except KeyboardInterrupt:
            # Save progress even if interrupted
            df.to_csv(meta_path, index=False)
            print(f"\n\n  Labeling interrupted. Progress saved ({labeled_count} labeled).")
            self._print_label_distribution(df)

    # ── Export for CNN ────────────────────────────────────────────────────

    def export_for_cnn(self, session_dir: Optional[str] = None):
        """
        Export labeled data in a format ready for CNN training.

        Creates a cnn_metadata.csv with columns matching what
        HarmonicsClassifier/train_cnn.py expects:
            source_audio, onset_sec, offset_sec, duration_sec, label_category

        Only labeled (non-'unlabeled') rows are exported.
        """
        import pandas as pd

        if session_dir:
            meta_path = Path(session_dir) / "metadata.csv"
        else:
            meta_path = self.metadata_path

        df = pd.read_csv(meta_path)
        labeled = df[df["label_category"] != LABEL_UNLABELED].copy()

        if labeled.empty:
            print("No labeled recordings to export.")
            return None

        # CNN expects these columns
        cnn_df = labeled[["source_audio", "onset_sec", "offset_sec",
                          "duration_sec", "label_category"]].copy()

        out_path = meta_path.parent / "cnn_metadata.csv"
        cnn_df.to_csv(out_path, index=False)

        print(f"\n  Exported {len(cnn_df)} labeled samples to {out_path}")
        self._print_label_distribution(labeled)
        return out_path

    # ── Helpers ───────────────────────────────────────────────────────────

    def _print_summary(self):
        print(f"\n{'=' * 70}")
        print(f"  SESSION SUMMARY")
        print(f"{'=' * 70}")
        print(f"  Completed:  {self.recordings_completed}")
        print(f"  Skipped:    {self.recordings_skipped}")
        print(f"  Output:     {self.session_dir}")
        print(f"  Metadata:   {self.metadata_path}")
        print(f"{'=' * 70}\n")

    @staticmethod
    def _print_label_distribution(df):
        """Print label distribution from a DataFrame."""
        print("\n  Label distribution:")
        for label in [LABEL_HARMONIC, LABEL_DEAD_NOTE, LABEL_GENERAL_NOTE, LABEL_UNLABELED]:
            count = (df["label_category"] == label).sum()
            if count > 0:
                pct = count / len(df) * 100
                print(f"    {label:15s}: {count:4d}  ({pct:.1f}%)")
        print()

    def run_test(self, string_idx: int = 0, fret: float = 5.0, torque: float = 200.0):
        """Quick test: record one sample and display it (no saving)."""
        print(f"\n{'=' * 70}")
        print(f"  TEST MODE  —  string={string_idx}  fret={fret}  torque={torque}")
        print(f"{'=' * 70}\n")

        input("Press ENTER to record a test sample...")

        audio = self.record_with_command(string_idx, fret, torque)
        if audio is None:
            print("Test recording failed.")
            return

        peak = np.max(np.abs(audio))
        rms = np.sqrt(np.mean(audio ** 2))
        print(f"  Peak: {peak:.4f}   RMS: {rms:.6f}")

        title = f"TEST — String {string_idx} | Fret {fret:.1f} | Torque {torque}"
        self.show_waveform_and_spectrogram(audio, title)
        print("Test complete.\n")


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def parse_args():
    p = argparse.ArgumentParser(
        description="Systematic audio recording with /RLFret commands.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Real-time labeling with default grid
  python rlfret_recording.py --mode realtime

  # Offline batch recording
  python rlfret_recording.py --mode offline

  # Offline batch with custom grid
  python rlfret_recording.py --mode offline --frets 4.0 5.0 7.0 --torques 100 300 500

  # Label a previous offline session
  python rlfret_recording.py --mode label --session /path/to/session_dir

  # Export labeled data for CNN training
  python rlfret_recording.py --mode export --session /path/to/session_dir

  # Quick test recording
  python rlfret_recording.py --mode test
        """,
    )

    p.add_argument(
        "--mode",
        choices=["realtime", "offline", "label", "export", "test"],
        default="realtime",
        help="Recording mode (default: realtime)",
    )
    p.add_argument(
        "--session",
        type=str,
        default=None,
        help="Path to existing session directory (for --mode label/export)",
    )
    p.add_argument(
        "--strings",
        type=int,
        nargs="+",
        default=PLAYABLE_STRINGS,
        help=f"String indices to record (default: {PLAYABLE_STRINGS})",
    )
    p.add_argument(
        "--frets",
        type=float,
        nargs="+",
        default=DEFAULT_FRET_POSITIONS,
        help="Fret positions to record (default: 0.0 to 9.0 in 0.5 steps)",
    )
    p.add_argument(
        "--torques",
        type=float,
        nargs="+",
        default=DEFAULT_TORQUES,
        help=f"Torque values to record (default: {DEFAULT_TORQUES})",
    )
    p.add_argument(
        "--reps",
        type=int,
        default=1,
        help="Repetitions per grid point (offline mode, default: 1)",
    )
    p.add_argument(
        "--duration",
        type=float,
        default=RECORDING_DURATION,
        help=f"Recording duration in seconds (default: {RECORDING_DURATION})",
    )
    p.add_argument(
        "--pluck-velocity",
        type=int,
        default=1,
        help="Pluck velocity (default: 1)",
    )
    p.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory (default: ../GuitarBot_Data/rlfret_recordings/)",
    )
    p.add_argument(
        "--session-name",
        type=str,
        default=None,
        help="Session name (default: timestamp)",
    )

    return p.parse_args()


def main():
    args = parse_args()

    # For label/export modes, we can skip recorder setup if we have a session
    if args.mode in ("label", "export") and args.session:
        recorder = RLFretRecorder(
            output_dir=str(Path(args.session).parent.parent),
            session_name=Path(args.session).name,
            recording_duration=args.duration,
        )
        if args.mode == "label":
            recorder.run_labeling_session(args.session)
        else:
            recorder.export_for_cnn(args.session)
        return

    # Create recorder
    recorder = RLFretRecorder(
        output_dir=args.output_dir,
        session_name=args.session_name,
        recording_duration=args.duration,
        pluck_velocity=args.pluck_velocity,
    )

    if args.mode == "test":
        recorder.run_test()

    elif args.mode == "realtime":
        recorder.run_realtime_session(
            strings=args.strings,
            fret_positions=args.frets,
            torques=args.torques,
        )

    elif args.mode == "offline":
        recorder.run_offline_session(
            strings=args.strings,
            fret_positions=args.frets,
            torques=args.torques,
            repetitions=args.reps,
        )

    elif args.mode == "label":
        # label without --session uses current session
        recorder.run_labeling_session()

    elif args.mode == "export":
        recorder.export_for_cnn()


if __name__ == "__main__":
    main()
