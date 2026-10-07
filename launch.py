#!/usr/bin/env python3
"""Launch the GuitarBot web UI and play/reset HTTP server."""

import argparse

from web.server import main as server_main


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch the GuitarBot stack")
    parser.add_argument(
        "--config",
        default=None,
        help="Interpretation config YAML (default: configs/default.yaml)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the web UI in a new browser tab",
    )
    parser.add_argument(
        "--experimental-traj",
        action="store_true",
        help="Enable experimental variable LH prep timing",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan trajectories but do not send UDP to OpenCR",
    )
    parser.add_argument("--port", type=int, default=8000, help="HTTP port")
    args = parser.parse_args()

    argv = ["--port", str(args.port)]
    if args.config:
        argv += ["--config", args.config]
    if args.no_browser:
        argv.append("--no-browser")
    if args.experimental_traj:
        argv.append("--experimental-traj")
    if args.dry_run:
        argv.append("--dry-run")
    server_main(argv)


if __name__ == "__main__":
    main()
