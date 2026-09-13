#!/usr/bin/env python3
"""The collector's ingest endpoint: one port, one path, append-only.

Readings are pushed to it by the automation hub (D-049). Nothing here reaches
out. The port is reachable only from the roles the policy names, and the
server binds only to the node's tailnet address, so nothing else on the host
reaches it either.

There is no password, and there will not be one: the sender's tailnet address
is the credential. That address is not a claim the sender makes -- it is
assigned by the control plane and bound to a node key, and packets carrying
any other source address never arrive over the tunnel. So the server accepts
writes only from the addresses in INGEST_FROM, which today is the automation
hub alone (D-059). The policy decides who may knock; this decides who may
write, and the two are not the same question -- a policy that admits a reader
to the port should not thereby admit a writer to the record.

    LISTEN_ADDR=<tailnet address> INGEST_FROM=<hub address> ./receiver.py

INGEST_FROM is a comma-separated list, and it is required: a collector that
would take a reading from anyone is a collector whose record means nothing.

Each accepted reading becomes one JSON line in $DATA_DIR/readings.jsonl, with
the time it arrived and the tailnet address it came from. Arrival time, not
the sender's clock, is what a lost-comms drill measures.

This receives and nothing else. It briefly served a command the hub could ask
for; the house now decides for itself when the robot runs, so that endpoint is
gone and the collector has no way to ask the house for anything at all
(docs/designs/mobile-unit.md, D-056).
"""
import json
import os
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LISTEN_ADDR = os.environ.get("LISTEN_ADDR", "")
PORT = int(os.environ.get("PORT", "8443"))
DATA_DIR = os.environ.get("DATA_DIR", "/data")
INGEST_FROM = [a.strip() for a in os.environ.get("INGEST_FROM", "").split(",") if a.strip()]
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
        # Refused before the body is read: an unwelcome sender does not get to
        # spend the collector's memory on a request it was never going to
        # keep. 403 rather than 404 -- the port is open to them by policy, and
        # pretending otherwise would only make the next drill harder to read.
        if self.client_address[0] not in INGEST_FROM:
            return self.reply(403)
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
        # There was a GET /command here: the hub asked, and the answer could
        # name one command from an allowlist the hub held. The owner then
        # decided the house should trigger the robot itself, on its own event,
        # with no dependency on anything outside it -- so the endpoint was
        # removed rather than left unused. An endpoint nobody asks for is
        # still an endpoint (D-056).
        self.reply(404)

    def do_404(self):
        self.reply(404)

    do_PUT = do_DELETE = do_PATCH = do_HEAD = do_404

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.client_address[0], fmt % args))


def main():
    if not LISTEN_ADDR:
        sys.exit("LISTEN_ADDR is required: bind to the tailnet address, never to all interfaces")
    if not INGEST_FROM:
        sys.exit("INGEST_FROM is required: name the senders whose readings count")
    ThreadingHTTPServer((LISTEN_ADDR, PORT), Ingest).serve_forever()


if __name__ == "__main__":
    main()
