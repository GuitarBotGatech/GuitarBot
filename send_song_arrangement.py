from __future__ import annotations

import argparse
import base64
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from pythonosc.udp_client import SimpleUDPClient

from parsing.song_arrangement import SongArrangement


UDP_IP = "127.0.0.1"
UDP_PORT = 12000
UPLOAD_HOST = "127.0.0.1"
UPLOAD_PORT = 8765
MAX_EVENTS_PER_OSC_PACKET = 48
CC7_MIN_INTERVAL_S = 0.08


def _chunked(items: list[list], chunk_size: int) -> list[list[list]]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    return [items[index:index + chunk_size] for index in range(0, len(items), chunk_size)]


def _is_cc7_row(row: list) -> bool:
    if not isinstance(row, list) or len(row) < 3:
        return False
    if str(row[0]) != "/cc":
        return False
    try:
        cc = int(float(row[1]))
    except (TypeError, ValueError):
        return False
    return cc == 7


def _throttle_cc7_rows(payload: list[list], min_interval_s: float = CC7_MIN_INTERVAL_S) -> list[list]:
    if min_interval_s <= 0:
        return payload

    cc7_rows: list[tuple[int, float]] = []
    for index, row in enumerate(payload):
        if not _is_cc7_row(row):
            continue
        try:
            timestamp = float(row[-1])
        except (TypeError, ValueError):
            continue
        cc7_rows.append((index, timestamp))

    if len(cc7_rows) <= 2:
        return payload

    kept_indexes: set[int] = {cc7_rows[0][0]}
    last_kept_time = cc7_rows[0][1]
    for index, timestamp in cc7_rows[1:-1]:
        if timestamp - last_kept_time >= min_interval_s:
            kept_indexes.add(index)
            last_kept_time = timestamp
    kept_indexes.add(cc7_rows[-1][0])

    thinned: list[list] = []
    for index, row in enumerate(payload):
        if _is_cc7_row(row) and index not in kept_indexes:
            continue
        thinned.append(row)

    dropped = len(payload) - len(thinned)
    if dropped > 0:
        print(f"Throttled /cc 7 events: dropped {dropped} point(s) using min interval {min_interval_s:.3f}s")

    return thinned


def _send_event_payload(
    client: SimpleUDPClient,
    address: str,
    payload: list[list],
    max_events_per_packet: int = MAX_EVENTS_PER_OSC_PACKET,
) -> None:
    chunks = _chunked(payload, max_events_per_packet)
    if len(chunks) == 1:
        print(f"Sending {address}: {len(payload)} event(s)")
        client.send_message(address, payload)
        return

    print(
        f"Sending {address}: {len(payload)} event(s) in {len(chunks)} packets "
        f"(max {max_events_per_packet} events/packet)"
    )
    for packet_index, chunk in enumerate(chunks, start=1):
        print(f"  {address} packet {packet_index}/{len(chunks)}: {len(chunk)} event(s)")
        client.send_message(address, chunk)


def send_song_from_json(json_path: str | Path, ip: str = UDP_IP, port: int = UDP_PORT) -> None:
    arrangement = SongArrangement.from_json_file(json_path)
    send_song_from_arrangement(arrangement, ip=ip, port=port)


def send_song_from_dict(song_data: dict, ip: str = UDP_IP, port: int = UDP_PORT) -> None:
    arrangement = SongArrangement.from_dict(song_data)
    send_song_from_arrangement(arrangement, ip=ip, port=port)


def send_song_from_arrangement(arrangement: SongArrangement, ip: str = UDP_IP, port: int = UDP_PORT) -> None:
    payloads = arrangement.render_osc_payloads()

    client = SimpleUDPClient(ip, port)

    # Send /Midi first so the receiver has the full MIDI sequence buffered
    # before /Chords+/Pluck triggers song playback synchronisation.
    for address in ("/Midi", "/Chords", "/Pluck"):
        payload = payloads.get(address, [])
        if payload:
            if address == "/Midi":
                payload = _throttle_cc7_rows(payload)
            _send_event_payload(client, address, payload)


def send_reset(ip: str = UDP_IP, port: int = UDP_PORT) -> None:
    client = SimpleUDPClient(ip, port)
    client.send_message("/Reset", [])
    print("Sending /Reset")


def _parse_beat_label(beat_str: str, beats_per_bar: int) -> float:
    """Mirror JS parseBeat(): handle '~X.X' raw beats and 'bar.beat.sub' format."""
    if not beat_str:
        return 0.0
    s = str(beat_str)
    if s.startswith("~"):
        return float(s[1:]) if s[1:] else 0.0
    parts = s.split(".")
    bar = int(parts[0]) if parts else 1
    subdiv = 16  # JS SUBDIV constant
    if len(parts) >= 3:
        beat = int(parts[1])
        sub = int(parts[2])
        return (bar - 1) * beats_per_bar + (beat - 1) + (sub - 1) / subdiv
    beat_frac = float(parts[1]) if len(parts) > 1 else 1.0
    return (bar - 1) * beats_per_bar + (beat_frac - 1)


def _analyze_audio(payload: dict) -> dict:
    """Full audio analysis via scipy STFT. Returns note hit/miss + spectrogram frames."""
    import numpy as np
    from scipy import signal
    from scipy.io import wavfile

    audio_b64: str = payload["audio_b64"]
    events: list = payload.get("events", [])
    bpm_val: float = float(payload.get("bpm", 120))
    time_sig: str = payload.get("time_sig", "4/4")
    latency_ms: float = float(payload.get("latency_ms", 0))
    latency_drift_ms_per_min: float = float(payload.get("latency_drift_ms_per_min", 0))
    rec_start_beat: float = float(payload.get("rec_start_beat", 0))

    # Time signature → seconds per beat
    try:
        _num_str, denom_str = time_sig.split("/")
        beats_per_bar = int(_num_str)
        denominator = int(denom_str)
    except Exception:
        beats_per_bar = 4
        denominator = 4
    seconds_per_beat = (60.0 / max(1.0, bpm_val)) * (4.0 / denominator)

    # Decode WAV
    wav_bytes = base64.b64decode(audio_b64)
    sr, audio = wavfile.read(io.BytesIO(wav_bytes))

    # Convert to float32 mono
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if audio.dtype == np.int16:
        audio = audio.astype(np.float32) / 32768.0
    elif audio.dtype == np.int32:
        audio = audio.astype(np.float32) / 2147483648.0
    else:
        audio = audio.astype(np.float32)

    # STFT
    nperseg = 4096
    hop = 1024
    noverlap = nperseg - hop
    freqs, times, Zxx = signal.stft(
        audio, fs=sr, nperseg=nperseg, noverlap=noverlap, window="hann"
    )
    db_matrix = 20.0 * np.log10(np.abs(Zxx) + 1e-10)  # shape: (freq_bins, time_frames)

    # MIDI → frequency bin mapping
    MIDI_MIN_VAL = 40
    MIDI_MAX_VAL = 68
    midi_bins: dict[int, int] = {}
    for n in range(MIDI_MIN_VAL, MIDI_MAX_VAL + 1):
        f = 440.0 * (2.0 ** ((n - 69) / 12.0))
        b = int(round(f * nperseg / sr))
        midi_bins[n] = min(b, db_matrix.shape[0] - 1)

    # Beat-dependent latency in beats: base + drift over elapsed recording minutes
    def latency_beats_at(beat_value: float) -> float:
        elapsed_beats = max(0.0, beat_value - rec_start_beat)
        elapsed_minutes = (elapsed_beats * seconds_per_beat) / 60.0
        latency_ms_now = max(0.0, latency_ms + (latency_drift_ms_per_min * elapsed_minutes))
        return latency_ms_now / (seconds_per_beat * 1000.0)

    # Build spectrogram frames aligned to sequencer beats (latency already applied)
    spec_frames = []
    for i, t in enumerate(times):
        raw_beat = rec_start_beat + t / seconds_per_beat
        beat = raw_beat - latency_beats_at(raw_beat)
        data = [
            float(db_matrix[midi_bins[n], i]) for n in range(MIDI_MIN_VAL, MIDI_MAX_VAL + 1)
        ]
        spec_frames.append({"beat": round(float(beat), 4), "data": data})

    # Note hit / miss detection
    HIT_DB_THRESHOLD = -50.0
    HIT_WINDOW_BEFORE = 0.1  # beats
    HIT_WINDOW_AFTER = 0.5   # beats

    note_analysis: dict = {}
    for ev in events:
        ev_id = ev.get("id")
        note = ev.get("note")
        if ev_id is None or note is None:
            continue

        note_beat = _parse_beat_label(str(ev.get("beat", "")), beats_per_bar)
        note_latency_beats = latency_beats_at(note_beat)
        w_start = note_beat + note_latency_beats - HIT_WINDOW_BEFORE
        w_end = note_beat + note_latency_beats + HIT_WINDOW_AFTER

        # Convert beat window to time window
        t_start = w_start * seconds_per_beat
        t_end = w_end * seconds_per_beat
        win_mask = (times >= t_start) & (times <= t_end)

        if not win_mask.any():
            note_analysis[ev_id] = {
                "hit": False, "confidence": 0.0, "peak": -200.0, "tremoloHz": None,
            }
            continue

        n_int = int(note)
        b_idx = midi_bins.get(n_int, 0)
        lo = max(0, b_idx - 1)
        hi = min(db_matrix.shape[0] - 1, b_idx + 2)

        peak = float(db_matrix[lo : hi + 1, :][:, win_mask].max())
        hit = peak > HIT_DB_THRESHOLD
        confidence = float(min(1.0, (peak - HIT_DB_THRESHOLD) / 30.0)) if hit else 0.0

        # Tremolo rate via amplitude envelope autocorrelation
        tremolo_hz = None
        duration_b = float(ev.get("duration_b", 0))
        if duration_b > 0.5:
            dur_t_start = (note_beat + note_latency_beats) * seconds_per_beat
            dur_t_end = (note_beat + note_latency_beats + duration_b) * seconds_per_beat
            dur_mask = (times >= dur_t_start) & (times <= dur_t_end)
            if dur_mask.sum() >= 20:
                lin = np.power(10.0, db_matrix[lo : hi + 1, :][:, dur_mask] / 20.0)
                amp_envelope = np.sqrt(np.mean(lin**2, axis=0))
                max_amp = amp_envelope.max()
                if max_amp > 1e-10:
                    norm = amp_envelope / max_amp - 0.5
                    N = len(norm)
                    max_lag = int(N * 0.8)
                    acorr = np.correlate(norm, norm, mode="full")
                    acorr = acorr[N - 1 :]  # positive lags only
                    best_lag = -1
                    best_val = 0.3
                    for lag in range(3, max_lag - 1):
                        if (
                            acorr[lag] > acorr[lag - 1]
                            and acorr[lag] > acorr[lag + 1]
                            and acorr[lag] > best_val
                        ):
                            best_val = float(acorr[lag])
                            best_lag = lag
                    if best_lag > 0:
                        frame_rate = float(sr) / hop
                        hz = frame_rate / best_lag
                        if 1.0 <= hz <= 20.0:
                            tremolo_hz = round(hz * 10) / 10

        note_analysis[ev_id] = {
            "hit": hit,
            "confidence": round(confidence, 3),
            "peak": round(peak, 1),
            "tremoloHz": tremolo_hz,
        }

    return {
        "ok": True,
        "noteAnalysis": note_analysis,
        "spectrogram": {
            "source": "python",
            "midiMin": MIDI_MIN_VAL,
            "midiMax": MIDI_MAX_VAL,
            "hopSamples": hop,
            "sampleRate": int(sr),
            "frames": spec_frames,
        },
    }


def run_upload_server(
    host: str = UPLOAD_HOST,
    port: int = UPLOAD_PORT,
    bot_ip: str = UDP_IP,
    bot_port: int = UDP_PORT,
) -> None:
    class UploadHandler(BaseHTTPRequestHandler):
        def _set_headers(self, status_code: int = 200) -> None:
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_OPTIONS(self):
            self._set_headers(204)

        def do_POST(self):
            if self.path == "/upload":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    raw = self.rfile.read(length)
                    payload = json.loads(raw.decode("utf-8"))
                    send_song_from_dict(payload, ip=bot_ip, port=bot_port)
                    self._set_headers(200)
                    self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
                except Exception as exc:
                    self._set_headers(400)
                    self.wfile.write(json.dumps({"ok": False, "error": str(exc)}).encode("utf-8"))
                return

            elif self.path == "/reset":
                try:
                    send_reset(ip=bot_ip, port=bot_port)
                    self._set_headers(200)
                    self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
                except Exception as exc:
                    self._set_headers(400)
                    self.wfile.write(json.dumps({"ok": False, "error": str(exc)}).encode("utf-8"))
                return

            elif self.path == "/analyze":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    raw = self.rfile.read(length)
                    payload = json.loads(raw.decode("utf-8"))
                    result = _analyze_audio(payload)
                    self._set_headers(200)
                    self.wfile.write(json.dumps(result).encode("utf-8"))
                except Exception as exc:
                    import traceback
                    traceback.print_exc()
                    self._set_headers(400)
                    self.wfile.write(json.dumps({"ok": False, "error": str(exc)}).encode("utf-8"))
                return

            else:
                self._set_headers(404)
                self.wfile.write(json.dumps({"ok": False, "error": "Not found"}).encode("utf-8"))
                return

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer((host, port), UploadHandler)
    print(f"Upload server listening on http://{host}:{port}/upload")
    print(f"Reset endpoint at http://{host}:{port}/reset")
    print(f"Forwarding songs to GuitarBot OSC at {bot_ip}:{bot_port}")
    server.serve_forever()


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Send GuitarBot arrangement JSON to OSC endpoints")
    parser.add_argument("json_path", nargs="?", help="Path to arrangement JSON file")
    parser.add_argument("--ip", default=UDP_IP, help="GuitarBot receiver IP")
    parser.add_argument("--port", type=int, default=UDP_PORT, help="GuitarBot receiver UDP port")
    parser.add_argument("--serve", action="store_true", help="Run local HTTP upload server for sequencer.html")
    parser.add_argument("--serve-host", default=UPLOAD_HOST, help="Upload server bind host")
    parser.add_argument("--serve-port", type=int, default=UPLOAD_PORT, help="Upload server bind port")
    return parser


if __name__ == "__main__":
    parser = _build_arg_parser()
    args = parser.parse_args()

    if args.serve:
        run_upload_server(
            host=args.serve_host,
            port=args.serve_port,
            bot_ip=args.ip,
            bot_port=args.port,
        )
    else:
        if args.json_path:
            path = Path(args.json_path)
        else:
            path = Path(__file__).resolve().parent / "Docs" / "Run Time Configuration" / "smoke_on_the_water.json"
        send_song_from_json(path, ip=args.ip, port=args.port)
