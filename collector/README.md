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

It accepts that write from the automation hub and from nobody else. Reaching
the port and being allowed to write to the record are two different
permissions, and the receiver now holds the second one itself (D-059).

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
  -e INGEST_FROM="$HUB_ADDR" \
  -v "$HOME/zt-collector/receiver.py:/app/receiver.py:ro" \
  -v zt-collector-data:/data \
  python:3.13-alpine python3 /app/receiver.py
```

## Shipping the readings out, with no AWS key

[`uploader.py`](uploader.py) exchanges the collector's X.509 certificate for
credentials that expire in an hour (IAM Roles Anywhere) and PUTs everything
written since the last run as one object in the archive bucket. There is no
access key on this host, in its environment, or in any file it reads (D-064,
D-067).

```bash
*/15 * * * * $HOME/zt-collector/upload.sh >> $HOME/zt-collector/upload.log 2>&1
```

[`upload.sh`](upload.sh) creates and destroys a container per run, so nothing
long-lived holds the certificate open. The image is `python:3.13-slim` because
it ships the `openssl` binary the signing needs — installing a package at
runtime, as root, on the machine that holds the credential, to save 40 MB, is
the wrong trade.

Two things are hand-rolled rather than imported: the `CreateSession` request
signed with the certificate's own key, and the ordinary SigV4 for S3. AWS
publishes a helper binary for the first; downloading and running a binary on
the machine that holds the credential is a larger trust decision than sixty
lines that can be read.

State is one integer: the byte offset already shipped, kept outside the data
volume. If the readings file is shorter than the offset it has been rotated,
and the uploader starts again from the beginning rather than guessing. It never
ships half a line.

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
- Readings also stay on the host after upload. Nothing prunes the local file
  except the 5 MB rotation, and the uploader cannot delete anything anywhere —
  by design, since its role may only add.
- The upload runs from cron on the host, not from a supervised service. If the
  host's clock or cron stops, readings queue locally and the next run ships
  them; nothing alerts. The staleness of the archive is not yet measured, and
  saying so is cheaper than pretending it is.
- The sender is identified by its tailnet address and nothing more. That is a
  real credential here — the control plane assigns the address and binds it to
  a node key, and a packet arriving over the tunnel cannot forge one — but it
  is the tailnet's assurance, not the application's. If the collector ever
  takes readings from outside this tailnet, it needs its own.
- `INGEST_FROM` is set from the local inventory when the container is created,
  so an address that changes has to be re-applied by hand. One sender, one
  line; a fleet would want the hub to be looked up rather than typed.
