# Threat model

Generic and publishable by design. It names actors, asset classes, what the
architecture defends against and — more usefully — what it provably does not.

The specific findings this is drawn from live in the private overlay. Which
device is exposed, on which port, and what that leaves reachable is an attack map
for one particular house; the generic document is the one worth reading anyway.

---

## What this system is

A home network carrying a household's daily infrastructure, used as a working
model of a distributed field-operations topology: a telemetry sink, sensors that
cannot run an agent, a gateway per site, and operator devices of varying trust.
Access between nodes is mediated by a mesh VPN with a central policy file.

## Actors

| Actor | Capability assumed |
|---|---|
| **Household member** | Physical access, daily use of the automation UI, no interest in the lab |
| **Operator** | Admin of the tailnet and the policy file; the only actor who changes the model |
| **Remote attacker with a leaked credential** | Can register a node onto the tailnet. Inherits whatever an unprivileged tagged node is granted |
| **Attacker already on the local network** | A guest, a compromised device, someone within radio range of the WiFi. **Bounded only by the LAN, not by any policy here** |
| **Device vendor** | Receives whatever the device sends to its cloud. Not constrained by anything in this repo |

## Asset classes

- **Physical state** — actuators that switch mains power. The only class where a
  compromise changes the world rather than disclosing it.
- **Streams** — camera video. Disclosure of the interior of a home.
- **Telemetry** — sensor readings. Low value alone; a reliable occupancy oracle
  in aggregate.
- **Control planes** — the automation platform, the broker, the site gateway's
  administration interface. Compromise of any one yields the classes above.
- **Credentials** — tailnet auth keys, cloud federation trust, the policy file
  itself.

---

## What the architecture defends against

**Remote access is deny-by-default and per-port.** Reaching a device across the
tailnet requires a grant naming a source role, a destination and a port. The
default state grants nothing.

**Machine identities are not people.** Infrastructure nodes authenticate as
roles, not as a person's account, so revoking a person does not strip
infrastructure and compromising a person's device does not inherit
infrastructure's reach.

**The exposed set is explicit and small.** Devices that cannot run an agent are
reachable only through per-host routes on a gateway, enumerated one at a time.
Exposure is a decision with a name attached, not a side effect of a subnet being
routable.

**Policy changes are tested before they take effect.** Assertions live beside the
rules; a change that would break a household path or silently widen access fails
before it applies.

**Recovery does not depend on the thing being recovered.** The administration
console is reached over the public internet, so a policy that breaks the tailnet
cannot lock the operator out of the place where it is undone. This was verified
by test, from a phone with the tailnet off, not assumed.

---

## What it provably does not defend against

This section matters more than the one above. A reviewer who finds these gaps
unaided will not trust anything else here.

### 1. Anything already on the local network

The network is flat. There is no separate segment for appliances, and building
one would fight the household's own direction of travel — the discovery protocols
its smart-home devices depend on do not cross subnets without a reflector.

Access policy governs **tailnet-originated** traffic. A device already on the
local network reaches every other device on it directly, regardless of any rule
in this repository. **The lab demonstrates control of remote access, not
segmentation.**

Everything below is a consequence of this one fact.

### 2. An actuator that authenticates nothing

One of the actuators answers its vendor's local control interface, over
plaintext, to a request signed with an **empty key** — returning hardware detail,
the owning account, and live physical state. Its physically identical twin, same
firmware, rejects the same request. Device security here is an accident of
provisioning, not a property of the model.

**Adopting it onto a managed platform did not close this.** That was tested
afterwards. The encrypted, authenticated protocol the platform uses runs
*alongside* the vendor's interface and is indifferent to it.

So the network control is not a stricter layer over a device that was already
safe — **it is the only control that exists**. This is the concrete argument for
putting physical-state changes behind source posture and a time-boxed grant.

### 3. Vendor cloud traffic

Several devices hold outbound sessions to their manufacturers. A mesh VPN secures
traffic *between its own nodes*; it does not stand between a device and the
internet. A robot vacuum on this network reaches its vendor under every policy in
this repository, and so does the actuator above.

This is not a gap to be closed with more grants. It needs egress filtering, which
is a different control at a different layer.

### 4. A broker inherited, not designed

The message broker predates the lab and carries dependencies that did not consent
to it. It listens on all interfaces in plaintext; credentials are required, but
the transport is not protected. Binding it to the private interface would break
working clients.

**It stays as it is.** The lab uses its own credentials and its own topic prefix
and changes nothing else. Inheriting a system you are not entitled to redesign is
the normal condition of this work; reporting the residual risk honestly is the
correct output, and quietly removing it would be a worse result than leaving it
named.

### 5. Availability of the single gateway

Exposure was deliberately narrowed to one gateway node. That concentrates a
dependency: if it is down, every non-agent device is unreachable remotely.

A redundant route server was declined on purpose. The candidate was the node the
model most wants to originate nothing, and the redundancy would have outlived its
own usefulness — the actuator's control plane is the gateway itself. **The
property that makes a node a good failover router is the property that makes it a
poor thing to trust.** Availability and least privilege genuinely conflict here;
this is the trade made, not an oversight.

### 6. Route acceptance is a client-side setting

Whether a node uses an advertised route is decided by that node. A setting the
restricted party controls is not an access control. With grants in place the
policy constrains what the route can carry — but the route's *reachability* is
not something the control plane enforces.

### 7. Physical access, and the radio layer

Out of scope entirely. Devices speaking low-power radio to a border router have
no IP presence and no key; there is nothing to revoke and nothing to grant.

---

## Known-good properties worth stating

- **No long-lived cloud access key** exists in the lab; federation is by
  short-lived credential.
- **The disclosure boundary is enforced by CI**, not by discipline — a commit
  containing a real address, hostname, account identifier or credential format
  fails the build.
- **The rollback target is byte-verified**, and reaching the place it is applied
  from was tested from a device that shares nothing with the one that captured
  it.

---

## Deliberately not fixed

Recorded here so that the absence of a fix is legible as a decision:

| Finding | Why it stays |
|---|---|
| Broker plaintext on the local network | Rebinding breaks clients that predate the lab |
| Actuator's unauthenticated local interface | It is the subject of the lab, not a defect to patch; and it is what justifies the strictest tier |
| Vendor cloud egress | Wrong layer; needs egress filtering, not grants |
| Flat network | Would fight the household's smart-home direction; a segmentation project in its own right |
| Single gateway | The redundancy available was worse than the dependency |
