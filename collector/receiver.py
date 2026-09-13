#!/usr/bin/env python3
"""The collector's endpoints: readings in, and one command waiting to be asked for.

Readings are pushed to it by the automation hub (D-049). Nothing here reaches
out, and nothing here authenticates the sender, deliberately: the tailnet
policy is the credential. The port is reachable only from the roles the policy
names, and the server binds only to the node's tailnet address, so nothing
else on the host reaches it either.

    LISTEN_ADDR=<tailnet address> ./receiver.py

Each accepted reading becomes one JSON line in $DATA_DIR/readings.jsonl, with
the time it arrived and the tailnet address it came from. Arrival time, not
the sender's clock, is what a lost-comms drill measures.

GET /command is the mobile-unit channel (docs/designs/mobile-unit.md). The hub
asks; this answers with at most one queued command name and then forgets it.
The collector cannot make the house do anything: the name means nothing here,
the allowlist lives in the hub, and the hub applies its own guards before it
acts. An operator queues a command with collector/ask.sh.
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
        if self.path != "/command":
            return self.reply(404)
        # One command, handed over once. Taken from the queue as it is served,
        # so a repeated poll gets nothing and a lost reply loses the command
        # rather than repeating it -- the safer way round for a machine that
        # moves.
        path = os.path.join(DATA_DIR, "command.json")
        body = b"{}"
        try:
            with open(path, "rb") as f:
                queued = json.loads(f.read() or b"{}")
            os.remove(path)
        except (FileNotFoundError, ValueError):
            queued = {}
        if queued.get("command"):
            queued["served_at"] = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
            append({"received_at": queued["served_at"], "peer": self.client_address[0],
                    "served_command": queued})
            body = json.dumps({"command": queued["command"], "id": queued.get("id", "")}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_404(self):
        self.reply(404)

    do_PUT = do_DELETE = do_PATCH = do_HEAD = do_404

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.client_address[0], fmt % args))


def main():
    if not LISTEN_ADDR:
        sys.exit("LISTEN_ADDR is required: bind to the tailnet address, never to all interfaces")
    ThreadingHTTPServer((LISTEN_ADDR, PORT), Ingest).serve_forever()


if __name__ == "__main__":
    main()
