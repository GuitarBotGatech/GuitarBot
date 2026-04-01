#!/usr/bin/env python3
"""Development web server for GuitarBot UI with cache disabled."""

from __future__ import annotations

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        # Force fresh assets on every refresh so UI edits appear immediately.
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve GuitarBot web UI without browser caching")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--directory", default=str(Path(__file__).parent / "web"))
    args = parser.parse_args()

    root = Path(args.directory).resolve()
    handler = lambda *a, **kw: NoCacheHandler(*a, directory=str(root), **kw)
    server = ThreadingHTTPServer((args.host, args.port), handler)

    print(f"Serving {root} on http://{args.host}:{args.port} (cache disabled)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
