# Runbook — a personal device is lost

**Purpose.** A machine role losing its access was measured in Phase 5: about
1.6 s from removing the device. The half that matters for a lost phone is
different — the identity belongs to a *person*, the device may be switched off
in a stranger's pocket, and it may never hear that anything happened. This
measures that half.

**Status:** run on 2026-09-13, on the live network, with the test user's node
standing in for the lost device (D-061).

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

## What is actually being asked

When a phone goes missing, three things are unknown and only one of them is
under anyone's control:

1. Whether the device is online when the revocation is issued.
2. Whether it will ever receive the revocation.
3. Whether the network refuses it anyway.

The reassuring answer to (3) is the only one worth having, because (1) and (2)
belong to whoever has the phone. So the drill removes the device's cooperation
deliberately, rather than assuming it.

## Setup

- The lost device is `zt-testuser`, a node registered to a person (the test
  user), not a tagged machine. Its one grant is the media appliance's AirPlay
  port (D-059), which is the destination probed throughout.
- Revocation is **user suspension** in the console — the action the offboarding
  runbook recommends, done in one place, reversible.
- The probe is one TCP connection per second, run inside the node's network
  namespace.

## Observed

### Case 1 — the device was offline when the user was suspended

| step | time |
|---|---|
| device stopped | 22:51:18 |
| user suspended while it was off | 22:51:30 |
| device started again | 22:51:43 |
| first probe after boot | 22:51:45 — **refused** |
| polled for a further 60 s | refused throughout |

**No window.** A device that missed the revocation does not get a grace period
on the way back; it is refused from the first packet it is able to send.

### Case 2 — the device never learned it was revoked

The node was cut off from the control plane first (`192.200.0.0/24` dropped in
its own OUTPUT chain), so it could not receive an updated policy or netmap,
while the peer-to-peer data path stayed up. That the cut did not break
connectivity is the control for this measurement: with the block in place and
the user active, the appliance still answered, over a **direct** path rather
than through Tailscale's servers.

| event | time |
|---|---|
| last successful connection | 22:55:36 |
| suspend clicked | 22:55:37.4 |
| first refusal | 22:55:38 |

**Under two seconds, with the revoked device none the wiser.** Its own status
output still listed the appliance as an active peer, with traffic counters, at
the moment every connection was being refused.

The enforcement is at the destination. The appliance received the new netmap
and stopped accepting the peer; nothing was asked of the device that had been
taken away. This is the property that makes suspension a real revocation rather
than a request.

### Case 3 — restoring, also without the device hearing it

Still cut off from the control plane, the user was restored: the appliance
began answering again within the poll interval. The destination re-admits on
the same evidence it used to refuse — the control plane's word, not the
device's.

## What this does not cover

- **A stolen browser session.** Suspension stops the device and the person's
  other machines. It does not, by itself, stop someone holding an unlocked
  phone from signing in to the identity provider and registering a *new* node,
  if that provider's session is still valid. That is an account action at
  Google or Apple, not a tailnet action, and it belongs in the offboarding
  runbook rather than here.
- **Disk encryption on the lost device.** The posture attribute says the
  tailnet state is encrypted at rest; it says nothing about the rest of the
  phone.
- **A device that is lost while a session is already open.** Every measurement
  here is a new TCP connection. An established SSH session surviving a
  revocation is a separate question, and it is not answered here.

## Repeating it

The node's state lives in the named volume `zt-testuser-ts` on the cloud dev
host, so no browser login is needed:

```bash
docker start zt-testuser
docker run --rm --network container:zt-testuser -v /tmp/reach.sh:/m.sh:ro -v /tmp/targets.txt:/t:ro alpine:3 sh /m.sh /t
```

Cut the control plane inside the node with
`iptables -I OUTPUT -d 192.200.0.0/24 -j DROP`, and remove the rule afterwards.
Leave the test user **suspended** when finished; that is its resting state.
