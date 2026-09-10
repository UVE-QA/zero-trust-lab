# Decisions

ADR-style, append-only. Why, not just what. Newest last.

---

## D-001 — The tailnet policy file is owned by GitOps, not Terraform

**Status:** accepted (inherited from the handoff, recorded here as required)

The policy file is a single global document. Tailscale publishes an official
GitOps action for it. Terraform owns AWS only, with state in S3 and locking.
Two systems writing the same global file will fight, and the loser's writes
disappear silently.

---

## D-002 — Sanitisation is enforced by CI, not by discipline

**Status:** accepted, implemented in Phase 0

`scripts/leak-sweep.sh` runs on every PR and refuses any tracked file
containing a tailnet or private LAN address, a MagicDNS domain, a twelve-digit
account id, a MAC address or a credential format. Site-specific strings —
node names, the tailnet name — reach CI through the `LEAK_DENYLIST` repository
secret, so the denylist never enters the repo, and a match reports its location
without echoing the term.

**Why a test and not a checklist.** Git history is permanent. "We will clean it
before publishing" means rewriting history, which is unreliable and visibly
awkward. The sweep earned its place immediately: while this commit was being
drafted it caught a real hostname that had been left in the placeholder example
file.

The sweep reads `git ls-files`, so the gitignored `local/` overlay is never
opened. Run it locally before committing — CI catching a leak on a pushed commit
is already too late.

---

## D-003 — Finding: an approved `/24` route into the home LAN is already live

**Status:** open. Recorded in Phase 0, deliberately not acted on.

A user-owned personal desktop advertises the entire home LAN as a subnet route,
and the route is approved and in use. With no access rules defined, Tailscale's
default is allow-all. The two together mean **every tailnet node already reaches
every device on the home LAN** — including the media appliance the design wants
isolated, and including any node that a leaked auth key could register.

Three consequences:

1. **Phase 1.5 is a migration, not a build.** The handoff frames the gateway
   role as unassigned. It is not: it is de facto held by the machine the handoff
   explicitly rules out as a gateway, because that machine is another
   household member's daily workstation and has to stay user-owned so it can
   serve as a posture subject. Moving the role to the automation hub is now a
   prerequisite rather than a preference.
2. **Whoever holds the gateway role sets the blast radius.** This is the
   argument for the taxonomy in `policy/README.md`, made concrete.
3. **Retiring the route is a change with household consequences.** It can remove
   remote LAN access for people who use it daily. It needs the owner's explicit
   go-ahead and a rollback note before it is touched — which is also why it was
   not touched during a capture phase.

This is the strongest available argument for the deny-by-default work: the
starting state is not "no policy", it is "an implicit policy of full access,
routed through someone's desktop."

---

## D-004 — Finding: the inherited MQTT broker stays as it is

**Status:** accepted. Residual risk documented, not remediated.

The broker was located rather than assumed. It runs on the node that will carry
`tag:gateway-home`, answering MQTT on the standard plaintext port on **all**
interfaces — tailnet and LAN alike. Anonymous connections are refused, so
credentials are required. There is no TLS listener.

**What this settles.** The grant direction is the first of the two the handoff
left open: the collector subscribes across the tailnet to the gateway. No broker
move is needed, and the "collector role temporarily on a user-owned node"
problem does not arise.

**What is deliberately not fixed.** Plaintext on a flat LAN, reachable by
anything already on that network. Binding the broker to the tailnet interface
would break the NVR and the automation hub, which are existing clients that
predate this lab and did not consent to it. Per the handoff's own rule, no
reconfiguration is made that affects an existing client.

So the exposure is recorded in `docs/00-threat-model.md` as a finding rather
than removed. Inheriting a system you are not entitled to redesign is the normal
condition of the work this lab models; reporting the residual risk honestly is
the correct output, and quietly removing it would be a worse result than leaving
it in place with a name.

The lab gets its own credentials and its own topic prefix, and changes nothing
else.

---

## D-005 — Finding: the actuator publishes no mDNS name, so Option B does not cover it

**Status:** open. Found during Phase 0 capture; changes a Phase 1.5 decision.

The handoff resolves the flat-network problem with Option B — stop addressing
devices by IP, resolve them by mDNS hostname instead — and states that the
chosen WiFi actuator is covered directly, because HomeKit accessories advertise
over Bonjour.

**That is not what the network shows.** A 12-second browse for the HomeKit
accessory service returns zero instances anywhere on the LAN, and neither
candidate host answers a reverse mDNS query. Both are powered and serving HTTP;
they simply publish no name.

Option B's own second verification step is this exact check, and its stated
fallback applies: a device that does not register a hostname cannot use Option B
and falls back to C or D. Option C — a static address set on the device — is
weak here, because the site gateway is not ours and its DHCP pool may span the
whole subnet with no way to shrink it. That points at **Option D**: reconcile
addresses from the automation hub, which already tracks every device it manages.

With one complication: the hub does not currently manage this device either. So
D needs the device adopted into the hub first, which is the same prerequisite
the qualification checks were already blocked on.

**Method note, because it nearly produced a wrong answer.** The first browses
were redirected to a file and came back completely empty — no service listing
*and no header line*. That is an output-buffering artifact, not a result. Re-run
under a pty the header appears and the instance list is genuinely empty. An
empty capture that is missing its own header is not evidence of absence; check
for the header before believing it.

**Not acted on.** Phase 0 is capture, and this is the owner's decision.

### Related, deliberately not concluded

The open HTTP port on those hosts looks more like the vendor's standard firmware
than the HomeKit variant. If that were confirmed it would reopen the
local-LAN-integration option that the handoff rules out — the ruling rests on
the HomeKit variant enforcing strict TLS. But this is an inference from a 404
page and a MAC prefix, not an identification. It is recorded so it is not lost,
and it must be confirmed against the physical device before anything is built on
it.

### What was ruled out

Every Matter actuator already known to the hub is Matter-over-Thread, verified
per node from its own diagnostics rather than inferred from the product. None is
an IP host, so none can stand in for the WiFi actuator, and the handoff's choice
survives the check. The one Matter-over-WiFi node is a camera bridge — not a
spare, and not an actuator.

Incidentally, those Thread devices are joined to three administrative fabrics at
once. Matter permits that; the HomeKit accessory protocol does not, which is
precisely why the WiFi socket has to be unpaired from one ecosystem before
another can drive it, and why the Thread devices did not.

---

## D-006 — The baseline is byte-exact, and the scanner bends around it

**Status:** accepted, done

`policy/policy.baseline.hujson` is the rollback target. It was verified
byte-identical to what the tailnet was serving by comparing a SHA-256 computed
in the console page against the committed file — not by reading it and trusting
the transcription.

The captured file is the **stock default, never modified**: a single
`{"src":["*"],"dst":["*"],"ip":["*"]}` grant, plus Tailscale SSH in check mode
to `autogroup:self` as root. Since every node belongs to one user,
`autogroup:self` is the entire tailnet. So the starting state is not merely
"no policy" — it is full mesh access plus root SSH between all of the owner's
machines, and, through the live subnet route in D-003, onward to every device
on the home LAN.

**The scanner conflict.** The stock template embeds Tailscale's own example
address inside a commented-out `tests` block. That address is in the CGNAT
range, so the disclosure sweep's tailnet-address rule matches it.

Two ways out, and only one of them is right. Editing the file to please the
scanner would make the rollback target something other than what the tailnet
actually served — which destroys the only property that file has. So the
scanner carries the exception instead: `scripts/leak-sweep.sh` blanks that one
literal before matching.

The exception is written to suppress **the literal, not the line**, and there is
a test for it: a line containing both the vendor example and a real address
still fails the build. An allowlist is the one place a scanner like this can be
talked into missing something, so it stays tiny and every entry is justified
where it is defined.

---

## D-007 — Correction: D-005 was wrong. The actuator does publish an mDNS name.

**Status:** accepted. **Supersedes the central claim of D-005.** D-005 is left
standing above because this file is append-only and a retracted finding is more
useful than a deleted one.

### What D-005 claimed, and what is actually true

D-005 reported that the chosen actuator publishes no mDNS name, concluded that
Option B's second verification step had failed, and pushed Phase 1.5 toward
Option D. **That conclusion was an artifact of the measuring tool, not a
property of the network.**

A direct multicast DNS query — a PTR question sent to the mDNS group and the
responses parsed in-process, with no shell tooling between the wire and the
result — returns eight HomeKit accessory instances on this LAN. **Two of them
are the actuator units**, matched to the hardware addresses found earlier by
vendor prefix. Each resolves to a hostname, each hostname resolves to the
device's current address, and the accessory port is open on both.

So Option B's requirement is met: these devices have stable names that survive a
lease change, which is exactly what the flat-network workaround needs.

### How the wrong answer happened

The service-discovery CLI buffers its output when stdout is not a terminal. A
browse that finds instances writes enough to flush; a browse that finds nothing
writes only a short header that never leaves the buffer and is lost when the
process is killed. The result is an empty file that looks identical to a
genuine "nothing is advertising."

The guard added after the first occurrence — treat a capture with no header line
as invalid — was necessary but **not sufficient**. It cannot distinguish "the
tool never flushed" from "the tool ran and found nothing," because both produce
a headerless empty file. A later attempt to force a terminal failed outright
with an ioctl error on a socket, and that failure was itself nearly read as
another zero result.

**The rule that actually works:** do not infer absence from a tool that can fail
silently. Establish the tool works by making it find something known to exist,
in the same invocation style, or bypass it and speak the protocol directly. The
browse for a known-present service returning results is the control; without a
control, an empty result is not evidence.

### What this changes

- **Option B is viable** for the actuator, and by extension the mDNS-based
  approach is not disqualified for the other non-tailnet devices. Phase 1.5
  should evaluate it on its merits rather than falling back to Option D because
  of a broken measurement.
- **mDNS is healthy on this LAN**, verified against several services known to
  exist. Any future claim that a device is not discoverable needs the same
  control.
- The rest of D-005 stands: every existing Matter actuator is Thread-attached
  and none is an IP host, so the WiFi actuator remains the only candidate for
  the action tier.

### The firmware question is also settled, against my earlier inference

D-005 noted an open HTTP port and suggested it pointed at the vendor's standard
firmware rather than the HomeKit variant — which, if true, would have reopened
the local-integration option the handoff rules out.

**It is the HomeKit variant.** The accessory records advertise the model, an
accessory category of "outlet", and a HomeKit protocol version. The HTTP port is
present on this firmware too, so it never distinguished the variants. The
handoff's reasoning in §5 stands unamended and the local-integration route stays
closed.

Both units also report a status flag of paired — they are bound to a controller
already, consistent with the handoff. Adoption therefore does require unpairing
first; it is not a case of a free device waiting to be claimed.

### Standing correction to the method notes

"Verify by digest, not by reading" was already recorded. Add: **verify a
negative result against a positive control.** Two findings in this phase were
nearly wrong in the same direction, both because a silent tool failure reads
exactly like a real absence.

---

## D-008 — What the subnet route is actually load-bearing for: almost nothing

**Status:** measured. Amends D-003 with evidence. **The route is still not
touched.**

D-003 recorded that an approved subnet route into the home LAN is live and that
the effective policy is allow-all. This entry answers the question that follows:
if the route were withdrawn, what would break?

### Method

Every live host on the LAN was enumerated and port-profiled from an on-LAN host,
then classified into two groups: hosts that are already tailnet nodes in their
own right, and hosts that are reachable *only* through the route. The second
group is the only thing the route buys.

### Result

**Everything the household actually uses remotely belongs to the first group.**
The automation UI, the NVR, and the operator machines are each tailnet nodes at
their own address; traffic to them never traverses the subnet route. The camera
streams are consumed by the NVR, which sits on the LAN itself. The actuators are
driven by a hub that is also on the LAN.

The second group — devices reachable only via the route — consists of appliances
that nothing remote depends on, plus one item that matters:

**The site gateway's administration interface is exposed to the entire tailnet.**
It is the control plane for the whole network, and the route publishes it to
every node that accepts routes — including the media appliance the design wants
isolated, and including any node that a leaked auth key could register. Remote
administration of the site gateway is the only capability the route genuinely
provides, and it is a liability rather than a feature.

**So withdrawing the route should be close to free.** That is the opposite of
the assumption the phase plan was built on, and it is worth knowing before the
migration is designed rather than after.

### Whether the route is *used* is a client-side toggle, and that is the point

Accepting an advertised subnet route is a per-client setting. The operator
laptop was verified to have the route installed on its tunnel interface; a Linux
node was verified not to. Apple platforms accept routes by default, so the nodes
most likely to be carrying the whole home LAN are the appliances and handhelds,
not the servers.

**A setting the receiving node controls is not an access control.** The node
being restricted is the one deciding whether the restriction applies, and it
flips with one command. With an allow-all policy there is nothing else in the
path. This is the clearest statement of the problem the project exists to fix:
the current arrangement is not a weak policy, it is the absence of one, with a
client-side convenience toggle standing in for it.

### Ordering — corrected

The route was previously treated as the lever that fixes D-003. It is not.
Migrating the gateway to another node changes *which* node advertises the route;
with the policy still allow-all, the exposure afterwards is identical.

The policy is the lever. Revised order:

1. **Phase 2 first, route untouched.** A deny-by-default policy constrains who
   may use the route without removing it — one commit, reversible with one
   revert, and it collapses the exposure to what is explicitly granted.
2. **Then the gateway migration**, with both nodes overlapping.
3. **Then withdraw the route**, once the narrow paths are proven.

That sequence never removes household access before a replacement works, and it
reduces real exposure considerably earlier than withdrawing the route first
would.

### Not done, deliberately

Confirming the exposure end-to-end from an off-LAN node requires enabling route
acceptance on that node, which temporarily widens what it can reach. That is a
change to a node's configuration made in order to demonstrate a weakness, so it
was not done unilaterally.

---

## D-009 — The blast-radius measurement uses a disposable node, not a trusted one

**Status:** accepted. Execution deferred to the Phase 2 window — see
`docs/runbooks/blast-radius.md`.

D-008 established what the subnet route exposes, measured from inside the LAN.
The open question was how to confirm it from outside, where no local path can
confound the result.

The obvious instrument was an existing off-premises node: enable route
acceptance on it, measure, turn it back off. **Rejected**, for three reasons
that are worth keeping because they generalise.

**1. An undo step is a step someone can forget.** The risk in "turn it straight
back off" is not the interval of widened reach — it is that the undo depends on
a person remembering it while distracted by the result they just got. An
ephemeral node deletes itself when it stops. There is no undo to forget, so no
exposure outlives the measurement. Prefer a mechanism that cannot be left half
done over a procedure that must be completed correctly.

**2. It would measure a weaker claim than the one being made.** The finding is
that *any node a leaked auth key could register* already reaches the whole home
LAN. A node registered with an auth key, accepting routes, **is** that scenario.
Demonstrating instead that a node already trusted can reach the LAN proves
something less interesting and is easy for a reader to wave away. Measure the
claim, not a proxy for it.

**3. It exercises the fleet tooling early**, on a task small enough that getting
it wrong is free — and that tooling is needed for later phases anyway.

The disposable node runs on the off-premises host, so the property that made
that host attractive is preserved: it has no local path to the home LAN either,
and the result is just as unconfounded.

### The sequencing hazard — the part that must not be got wrong

Deferring the measurement into the Phase 2 window creates one trap.

**The "before" reading only exists while the tailnet is still allow-all.** Both
readings therefore have to sit in a single window around the policy apply: bring
the node up, measure, apply the policy, measure again, tear the node down.

**Do not let the policy land first and plan to reconstruct the baseline
afterwards.** Reverting a production tailnet to allow-all in order to take a
reading is a far worse act than anything this decision is weighing — it would
deliberately re-expose a household network for the sake of a number. If the
before-reading is missed, it is missed; write that down and move on with the
after-reading alone.

### Cost control

Every node in the fleet consumes a tagged resource, and the plan in use caps
them. Teardown is not housekeeping — it is what keeps the cap from blocking
unrelated work. This is the first exercise of that discipline.

---

## D-010 — Two actuators, used as a granted/denied pair rather than one plus a spare

**Status:** accepted. Both units confirmed by the owner as free for the lab and
not needed by the household.

The plan assumed one actuator with a second held in reserve. Both are available,
and a matched pair is worth more than a spare.

### What the pair buys that one device cannot

With a single actuator the strongest available demonstration is temporal: the
path works inside a just-in-time window and fails outside it. That is real, but
a sceptical reader can ask whether anything was ever actually constrained, or
whether the window simply toggled the whole class of traffic.

With two **identical** devices — same model, same protocol, same port, same
segment, both reachable only through the gateway — the grant names one host and
the assertions prove the other is unreachable. Same everything, different
outcome, at the same instant. That demonstrates the property that actually
matters: least privilege here is **per host**, not per protocol or per device
class. It is the difference between "the door was locked at night" and "this
door is locked and the identical one beside it is not."

### Role assignment, and why each way round

- **The granted actuator** is the unit with no history of address instability.
  The primary demonstration should not rest on the device known to wobble.
- **The denied control** is the unit that has previously fallen back to a
  link-local address, so it does double duty as the live example behind the
  availability finding about unreliable addressing on a network whose DHCP we
  do not control.

### The control needs no changes at all

This is the part worth noticing. The denied device does not need to be adopted
by the automation hub, or unpaired from anything, or reconfigured. For policy
purposes it already is exactly what it needs to be: an IP host of the right
class on the right port behind the gateway. The policy simply does not grant it.

So the pair costs **one** device change rather than two, and the household side
of the second device is left entirely alone — which is the standing rule for
anything in this environment, and here it happens to also be the better design.

### Consequence for Phase 2

The `tests` section gains a pair of assertions that were not previously
possible: the granted host accepted, the control host denied, on the same port
from the same source. Those belong in the first policy commit, alongside the
household-access assertion, because they are what makes the actuator tier a
demonstration rather than an assertion.

---

## D-011 — Finding: the granted actuator authenticates nothing on the local network

**Status:** open finding. Goes into the threat model. **Not remediated** — it is
the subject of the lab, not a defect to quietly patch.

While identifying which physical unit was which, one of the two actuators
answered its local HTTP API — over plaintext, on the standard port — to a
request signed with an **empty key**. It returned full system detail
unauthenticated: hardware and chip type, hardware address, firmware version,
the vendor's cloud endpoint, the owning account id, the bind id, and the current
on/off state.

The second, physically identical unit on the same firmware **rejects** the same
request with a signature error. Two identical devices, different security
posture, cause unknown — most likely differing bind history. That asymmetry is
itself worth keeping: it means device security here is not a property of the
model, it is an accident of provisioning, which is precisely why a network
control cannot be replaced by trusting the device.

### The inference, marked as an inference

Reads and writes are signed the same way, so a **write** — switching the socket
— would very likely also be accepted. **This was not tested.** Testing it means
changing physical state to prove something already sufficiently evidenced, and
nothing in the plan requires the proof. It is recorded as a strong inference
rather than a demonstrated fact, and if it is ever tested it should be on a unit
driving nothing, deliberately and on purpose.

That distinction matters here more than usual: this phase has already retracted
one finding that was asserted more confidently than the evidence supported.

### Why this is the lab's best argument, not its worst problem

The handoff's case for the action tier is that a cheap WiFi actuator on a flat
network is exactly what least privilege is meant to contain. This is that claim
with evidence behind it: the only thing standing between anything on the local
network and a physical state change is **network reachability**. The device
contributes no meaningful authentication of its own.

So the controls are not theatre. Posture plus a time-boxed grant is not a
decorative extra tier applied to a device that was already safe — it is the
entire defence. A reviewer who wants to know why the action tier deserves
stricter treatment than the telemetry tier now has a concrete answer.

### What is deliberately not done

The device is not reconfigured, its key is not changed, and its cloud session is
not interfered with. It also holds an outbound session to its vendor's cloud,
which no policy in this repo touches — the same limitation the robot vacuum
illustrates, now present on a device that *is* in scope. Both belong in
`docs/00-threat-model.md` as findings.

### D-011 addendum — 2026-09-09: the unauthenticated read is live, not static

Recorded as an addendum rather than an edit, since this file is append-only.

While establishing which physical unit was which, a positive control was run
that also strengthens this finding. Switching the accessory through its normal
control path — the home ecosystem's hub, over the accessory protocol — was
immediately visible through the **unauthenticated** local HTTP interface, with a
current timestamp.

So the exposure is not limited to static disclosure of hardware and account
details. Anything on the local network can **monitor the actuator's physical
state in real time**, without credentials, and learn when someone switched it
and when.

That also raises the confidence of the write inference recorded above — the
unauthenticated interface is demonstrably live and authoritative about state,
not a stale cache. The write is **still not tested**, and still should not be
tested merely to make the point.

The methodological note is worth keeping too. The identification initially
rested on a negative — one unit *not* changing — with no control behind it.
Taken at face value it happened to be right, but it was unsupported: the local
interface and the accessory protocol are separate control planes, and had the
first not reflected the second, the same reading would have appeared regardless
of which device was switched. The control cost one extra step and converted a
guess into evidence. Same lesson as D-007, applied before the mistake rather
than after it.

---

## D-012 — The gateway-vantage discovery check is closed, and it closed itself

**Status:** resolved. Closes the item left open by D-007.

D-007 corrected a wrong finding about the actuator's discoverability, but left
one thing genuinely unresolved: every measurement had been taken from the
operator laptop, while the check as specified says to test from the gateway.
An attempt to settle it directly was abandoned as inconclusive and recorded as
such, because the only evidence available at the time was a negative with no
control behind it.

It is now resolved, and it resolved as a side effect of work that had to happen
regardless. When the actuator was released from its previous controller, the
automation hub — the node that will carry the gateway tag — immediately raised a
pairing flow for it **sourced from zeroconf**, naming the accessory and its
category.

That is the check, from the right vantage point, answered by the system itself:
the gateway receives the actuator's multicast announcements and resolves it by
name. Option B is viable at the node that actually has to do the resolving,
which is the only place the answer mattered.

**The process point is worth more than the result.** The honest move when the
direct attempt failed was to record it as open with the reasons, rather than
either asserting the likely answer or spending effort forcing a shell onto the
gateway. Both alternatives were available and both were worse: one repeats
D-007, and the other buys with real effort what patience got for nothing. An
open item with a stated resolution path is not a loose end — it is a cheaper
plan.

### Remaining step, and why it is not taken here

Adoption is one action from complete: the pairing flow is live and waiting on
the accessory's setup code. That code is a pairing secret printed on the device,
and entering it is left to the owner in the hub's own interface. There is
nothing to gain from routing a credential through this session, and the step
takes them seconds.

---

## D-013 — The actuator is qualified, and adopting it did not close the hole

**Status:** Phase 0 actuator qualification **complete**. All three checks pass.

The actuator was released from the previous ecosystem and adopted by the
automation hub. Qualification now reads:

| Check | Result | How |
|---|---|---|
| Transport | **pass** | HomeKit-over-WiFi, an ordinary IP host with an open accessory port — read from its own advertised records, not inferred from the product |
| Local control | **pass** | The integration's declared class is *local push*: no cloud polling, no vendor round trip |
| Name resolution | **pass** | Resolves by name, verified from the operator host **and** from the gateway itself (D-012) |

The local-control result was predicted to be a formality, and it was. It was
still read off the integration's own manifest rather than asserted. This phase
has already paid once for an assumption.

### The finding survives adoption, and that is the point

D-011 recorded that this unit answers its vendor HTTP interface, over plaintext,
to a request signed with an empty key. That was re-tested **after** the device
was paired to the hub.

**It still works.** Pairing the device to a platform we control did not close
it. The accessory protocol layer is properly encrypted and authenticated, but
the vendor's own interface sits alongside it and is indifferent to who the
controller is.

This is worth more than the original finding. The intuitive move — "we brought
it onto a platform we manage, so it is handled now" — is **false comfort**. The
pairing is not the control. A second, unauthenticated control plane remains on
the device, and nothing about adoption, the accessory protocol, or the choice of
controller touches it.

What *can* touch it is reachability. Which is precisely the argument for putting
the action tier behind a host-specific grant, source posture and a time-boxed
window: those constrain who can open a socket to the device at all, and that is
the only layer with any authority over the interface the vendor left open.

So the action tier is not a stricter control applied to a device that was
already safe. It is the only control that exists.

### Consequence for the threat model

`docs/00-threat-model.md` should carry this as a worked example rather than a
line item: an inherited device, brought onto a managed platform, still exposing
an unauthenticated path — and the network being the only place that is
answerable. It pairs naturally with the vendor-cloud limitation already noted,
since the same device also holds an outbound session no policy here touches.

---

## D-014 — The break-glass path does not work. Phase 2 is blocked until it does.

**Status:** open, **blocking**. This is the most consequential finding of
Phase 0.

The handoff requires, before any policy work: confirm the admin console is
reachable from a phone that is off the tailnet. The reasoning is that the
console is reached over the public internet rather than over the tailnet, so a
bad policy cannot lock anyone out of the place where it gets undone.

**The console is reachable. It is not authenticable.**

### What was measured

The phone was taken off the tailnet, and that precondition was **verified rather
than accepted**: the coordination server reported the node offline across
repeated polls with a frozen last-seen time, a tailnet-level ping timed out, and
ICMP got no reply. Only then was the test run.

The console page loaded. Sign-in failed, and the device's own credential sheet
stated that **no passkey for this site exists on the phone**, offering only two
fallbacks: scan a QR code using another device, or present a hardware security
key. Neither is a recovery path. The first requires the very machine that an
incident may have made unavailable; the second requires hardware that does not
exist here.

### Why this blocks Phase 2 rather than being a to-do

The rollback target was captured first, byte-verified, and committed, precisely
so that a bad policy could be undone. That work assumed the console could be
reached to apply it. **A rollback target that cannot be reached is not a
rollback target** — it is a file.

The failure mode is specific and plausible: apply a restrictive policy, discover
away from home that something broke, and find that the only device able to
authenticate to the console is the laptop at home. The tailnet being broken is
the scenario, so "connect to the tailnet and use the laptop" is not available.

So the safety net the handoff asks for does not currently exist, and the first
restrictive policy must not be applied until it does.

### Remediation, in order of preference

1. **Register a second passkey bound to the phone.** Two independent devices,
   each able to authenticate alone, neither depending on the other. Adds no
   long-lived secret and is the fix the architecture already assumes. This is
   the recommendation.
2. **Add a second login method to the account**, if the provider permits it for
   an existing passkey-only identity. Worth checking, but it introduces an
   external dependency in the recovery path.
3. **Hold an API access token offline as the recovery path.** Works from
   anywhere, but it is a long-lived credential — a real cost that needs its own
   decision rather than being adopted by default because it is convenient.

Whichever is chosen, the test is re-run and must pass **from the phone, off the
tailnet, with no second device involved**, before Phase 2 begins.

### The finding is the point

This is what the check exists to catch, and it caught it. Discovering that the
recovery path is imaginary costs nothing today; discovering it during an
incident costs the thing it was supposed to protect. Recorded as a finding with
the same weight as any technical one, because an unusable control is
indistinguishable from an absent one.

---

## D-015 — Correction: D-014 diagnosed the right failure and the wrong cause

**Status:** accepted. **Supersedes D-014's cause and remediation.** D-014's
observation stands; its conclusion does not.

D-014 recorded that the console could not be authenticated from the phone, that
no passkey existed on that device, and that the fix was to register a second
passkey. The observation was real and correctly measured. The diagnosis was
wrong, and it was wrong because it inherited an unverified premise instead of
checking the account.

**The account does not use passkey authentication at all.** The sole user
authenticates through a consumer identity provider, evidenced by the provider's
relay address on the account. The sign-in page offers that provider as a
first-class button alongside the passkey option. The passkey attempt failed
because there is no passkey — and none is needed.

So the recovery path very probably exists and was never broken. It was reached
for with the wrong control.

### Where the wrong premise came from

The handoff states that there is no identity provider and that the account is a
passkey identity. **That is factually incorrect** and it propagated: the
break-glass test was designed around passkeys, the failure was read as a missing
passkey, and the remediation was drafted to add one. Every step was locally
reasonable and the starting fact was never checked.

The design consequences the handoff drew from that premise **still hold**, which
is why the error survived so long. A consumer identity provider supplies no
SCIM, no group provisioning and no automated deprovisioning, so the conclusion —
build the policy on tags and autogroups — is unaffected. Only the stated fact
was wrong, and it happened to be a fact nothing downstream depended on until a
recovery path was designed around it.

### The lesson, which is the same one twice

This phase has now corrected two findings, and both failed the same way: a
negative result accepted without establishing what a positive would look like.
D-007 concluded a device was silent when the tool was silent. D-014 concluded a
credential was missing when the credential was of the wrong kind.

The specific guard that would have caught this one is cheap: **before testing
whether a sign-in method works, confirm which sign-in method the account
actually uses.** One look at the account page. The break-glass test was run
carefully — the network precondition was verified from the coordination side
across repeated polls — and none of that rigour helped, because it was aimed at
the wrong question.

Rigour applied to an unexamined premise produces confident wrong answers.

### Status of the block

**D-014's block on Phase 2 is suspended, not lifted.** The recovery path is
now believed to work, and belief is what D-014 was written to prevent. It is
lifted when the test is re-run — phone, off the tailnet, no second device — and
passes using the account's actual sign-in method.

If it passes, the remediation D-014 proposed becomes unnecessary and no second
credential is created. If it fails, D-014's options apply after all, and the
block was right for the wrong reason.

---

## D-016 — Break-glass verified. The Phase 2 gate is lifted.

**Status:** closed. Resolves D-014 and D-015.

Re-run from the phone on cellular, with the tailnet client off and wifi off.
Signed in using the account's actual method, and the policy editor loaded with
live content.

**The recovery path works and was never broken.** It was reached for with the
wrong control, for the reason recorded in D-015.

Incidentally, the editor showed the same allow-all grant that
`policy/policy.baseline.hujson` contains — a third independent confirmation
that the committed rollback target matches what the tailnet is serving, this
time from a device that shares nothing with the machine that captured it.

**Phase 2's gate is lifted.** No second credential was created, which is the
better outcome: the best-managed secret is the one that was never issued.

### What this cost, and the guard that would have prevented it

The handoff asserts the account uses passkey authentication. It does not. That
single unchecked fact produced a test aimed at the wrong control, a confidently
wrong finding, a remediation plan for a problem that did not exist, and a block
on the next phase.

The account page was one click away throughout, in a console that was already
open and authenticated.

The guard is narrow and worth stating as a rule: **when a document supplies a
fact about a system you can query, query it before building on it.** Not every
premise deserves that — but one that a whole safety path is designed around
does, and the cost of checking was a single page load.

This phase corrected three findings, and all three failed identically: a
negative result accepted without establishing what a positive would look like.
The method notes in `STATUS.md` carry the general form. This entry records the
specific variant that is easiest to miss, because it does not feel like
measuring at all — inheriting a fact from documentation rather than from the
system.

---

# Phase 1 — Tag the machine identities

## D-017 — Finding: there are **two** subnet routers, and one is the node meant to be isolated

**Status:** open finding. Amends D-003 and D-008. **Nothing touched.**

D-003 recorded one approved route into the home LAN, served by a user-owned
personal desktop. That was incomplete, and the way it was incomplete is
instructive.

**The media appliance also advertises the same route, and it is approved too.**

The earlier reading came from the client's status output, which reports the
*primary* holder of a route. When two nodes advertise the same prefix only one
is primary, so the second is simply absent from that view. The console's device
pages show both. A field that answers a narrower question than the one being
asked will quietly give a smaller answer.

### Why this one matters more than the first

The design assigns that appliance `tag:kiosk`, described as *deliberately
isolated, appears in no `src`*. It is currently a gateway into the entire home
network. The single node the model most wants cut off from everything is, in the
starting state, one of only two ways in.

That is a better illustration of the project's premise than anything that could
have been constructed deliberately: intent expressed in a document, and the
opposite arrangement live on the network, with nothing in between to notice the
contradiction. Phase 2's `tests` section is exactly the thing that would have
noticed.

### Consequences

- **Phase 1.5 has two migrations, not one.** Withdrawing one route leaves the
  other serving the same prefix, and the exposure is unchanged.
- **Tagging the appliance does not remove its route.** Tags govern access; route
  advertisement and approval are separate. Tagging it `tag:kiosk` while it still
  routes the LAN would produce a policy that reads isolated and behaves like a
  gateway. The route must be dealt with explicitly, not assumed away.
- D-008's conclusion is unchanged: the route is load-bearing for almost nothing,
  so removing both should still be cheap.

### Correction to D-008

D-008 identified which media device was the tailnet node by matching names
resolved over multicast. That mapping was **backwards** — the appliance's own
endpoint list settles it, and the device that is a tailnet node is the other one
of the pair. The counts and conclusions in D-008 are unaffected; the labels on
two rows were wrong.

---

## D-018 — Tags are assigned from the console, not by re-authenticating with a tagged key

**Status:** accepted. Deviates from the handoff's stated method, deliberately.

The handoff specifies: *re-authenticate every non-human node with a tagged auth
key.* That is the classic method and it works, but the console exposes a direct
**edit ACL tags** action on an existing machine, and that is the better path
here.

Three reasons, in order of weight:

1. **No credential is created.** The auth-key method requires minting a tagged
   pre-authentication key, putting it on the target host, and disposing of it.
   That is a credential with a blast radius — anything holding it can register a
   node under that tag — and it exists only to accomplish a state change the
   console can make directly. The best-managed secret remains the one never
   issued.
2. **No re-registration.** Re-authenticating restarts the client and re-registers
   the node. One of the targets is reachable only over the tailnet, and another
   is in daily household use. A method whose failure mode is "the node does not
   come back" should not be chosen when an equivalent method has no such mode.
3. **It is reversible in the same place.** Tags edited in the console can be
   edited back, without touching the host at all.

The handoff's method is not wrong; it is the right method when provisioning a
*new* node, which is exactly what the fleet scripts will do later. For nodes
that already exist and already work, changing their identity in place is less
machinery for the same result.

### The consequence that needs consent, not just recording

Tagging a node **transfers it from the owning user to the tag**, and Tailscale
disables key expiry on tagged nodes. Disabling key expiry is on the handoff's
short list of things to confirm with the owner before doing. So the tagging step
is gated on explicit approval, and this entry records the reasoning rather than
the completed action.

---

## D-019 — Rename `tag:kiosk` to `tag:appliance`: the name was already taken

**Status:** accepted, before anything was applied.

The handoff assigns the media appliance a tag named for a kiosk, meaning a
locked-down device that originates nothing. Reasonable in the abstract.

**In this house "kiosk" already means something else.** The automation platform
exposes kiosk-mode entities for two personal handhelds — it is a display mode in
an app, running on devices that are *not* the one the tag would apply to.

So the tag would have read, to anyone here, as governing a handheld while
actually governing an appliance. A policy file whose identifiers point at the
wrong device in the reader's head is worse than one with an inelegant name: the
whole value of the `tests` section is that a human can look at a rule and say
whether it is right, and that check fails silently when the words mean different
things to the writer and the reader.

Renamed to `tag:appliance` — the role it actually describes: something attached
to the network with no function *over the tailnet*, present but never a source.

### The general rule, now in `policy/README.md`

Do not name a tag after a word the surrounding environment already uses for
something else. The taxonomy is supposed to make the policy readable; a term
with a local meaning does the opposite, and the collision is invisible to
whoever writes the tag because they are not the one who will misread it.

### What did not change

The **assignment** is unchanged and still correct. The appliance keeps a real
job — it is the local hub for the home ecosystem — but that job runs entirely
over the local network, which access rules do not touch. Nothing it does needs
the tailnet, so it belongs in no `src`, exactly as the handoff intends.

The handhelds stay **user-owned**. They are personal devices and posture
subjects, and their kiosk mode is an application feature, not a network role.
Tagging them would strip the user identity that posture work in Phase 3 depends
on, to describe something that is not a network property at all.

Their remote access to the automation UI is a separate matter and is covered by
the household grant that Phase 2 must ship with an `accept` assertion.

---

## D-017 addendum — the second router is deliberate redundancy, and that is the interesting part

Recorded as an addendum rather than an edit; this file is append-only.

D-017 framed the second subnet router as something the design had failed to
notice — "intent in the document, the opposite live, nothing in between to
catch it." **That framing was wrong and unfair to the setup.** The owner
configured the appliance as a *backup* subnet router on purpose.

That is a sound arrangement and the reasoning is visible in the hardware: the
primary router is a desktop workstation, which sleeps; the appliance is always
on. Tailscale supports exactly this — several nodes advertising the same prefix,
one primary, the others taking over when it drops. Someone thought about
availability and built for it.

### So the real finding is a tension, not a mistake

**The property that makes a node a good failover router — always on, always
attached — is the same property that makes it a poor thing to trust.** And the
appliance is simultaneously the node the access model most wants to originate
nothing.

Availability engineering pulled one way, least privilege pulls the other, and
both are right. That conflict is worth far more to this project than a missed
route would have been: it is the kind of thing that shows up in real
infrastructure constantly and never appears in a reference architecture.

Recording it as a tension also changes what a good resolution looks like. The
answer is not "remove the backup router" — that trades away availability
someone deliberately bought. It is to move the *routing role* somewhere that is
both always-on and appropriate to trust, at which point the redundancy question
gets asked again on its own terms.

The always-on automation hub is that place, which is where the phase plan was
already going. And the segmentation option the plan prefers removes advertised
routes altogether in favour of forwarding by name — under which there is no
route to be redundant about, and the tension dissolves rather than being
decided.

### What does not change

- Both advertisements are live and both must be retired together, or the
  exposure is unchanged. Retiring one is worse than useless: it looks like
  progress.
- Tagging the appliance will not remove its route, so the contradiction between
  a policy that reads *isolated* and a node that routes the LAN is real until
  the routing role actually moves.
- A subnet router does not need to appear in `src` to serve a route, so
  `tag:appliance` and *backup router* are not in conflict as policy — only as
  intent. Which is precisely why it needs writing down rather than leaving to be
  rediscovered.

### Correction to the record

The original entry's rhetoric about intent and reality diverging unnoticed
should be read as applying to **this project's own documentation**, which
assigned an isolation role to a node without checking what that node was already
doing. Not to the network, which was doing something sensible.
