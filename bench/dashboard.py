"""Serve the results dashboard. It polls results/results.json and results/live.json every few seconds,
so a running bench or a live `preflight cascade` shows up without reloading.

    python bench/dashboard.py            # http://localhost:8765/dashboard.html
"""
from __future__ import annotations

import argparse
import functools
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent


class NoCache(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *a):  # keep the terminal for the demo output
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-open", action="store_true")
    a = ap.parse_args()
    (HERE / "results").mkdir(exist_ok=True)
    handler = functools.partial(NoCache, directory=str(HERE))
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), handler)
    url = f"http://localhost:{a.port}/dashboard.html"
    print(f"preflight dashboard: {url}  (Ctrl+C to stop)")
    if not a.no_open:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
