# Runbook — a second user, and what a group is worth

**Purpose.** Measure what joining, being granted, being suspended and being
restored actually do — on the live network, with a second identity, rather than
from the policy file.

**Status:** run twice on 2026-09-13 — the second time after the grant moved to
a real device (D-059). The test user stays in the tailnet, **suspended between
drills**, so the drill can be repeated without a new invitation.

---

## Before you start

This drill takes access away on purpose. In a house whose only way in is this
tailnet, that is one careless row in a console away from being the wrong
access. So, every time, in this order (D-072):

1. **Name the identity you are about to act on, out loud, and read it back from
   the console row you are about to click.** The test user and the owner sit in
   the same table, two rows apart.
2. **Check that a second path into the house answers** — the standby gateway,
   or a house node other than the one this drill touches. If it does not
   answer, fix that first: the drill can wait, the house cannot.
3. **Confirm the way back exists without the network you are about to disturb.**
   The console is reachable from any browser; the cloud break-glass is
   documented and was exercised. Neither depends on the tailnet.

If any of the three is not true, do not start. A measurement is worth less than
a working house, and the drill will still be there tomorrow.

## Why a second identity at all

Until this drill the lab had one person, and every grant to a person said
"every member of the tailnet". With one member those two are indistinguishable,
which is exactly how the mistake survives. Adding a real second identity is the
only way to find out which one the policy meant — and it turned out to mean the
wrong one, so the grants were narrowed to a group first (D-057).

## The setup

- A second account with its own provider identity, invited to the tailnet as a
  **Member**. The console already required an admin's approval to join.
- A throwaway node registered **as that user**, not with an auth key: a
  container whose login URL the owner opened while signed in as the test user.
  It carries no tag, so it is a person's device, which is what the drill needs.
- One probe, eight destinations: the collector's ingest port, the automation
  hub's UI, shell and broker, production's SSH, the home server's SSH, and both
  smart plugs.

Since the 2026-09-13 run the granted destination has changed: the test user's
one port is the media appliance's, not the collector's (D-059). Re-run the
probe with the appliance in the targets file; the shape of the result — 0, 1,
0, 1 — is what the drill is watching, not which port it is.

A note for whoever repeats this: every Tailscale account gets its own empty
tailnet, so the device-connect screen offers a choice of two. Choosing the
personal one puts the node somewhere harmless and useless.

## Observed — second run, 2026-09-13, ten destinations

The probe now includes the media appliance's AirPlay port, which is the test
user's only grant since D-059, and keeps the collector's ingest port as a
destination that must be refused.

| state | reachable, of 10 | measured |
|---|---|---|
| granted, user active | **1** | the appliance's AirPlay port. It answered — so the grant names a live service, not a hole in a policy file |
| user suspended | **0** | **about 1.6 s** from the click: last open at 22:34:30, first refused at 22:34:32 |
| user restored | **1** | **about 1.7 s** from the click: clicked 22:35:35.3, open at 22:35:37 |
| suspended again, full sweep | **0** | appliance, collector ingest and shell, hub UI, shell and broker, production, home server, both plugs |

Poll resolution is one second, so each figure carries that. Both transitions
were quicker than the first run's ~3 s and ~2 s; with two samples that is a
range, not a trend.

The refusal that matters as much as the acceptance: **the collector's ingest
port is now refused** for this identity. Before D-059 it was the one thing the
test user could reach, and it accepts writes.

## Observed — first run, 2026-09-13, eight destinations

| state | reachable, of 8 | measured |
|---|---|---|
| in the tailnet, in no group | **0** | nothing at all, including the collector |
| added to a group with one grant | **1** | the collector's ingest port, nothing else |
| user suspended | **0** | **about 3 s** from the click |
| user restored | **1** | **about 2 s** from the click |

## What it shows

- **Joining is not being granted.** A person in the tailnet who is in no group
  reaches nothing. Before D-057 the same person would have arrived holding the
  house's automation UI, its shell, production's SSH and a socket in the flat.
- **A group is worth exactly what it names.** One grant, one port, one machine.
- **Suspension is the honest revocation.** It cut access in about three seconds,
  it is done in one place, it does not need the device's cooperation, and it is
  reversible — the account and its machines survive, they simply see nothing.
  For offboarding that is better than deletion: access ends immediately and the
  paperwork can follow.
- **What the drill did not test:** a person whose device is offline at the
  moment of suspension, and what a suspended user can still see in the console.

## Repeating it

The test user stays suspended. To run the drill again: restore the user in the
console, start a node as them, measure, suspend, measure.

**The login is paid.** The node registered on 2026-09-13 keeps its state in the
named volume `zt-testuser-ts` on the cloud dev host, so the next run starts it
with `docker start zt-testuser` and needs nobody's browser. The paragraph below
is why that matters and what the first two runs cost.

**Budget for a browser login.** The two nodes from the first run still appear
in the console under the test user, but they are dead: the container kept its
tailnet state in `/tmp` inside itself, so removing the container destroyed the
node key and left two stale registrations behind. Re-running therefore needs
the test account signed in to a browser again — which is a person's hands, not
a script's. The fix is one flag: put the state in a named volume
(`-v zt-testuser-ts:/var/lib/tailscale --state=/var/lib/tailscale/ts.state`)
and the node survives the container, the way the collector's does. Do that on
the next run and the one after it will need no login at all.

The container:

```bash
docker run -d --name zt-testuser --hostname zt-testuser \
  --device /dev/net/tun --cap-add NET_ADMIN --cap-add NET_RAW --memory 96m \
  --entrypoint /usr/local/bin/tailscaled tailscale/tailscale:v1.102.3 \
  --state=/tmp/ts.state --socket=/var/run/tailscale/tailscaled.sock --tun=tailscale0
docker exec -d zt-testuser tailscale up --hostname=zt-testuser --accept-dns=false --timeout=0
docker exec zt-testuser tailscale status     # prints the login URL to open
```

The image's normal entrypoint gives up on the login after a minute, which is
shorter than a person takes; running `tailscaled` directly removes the
deadline. Measure with [`collector/reach.sh`](../../collector/reach.sh) and a
targets file kept off the repository.
