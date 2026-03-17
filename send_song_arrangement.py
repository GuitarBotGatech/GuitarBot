from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from pythonosc.udp_client import SimpleUDPClient

from parsing.song_arrangement import SongArrangement


UDP_IP = "127.0.0.1"
UDP_PORT = 12000
UPLOAD_HOST = "127.0.0.1"
UPLOAD_PORT = 8765


def send_song_from_json(json_path: str | Path, ip: str = UDP_IP, port: int = UDP_PORT) -> None:
    arrangement = SongArrangement.from_json_file(json_path)
    send_song_from_arrangement(arrangement, ip=ip, port=port)


def send_song_from_dict(song_data: dict, ip: str = UDP_IP, port: int = UDP_PORT) -> None:
    arrangement = SongArrangement.from_dict(song_data)
    send_song_from_arrangement(arrangement, ip=ip, port=port)


def send_song_from_arrangement(arrangement: SongArrangement, ip: str = UDP_IP, port: int = UDP_PORT) -> None:
    payloads = arrangement.render_osc_payloads()

    client = SimpleUDPClient(ip, port)

    for address in ("/Chords", "/Pluck", "/Midi"):
        payload = payloads.get(address, [])
        if payload:
            print(f"Sending {address}: {len(payload)} event(s)")
            client.send_message(address, payload)


def send_reset(ip: str = UDP_IP, port: int = UDP_PORT) -> None:
    client = SimpleUDPClient(ip, port)
    client.send_message("/Reset", [])
    print("Sending /Reset")


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

            if self.path == "/reset":
                try:
                    send_reset(ip=bot_ip, port=bot_port)
                    self._set_headers(200)
                    self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
                except Exception as exc:
                    self._set_headers(400)
                    self.wfile.write(json.dumps({"ok": False, "error": str(exc)}).encode("utf-8"))
                return

            if self.path != "/upload":
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
