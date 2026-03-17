from __future__ import annotations

from pathlib import Path

from pythonosc.udp_client import SimpleUDPClient

from parsing.song_arrangement import SongArrangement


UDP_IP = "127.0.0.1"
UDP_PORT = 12000


def send_song_from_json(json_path: str | Path, ip: str = UDP_IP, port: int = UDP_PORT) -> None:
    arrangement = SongArrangement.from_json_file(json_path)
    payloads = arrangement.render_osc_payloads()

    client = SimpleUDPClient(ip, port)

    for address in ("/Chords", "/Pluck", "/Midi"):
        payload = payloads.get(address, [])
        if payload:
            print(f"Sending {address}: {len(payload)} event(s)")
            client.send_message(address, payload)


if __name__ == "__main__":
    default_path = Path(__file__).resolve().parent / "Docs" / "Run Time Configuration" / "smoke_on_the_water.json"
    send_song_from_json(default_path)
