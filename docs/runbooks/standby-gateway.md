# Runbook — the second way into the house

**Purpose.** The house has one gateway: the automation hub advertises two host
routes, one per exposed socket, and everything to those sockets goes through it.
If it is down, nothing in the action tier is reachable. This is the standby, and
the shape it takes is the point (D-069).

**Status:** policy applied 2026-09-14; the device-side steps below are the
owner's, and the routes are approved only once they are the right ones.

---

## What was there before, and why it was the wrong shape

Two personal devices — a desktop and the media appliance — each advertised the
**whole home /24**, deliberately, as a way back in if the primary gateway was
off, hung, or busy. Neither advertisement was ever approved, so nothing routed
through them; they sat waiting for a click.

Three things were wrong with that as a standby:

1. **Approval is all-or-nothing per prefix.** Turning the standby on meant
   approving the entire subnet — every camera, recorder and appliance on it —
   in the moment when something had already gone wrong.
2. **It would not have worked anyway.** The grant to the socket names
   `via tag:gateway-home`. Traffic through another machine is refused until the
   policy names it too, so the "one click" was a click plus a policy change,
   under stress.
3. **A desktop cannot hold the role.** Tagging a node removes its owner's
   identity, and that machine is somebody's daily computer (the same reason the
   tablet keeps its own — D-068).

## The shape it takes instead

The always-on media appliance carries a second tag, `tag:gateway-standby`, and
advertises **the same two host routes as the primary** — not the subnet. Both
sets are approved in advance. Tailscale treats two nodes advertising the same
prefix as a primary and a standby and moves traffic to the survivor on its own.

So the failover needs no click, no policy change and no widening: what changes
is which machine forwards, and nothing changes about what may be reached.

Being a road is not permission to travel. The same node still holds
`tag:appliance`, and the policy asserts that as a *source* it reaches nothing —
including the sockets it forwards packets to.

## The steps

**On the appliance** (its own screen and remote): Tailscale app → Subnet Router
→ remove the `/24` → *Advertise New Route* twice, once per socket address, each
as a `/32`. The addresses are the two in `local/inventory.yaml`; they are not
written here.

**On the desktop**: turn subnet routing off. Its advertisement was the other
half of the old arrangement and the standby no longer needs it.

**In the console**, once the appliance advertises the two /32s: assign it
`tag:gateway-standby` alongside `tag:appliance`, then approve exactly those two
routes. Approve nothing wider; if a `/24` is still listed, the device step is
not finished.

## Checking it, and the honest gap

With both approved, `tailscale status --json` on an operator device lists the
route and which node is primary. Pulling the primary offline should move it
within a minute or two.

**Not yet measured:** this failover has not been drilled. Until it is, the
standby is a design, not a result — and the page says so rather than drawing a
line that has never carried a packet.
