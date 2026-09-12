# Runbook — a device joins, changes role, and is revoked

**Purpose.** Show, on the live tailnet, that what a device may reach follows
its identity and nothing else: the same machine on the same network, with the
policy untouched throughout.

**Status:** executed 2026-09-11. Lab roles only; the house was not involved.
Re-run every 30 days: the numbers are evidence only while they are recent, so
the evidence page shows when the next run is due and a weekly job raises an
issue when it slips.

---

## Method

A throwaway container on the cloud dev host is registered as its own tailnet
node with a **one-time, ephemeral, tagged** key — tagged means the node takes
the role from the key and cannot claim another; ephemeral means it disappears
when it goes offline; one-time means the key dies with first use.

From inside that node, [`collector/reach.sh`](../../collector/reach.sh) tries
one TCP connection to each of eight destinations: the collector's ingest port,
the hub's UI, shell and broker, production's SSH, the home server's SSH and
both smart plugs. Nothing is sent; the question is only whether the tailnet
carries the connection. The destinations are passed in from a file the
operator keeps locally — no real address belongs in this repository.

**The policy file was not edited at any point during this drill.**

## Observed

| | time (UTC) | what |
|---|---|---|
| joins as `tag:sensor` | 02:56:27 | one node, role from the key |
| measured | 02:56:39–02:57:07 | **1 of 8 open**: the collector's ingest port. The hub's UI, shell and broker, production, the home server and both plugs: refused |
| role changed in the console to `tag:appliance` | 02:58:57 | one field, no policy change |
| path gone | by 02:59:00 | the port that was open every second since 02:57:22 went refused **within about three seconds** |
| measured again | 02:59:16–02:59:45 | **0 of 8 open** |
| device removed in the console | 03:00:44.3 | |
| node off the network | 03:00:45.9 | **about 1.6 seconds**, and every destination refused after it |

Timing resolution is one second: the poll ran once a second with a two-second
connect timeout, so each figure is that poll's granularity, not a stopwatch.

## What it shows, and what it does not

- **Access follows identity.** Same machine, same address, same network. One
  role reached exactly one port; the other reached nothing. Nobody edited a
  rule between the two measurements.
- **Revocation is immediate and central.** Removing the device in the control
  plane cut it off in under two seconds. Nothing had to be changed on the
  device, and the device could not refuse.
- **A tagged key cannot lift itself.** The node never had a way to claim a
  different role; the role travelled with the credential and then with the
  control plane's record of it.
- **It does not show posture or people.** These are machine roles. The
  operator's own devices are governed by the posture rules, which this drill
  did not touch.

## Re-run

Generate a one-time, ephemeral, tagged key in the console, then, on the host:

```bash
docker run -d --name zt-drill --hostname zt-drill --device /dev/net/tun \
  --cap-add NET_ADMIN --cap-add NET_RAW --memory 96m \
  -e TS_AUTHKEY="$KEY" -e TS_USERSPACE=false -e TS_STATE_DIR=/tmp/ts \
  tailscale/tailscale:v1.102.3
docker run --rm --network container:zt-drill \
  -v "$PWD/reach.sh:/m.sh:ro" -v "$HOME/targets:/t:ro" alpine:3 sh /m.sh /t
```

Change the tag in the console, measure again, remove the device, and finish
with `docker rm -f zt-drill`. The node removes itself from the tailnet.
