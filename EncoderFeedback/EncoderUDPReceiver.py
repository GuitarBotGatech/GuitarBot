"""
EncoderUDPReceiver.py

Listens for encoder feedback UDP packets from the microcontroller and logs them.
Expected packet format matches EncoderFeedbackCollector.h (packed):
- uint8  motor_id
- int32  encoder_position (little-endian)
- uint16 status_word (little-endian)
- uint8  checksum (one's complement sum of prior fields)

By default, listens on 0.0.0.0:8889 and prints to console and optional CSV.

Usage:
  python -m EncoderFeedback.EncoderUDPReceiver --host 0.0.0.0 --port 8889 --csv encoder_log.csv
  python -m EncoderFeedback.EncoderUDPReceiver --duration 10 --csv run.csv
"""
from __future__ import annotations
import argparse
import socket
import struct
import time
import csv
from typing import Optional

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8889

PACKET_STRUCT = struct.Struct("<B i H B")  # motor_id, encoder_position, status_word, checksum
PACKET_SIZE = PACKET_STRUCT.size  # 8 bytes


def calc_checksum(motor_id: int, encoder_pos: int, status_word: int) -> int:
    s = 0
    s = (s + (motor_id & 0xFF)) & 0xFF
    s = (s + (encoder_pos & 0xFF)) & 0xFF
    s = (s + ((encoder_pos >> 8) & 0xFF)) & 0xFF
    s = (s + ((encoder_pos >> 16) & 0xFF)) & 0xFF
    s = (s + ((encoder_pos >> 24) & 0xFF)) & 0xFF
    s = (s + (status_word & 0xFF)) & 0xFF
    s = (s + ((status_word >> 8) & 0xFF)) & 0xFF
    return (~s) & 0xFF


def run_receiver(host: str, port: int, csv_path: Optional[str], duration: Optional[float]):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))
    sock.settimeout(0.5)
    print(f"Listening for encoder feedback on {host}:{port} (packet size {PACKET_SIZE} bytes)")

    csv_file = None
    csv_writer = None
    if csv_path:
        csv_file = open(csv_path, "w", newline="")
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(["timestamp", "motor_id", "encoder_position", "status_word", "checksum_ok"])  # header

    start = time.time()
    count = 0
    try:
        while True:
            if duration is not None and (time.time() - start) >= duration:
                print("Duration elapsed; stopping receiver")
                break
            try:
                data, addr = sock.recvfrom(64)
            except socket.timeout:
                continue

            if len(data) < PACKET_SIZE:
                continue

            # Some MCUs may batch multiple packets; parse chunk-wise
            offset = 0
            while offset + PACKET_SIZE <= len(data):
                motor_id, enc, status, checksum = PACKET_STRUCT.unpack_from(data, offset)
                offset += PACKET_SIZE
                expected = calc_checksum(motor_id, enc, status)
                ok = (checksum == expected)
                ts = time.time()
                count += 1
                print(f"[{ts:.3f}] motor={motor_id:02d} enc={enc:8d} status=0x{status:04X} chk={'OK' if ok else 'BAD'}")
                if csv_writer:
                    csv_writer.writerow([f"{ts:.6f}", motor_id, enc, status, int(ok)])
    finally:
        sock.close()
        if csv_file:
            csv_file.close()
        print(f"Receiver stopped after {count} packets")


def main():
    ap = argparse.ArgumentParser(description="UDP receiver for encoder feedback")
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--csv", dest="csv_path")
    ap.add_argument("--duration", type=float)
    args = ap.parse_args()

    run_receiver(args.host, args.port, args.csv_path, args.duration)


if __name__ == "__main__":
    main()
