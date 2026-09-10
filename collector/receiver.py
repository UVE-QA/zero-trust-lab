#!/usr/bin/env python3
"""The collector's ingest endpoint: one port, one path, append-only.

Readings are pushed to it by the automation hub (D-049). Nothing here reaches
out, and nothing here authenticates the sender, deliberately: the tailnet
policy is the credential. The port is reachable only from the roles the policy
names, and the server binds only to the node's tailnet address, so nothing
else on the host reaches it either.

    LISTEN_ADDR=<tailnet address> ./receiver.py

Each accepted reading becomes one JSON line in $DATA_DIR/readings.jsonl, with
the time it arrived and the tailnet address it came from. Arrival time, not
the sender's clock, is what a lost-comms drill measures.
"""
import json
import os
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LISTEN_ADDR = os.environ.get("LISTEN_ADDR", "")
PORT = int(os.environ.get("PORT", "8443"))
DATA_DIR = os.environ.get("DATA_DIR", "/data")
MAX_BODY = 4096                 # one reading, not a batch
MAX_FILE = 5 * 1024 * 1024      # then rotate once; the archive is Phase 5's job


def append(record):
    path = os.path.join(DATA_DIR, "readings.jsonl")
    try:
        if os.path.getsize(path) > MAX_FILE:
            os.replace(path, path + ".1")
    except FileNotFoundError:
        pass
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, separators=(",", ":")) + "\n")


class Ingest(BaseHTTPRequestHandler):
    server_version = "collector"
    sys_version = ""

    def reply(self, code):
        self.send_response(code)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        if self.path != "/ingest":
            return self.reply(404)
        try:
            n = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.reply(400)
        if not 0 < n <= MAX_BODY:
            return self.reply(413 if n > MAX_BODY else 400)
        try:
            body = json.loads(self.rfile.read(n))
        except ValueError:
            return self.reply(400)
        if not isinstance(body, dict) or not isinstance(body.get("sensor"), str) or "value" not in body:
            return self.reply(422)
        append({
            "received_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "peer": self.client_address[0],
            "reading": body,
        })
        self.reply(204)

    def do_GET(self):
        self.reply(404)

    do_PUT = do_DELETE = do_PATCH = do_HEAD = do_GET

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.client_address[0], fmt % args))


def main():
    if not LISTEN_ADDR:
        sys.exit("LISTEN_ADDR is required: bind to the tailnet address, never to all interfaces")
    ThreadingHTTPServer((LISTEN_ADDR, PORT), Ingest).serve_forever()


if __name__ == "__main__":
    main()
