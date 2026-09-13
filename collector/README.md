# Collector

The telemetry sink: a tailnet node with the `tag:collector` identity, running
as two containers on the cloud dev host. It lives outside the house and has no
path into it; the automation hub pushes readings to it (D-049).

| container | what it is |
|---|---|
| `zt-collector-ts` | the tailnet node: `tailscale/tailscale`, kernel mode, its own network namespace, identity in a named volume |
| `zt-collector-ingest` | [`receiver.py`](receiver.py), sharing that namespace, bound to the node's tailnet address only |

Nothing is published on the host's own interfaces. The receiver accepts one
path, `POST /ingest`, one small JSON reading per request, and appends it with
its arrival time and sender address to `readings.jsonl` in the data volume.

## Run

The data volume is made writable for the unprivileged user once:

```bash
docker run --rm -v zt-collector-data:/data alpine:3 chown 65534:65534 /data
```

The node container itself, once its state volume exists, takes no key:

```bash
docker run -d --name zt-collector-ts --hostname zt-collector \
  --device /dev/net/tun --cap-add NET_ADMIN --cap-add NET_RAW \
  --memory 128m --restart unless-stopped \
  -e TS_USERSPACE=false -e TS_ACCEPT_DNS=false \
  -e TS_STATE_DIR=/var/lib/tailscale \
  -e TS_EXTRA_ARGS=--advertise-tags=tag:collector \
  -v zt-collector-ts:/var/lib/tailscale \
  tailscale/tailscale:v1.102.3
```

```bash
docker run -d --name zt-collector-ingest \
  --network container:zt-collector-ts \
  --read-only --cap-drop ALL --security-opt no-new-privileges \
  --user 65534:65534 --memory 64m --pids-limit 32 \
  --restart unless-stopped \
  -e LISTEN_ADDR="$(docker exec zt-collector-ts tailscale ip -4)" \
  -v "$HOME/zt-collector/receiver.py:/app/receiver.py:ro" \
  -v zt-collector-data:/data \
  python:3.13-alpine python3 /app/receiver.py
```

## Registration, and why no key is stored

The node registers once, with a one-time tagged key typed in at creation. Its
identity then lives in the state volume, so the containers can be recreated
without a key at all — which is how they run now: nothing in the container's
environment can register anything.

The first build did keep the used key in the environment. It was spent and
could register nothing, but a credential that outlives its purpose is still
one lying around, so it was removed by recreating both containers (about nine
seconds of downtime, one telemetry tick, no reading lost). Replacing a lost
state volume needs a fresh key from the console, which is the same trade as
[the rehome runbook](../docs/runbooks/rehome-collector.md).

## Undo

```bash
docker rm -f zt-collector-ingest
```

The readings stay in the `zt-collector-data` volume until it is removed as
well. Removing the node itself is `docker rm -f zt-collector-ts` and deleting
the machine in the Tailscale console.

## Known limits

- If the node container restarts, the receiver loses the namespace it joined
  and has to be restarted after it. Acceptable for a lab sink; recorded rather
  than engineered around.
- Readings stay on the host. Moving them to the archive bucket is the
  certificate-based cloud access of Phase 5.
- No sender authentication in the application. The tailnet policy decides who
  reaches the port; the receiver records who did.
