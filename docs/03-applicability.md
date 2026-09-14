# Where this model earns its keep, and where it is ceremony

**What this is.** An argument, not a measurement. Everything else in `docs/` is
either a record of something observed or a decision with its reasoning; this
file answers a question the lab keeps provoking — *what does an enterprise
actually get from this, and is it worth the ceremony?* — and it is written to be
argued with. Where it leans on a number from this lab, the number is linked.

---

## What actually changes, mechanically

In the perimeter model the credential is **location**. Inside the office
network, on the VPN, on a jump host — and from there routing and hand-maintained
firewall rules are all that stand between you and everything else. The rules
accrete, nobody dares delete one, and the concentrator that lets people in
becomes both a bottleneck and a target worth attacking.

Zero trust replaces location with four properties. None of them is new on its
own; the combination is what makes the difference.

1. **Every connection is authorised against an identity** — a person or a
   workload — so being "inside" stops meaning anything.
2. **Deny by default, with explicit grants**, expressed as data rather than as
   thousands of ACL lines spread across devices.
3. **Short-lived credentials.** Certificates and federated tokens instead of
   keys that outlive the reason they were issued.
4. **The state of the device is an input**, not an assumption.

This lab demonstrates all four at small scale: the collector holds
[no cloud key at all](02-decisions.md) and trades a certificate for an hour of
credentials (D-067); the production shell depends on what the device reports
about itself (D-060); and revocation was measured at
[under two seconds](runbooks/lost-personal-device.md), enforced at the
destination, on a device that never learned it had been revoked (D-061).

## What an enterprise gets, in the terms a budget is written in

**Containment of lateral movement.** This is the whole argument. The expensive
part of a modern incident is rarely the first machine; it is the spread from
that machine to five hundred others over file sharing and remote desktop.
Identity-scoped, deny-by-default paths are micro-segmentation that does not
require touching a single switch.

**Joining and leaving become identity operations.** Not firewall tickets. The
second-user drill here measured the difference exactly: a new member of the
network arrives reaching [nothing](runbooks/second-user.md), where under the
previous policy the same person would have arrived holding the house's
automation UI, its shell, production's SSH and a socket in the flat.

**Third parties without network membership.** Contractors, suppliers, and the
company acquired last quarter get an application, not a subnet.

**Remote work without a chokepoint.** Encrypted peer-to-peer paths instead of
hairpinning every session through one appliance that is also the thing everyone
attacks.

**An audit answer that exists.** "Who could reach what, and who did" is a
query, not an archaeology project across firewall configs and netflow.

## Where the ceremony is real

The overhead is roughly fixed and the benefit scales with identities, sites and
the cost of lateral movement. So:

- **Small, static, single-site estates.** One serverroom, few people, no
  contractors: the perimeter is cheap and the policy overhead dominates. Say so
  rather than selling.
- **Devices that cannot run an agent.** Cameras, controllers, printers, most
  smart-home hardware. They end up behind gateways with host routes — the
  awkwardness in this lab's `/32`-per-device arrangement is exactly that, and it
  does not go away at scale, it multiplies.
- **Policy rots like firewall rules do.** Moving ACLs into a file does not stop
  them accumulating; it only makes the accumulation reviewable. Reviewing is
  still work somebody has to do.
- **New dependencies.** A control plane, an identity provider, and the
  operational discipline that goes with them. This lab spent an evening on
  guardrails specifically so that a policy mistake or an experiment could not
  lock the household out of its own house (D-072), and that concern is not
  hypothetical: the tailnet is the only way in.
- **Lock-in.** The policy language, the identity provider and the overlay are
  usually three products from one or two vendors.

## How widespread it is, honestly

Nearly every large organisation reports a zero-trust programme; that is a
statement about slides. The slice that is genuinely widespread is **ZTNA
replacing VPN for remote access** — the easiest, most visible win. Identity
deciding access *inside* the data centre is much rarer, and the common real
state is a hybrid: modern access at the edge, classic segmentation behind it.

Government pushed its own adoption by mandate — the 2021 US executive order and
the OMB memorandum that followed set deadlines for federal agencies — which is
why public-sector case studies are over-represented in the material.

Precise percentages are omitted on purpose. Almost every number in circulation
is vendor-sponsored and each counts a different thing as "adopted".

## The verdict this lab argues for

The advantage is not that zero trust is "more secure" in the abstract. It is
that security becomes **data you can test** — this repository has 9 accepting
and 50 refusing assertions that the real network evaluates against real devices
before any change merges — and that **failures are contained by default**
rather than by the diligence of whoever last edited a firewall.

Both of those matter in proportion to how many people, sites and machines are
involved. In a flat with one operator and thirty devices, most of it is
ceremony — which is the honest reason this lab exists as a demonstration rather
than as a home improvement.
