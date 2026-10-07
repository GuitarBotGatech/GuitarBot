#!/usr/bin/env python3
"""GuitarBot HTTP server: static UI plus POST /play and POST /reset."""

from __future__ import annotations

import argparse
import os
import threading
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from tuning import tune as tu
from control.playback import PlaybackSession, get_session
from notation.events import load_config

WEB_DIR = Path(__file__).resolve().parent
DEFAULT_PORT = 8000


def _env_flag(name: str) -> bool:
    value = os.environ.get(name, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def create_app(
    *,
    dry_run: bool = False,
    session: PlaybackSession | None = None,
) -> Flask:
    app = Flask(__name__)
    playback = session if session is not None else get_session()
    app.config["DRY_RUN"] = bool(dry_run)
    app.config["PLAYBACK_SESSION"] = playback

    def _busy_error():
        return jsonify({"ok": False, "error": "robot is busy"}), 409

    def _send_in_background(traj) -> None:
        try:
            from control.playback import send_trajectory

            send_trajectory(traj)
        except Exception:
            import traceback

            traceback.print_exc()
        finally:
            playback.release()

    @app.get("/health")
    def health():
        return jsonify(
            {
                "ok": True,
                "dry_run": bool(app.config["DRY_RUN"]),
                "playing": playback.busy_lock.locked(),
            }
        )

    @app.post("/play")
    def play():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"ok": False, "error": "JSON object required"}), 400

        if not playback.try_acquire():
            return _busy_error()

        try:
            traj = playback.play_arrangement(payload, send=False)
        except Exception as exc:
            playback.release()
            return jsonify({"ok": False, "error": str(exc)}), 400

        duration_s = float(traj.shape[0] * tu.TIME_STEP)
        body = {
            "ok": True,
            "shape": [int(traj.shape[0]), int(traj.shape[1])],
            "duration_s": duration_s,
            "dry_run": bool(app.config["DRY_RUN"]),
        }

        if app.config["DRY_RUN"]:
            playback.release()
            return jsonify(body)

        worker = threading.Thread(
            target=_send_in_background,
            args=(traj,),
            daemon=True,
            name="guitarbot-play",
        )
        worker.start()
        return jsonify(body)

    @app.post("/reset")
    def reset_robot():
        if not playback.try_acquire():
            return _busy_error()

        try:
            traj = playback.reset(send=False)
        except Exception as exc:
            playback.release()
            return jsonify({"ok": False, "error": str(exc)}), 400

        body = {
            "ok": True,
            "shape": [int(traj.shape[0]), int(traj.shape[1])],
            "duration_s": float(traj.shape[0] * tu.TIME_STEP),
            "dry_run": bool(app.config["DRY_RUN"]),
        }

        if app.config["DRY_RUN"]:
            playback.release()
            return jsonify(body)

        worker = threading.Thread(
            target=_send_in_background,
            args=(traj,),
            daemon=True,
            name="guitarbot-reset",
        )
        worker.start()
        return jsonify(body)

    @app.get("/")
    def index():
        return send_from_directory(WEB_DIR, "index.html")

    @app.get("/<path:filename>")
    def static_files(filename: str):
        return send_from_directory(WEB_DIR, filename)

    return app


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GuitarBot play/reset HTTP server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="HTTP port")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind host",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan trajectories but do not send UDP to OpenCR",
    )
    parser.add_argument(
        "--experimental-traj",
        action="store_true",
        help="Enable experimental variable LH prep timing",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the web UI in a browser tab",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Interpretation config YAML (default: configs/default.yaml)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    dry_run = bool(args.dry_run or _env_flag("GUITARBOT_DRY_RUN"))
    tu.USE_EXPERIMENTAL_TRAJ = bool(args.experimental_traj)
    tu.graph = False

    config = load_config(args.config)
    app = create_app(dry_run=dry_run, session=PlaybackSession(config=config))
    url = f"http://{args.host}:{args.port}/index.html"
    print(f"GuitarBot server on {url}")
    print(f"  POST /play   arrangement JSON")
    print(f"  POST /reset  home motors")
    print(f"  dry_run={dry_run} experimental_traj={tu.USE_EXPERIMENTAL_TRAJ}")
    print(f"  config={args.config or 'configs/default.yaml'}")

    if not args.no_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()

    app.run(host=args.host, port=args.port, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
