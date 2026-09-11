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

---

## D-020 — Tagging via the console does **not** disable key expiry. The handoff expected it would.

**Status:** measured. First node tagged; result differs from the documented
expectation, so the remaining nodes are paused on a decision this raises.

The appliance was tagged from the console. Four things were checked afterwards
rather than assumed, and one came back against expectation.

| Checked | Result |
|---|---|
| Tag applied, ownership moved from the user to the tag | yes — the console states this explicitly before you confirm |
| Node still online and reachable | yes, direct connection, unchanged latency |
| Household paths unaffected | yes — automation UI and broker both answer as before |
| **Key expiry disabled** | **no — expiry is unchanged and still set** |

### Why the difference, and why it matters

The handoff instructs: *note in the inventory that key expiry is disabled by
default on tagged devices, and which nodes that now applies to.* The honest
answer for this tailnet is **none of them**.

The behaviour it describes belongs to the *other* method. Key expiry is turned
off when a node **authenticates with a tagged auth key** — the identity is
minted as a machine identity from the start. Assigning a tag to a node that has
already authenticated under a person changes its ownership, but the node keeps
the credential and the expiry it already had.

So D-018's choice of method quietly avoided a side effect the handoff treated as
unavoidable. That is good — an infrastructure node whose key never expires never
re-proves anything — but it is not free, and the cost lands later.

### The trade-off this creates, which needs deciding rather than drifting

A tagged node with expiry still enabled **will drop off the tailnet when the key
expires**, in roughly six months for every node here. Re-authenticating it then
requires a tagged auth key — precisely the credential D-018 avoided minting.

Two defensible positions:

- **Leave expiry on.** Better posture: machine identities re-attest on a
  schedule instead of living forever. Cost: a calendar item, and an outage for
  any node nobody re-authenticates in time. For a gateway the household depends
  on, "nobody got to it in time" is a real failure mode, not a hypothetical.
- **Disable expiry on tagged nodes**, as Tailscale does by default for machine
  identities. Cost: the identity never expires, which is exactly the property
  the lab argues against elsewhere.

Neither is obviously right, and the handoff's list of actions to confirm with
the owner includes disabling key expiry — so this is not a decision to take
silently on the way past.

**Recorded as open.** The expiry dates are known and months away, so nothing
forces the choice today. What would be wrong is to let it be settled by
whichever method happens to get used next.

### The contradiction from D-017 is now live and confirmed

The appliance's approved route into the home network **survived tagging**, as
predicted but now verified. The tailnet currently contains a node tagged as an
appliance — a role defined as originating nothing — that is a standing backup
gateway into the entire home LAN.

Nothing is broken by that today, because the grants are still allow-all and
constrain nothing. It becomes a live contradiction the moment Phase 2 writes a
policy that says one thing while the routing table does another. Which is the
argument for treating the route migration as part of the same piece of work,
not as a later tidy-up.

---

## D-021 — Phase 1 applied. Two operational facts worth more than the tagging itself.

**Status:** Phase 1 changes complete. Acceptance **partially** met — see the
residue below, which is stated rather than glossed.

All three infrastructure nodes carry machine identities:

| Node role | Tag | Ownership |
|---|---|---|
| production stand-in | `tag:prod` | moved from the person to the tag |
| gateway | `tag:gateway-home` | moved from the person to the tag |
| network appliance | `tag:appliance` | moved from the person to the tag |

Operator devices stay user-owned, as the design requires for posture work.

Everything was verified against a baseline captured immediately before each
change: the automation UI answers over both the tailnet and the local network,
the broker still completes an MQTT handshake, the newly adopted actuator is
still reachable, operator access to the production stand-in is intact, and every
node is online. Nothing the household depends on moved.

### The acceptance criterion is not fully met, and cannot be by tagging

Phase 1's criterion is *no infrastructure node is authenticated under a personal
identity*. Three nodes now satisfy it. **One does not, and it is the most
consequential one.**

The primary subnet router — the node that actually carries traffic into the home
network — is a personal workstation, and the handoff correctly forbids tagging
it: it is someone's daily machine and a posture subject, and tagging would strip
the user identity that Phase 3 depends on.

So an infrastructure role is running under a personal identity, and no amount of
tagging fixes it. **Only moving the role fixes it.** That is the same conclusion
D-017 reached from the other direction, now arriving as an unmet acceptance
criterion rather than as an observation — which is a better place for it,
because a criterion has to be answered.

Phase 1 is therefore complete in what it can do, with the residue named: the
routing role must move to the tagged gateway before this criterion is honestly
met. Recording it as met would be the kind of quiet rounding-up that the whole
project exists to argue against.

### Operational fact 1: the policy file is reformatted on save

The saved file came back nine bytes smaller than what was submitted. The service
re-aligns column padding, and it does so **per block** — a blank line inside the
tag list split it into two alignment groups, and the second group was re-padded
to its own longest entry.

Harmless in itself, and the repo copy was reconciled to match what is live.
**But it matters for D-001.** The GitOps workflow is meant to own this file, and
a workflow that applies the repo copy and then compares will see drift on every
run that touches formatting. Whatever applies the policy must compare
*semantically*, or normalise through the same formatter first, or it will report
a difference that is not one — and a check that cries wolf gets switched off.

### Operational fact 2: the editor lies about what will be saved

The console editor is a legacy CodeMirror instance with a mirror textarea.
Writing to that textarea — even correctly, with the native setter and a
dispatched input event — updates the DOM but **not** the component state.
"Preview changes" showed an empty diff while the textarea held the new content.
Saving then would have silently written the *old* file, and left the tags
apparently declared but actually absent.

The habit that caught it generalises past this one editor: **before committing
a change through someone else's UI, make the UI show you the change.** The diff
view existed and cost one click.
# Phase 1.5 — Segmentation on a flat network

## D-022 — Option B verified. Both checks pass, and one of them nearly failed for the wrong reason.

**Status:** verification complete. **Nothing changed yet** — the cutover is
sequenced after Phase 2, per the ordering correction in D-008.

The handoff requires two things confirmed before building on Option B, *neither
assumed*. Both are now answered from the gateway itself.

### Check 1 — what forwarding the gateway can actually do

**Result: natively supported.** The handoff feared the add-on might be "too
constrained" and prepared Option D as the fallback. It is not constrained; the
capability is purpose-built. The add-on exposes a service list where each entry
names a target, a protocol — including raw TCP, which covers both the camera
stream and the actuator's control port — and a port to expose it on. Each
service gets a stable name on the tailnet side, which is exactly what Option B
asks for.

**Phase 1 turned out to be a prerequisite, not just a predecessor.** The add-on
documentation states the mechanism requires the device to be tagged. It is,
since Phase 1. Had the phases run in the other order this check would have
failed and Option D would have been adopted for no good reason.

One thing is *likely* rather than proven: the console offers the feature with no
upgrade prompt, which suggests it is available on the current plan. Proving it
means creating one, which is a change. Recorded as likely — the handoff's own
rule is not to design around a feature without confirming availability, so this
gets confirmed before it is depended on.

### Check 2 — whether each device resolves by name from the gateway

**Result: pass, for every device in the proposed set** — and verified by
*connecting*, not merely by looking up. A name that resolves but does not carry
a connection would have passed a weaker test and failed in production.

The actuator answers on its HTTP port when addressed by name. The camera accepts
a stream connection when addressed by name. Both from the gateway, which is the
only vantage point that matters.

**This check nearly produced a false blocker.** The first lookup command
returned only an IPv6 link-local address — which needs a zone identifier and
would plausibly have broken forwarding. It looked like Option B was dead. The
broader form of the same command shows both families with the IPv4 first, and
the connection test settles it outright. That is the third time this project has
had a narrow command produce a confident wrong negative; the standing rule
holds — do not conclude absence from a tool until you have made that tool find
something.

### A third naming mechanism, deliberately not used

The site gateway runs a DNS server handing out names derived from DHCP
hostnames, and those names resolve and connect too. They would work.

**They are not used.** Depending on them means depending on the one piece of
infrastructure the handoff explicitly says is not ours and cannot be configured
— the same device whose inability to reserve addresses caused this whole
problem. Multicast name resolution is peer-to-peer and depends on nothing
outside our control. Recorded as an available fallback that is being declined
on purpose, so nobody later "fixes" a problem by reaching for it.

### What is still open

Whether the add-on passes a name through to its forwarding target, or resolves
it once and caches, or requires an address. The host can plainly resolve and
connect by name; whether the add-on preserves that is untested, and testing it
means a configuration change and an add-on restart — which briefly drops the
household's remote access. That is an ask-first change, not a proceed-and-record
one.

---

## D-023 — Correction: D-022's check 1 was wrong. Option B via the add-on is dead.

**Status:** accepted. **Supersedes D-022's "natively supported" conclusion.**
Nothing was changed on the gateway — the attempt was rejected by validation
before it took effect.

D-022 reported that the gateway's forwarding capability was "natively supported,
not too constrained", and that Option B was viable. That was based on the option
schema declaring the target as a free-form string, and on documentation
describing it as "a local address reachable from this app."

**The schema enforces a pattern the documentation only hinted at.** Submitting a
hostname target came back rejected against a regular expression that permits
exactly one host: **loopback**.

So the service mechanism can expose things running *on the gateway itself*. It
cannot forward to another device on the network, by name or by address. It is
not a forwarding proxy at all, and Option B as the handoff describes it cannot
be built on it.

The handoff anticipated precisely this — *"if it is too constrained, go to
Option D"* — and it was right to keep the fallback.

### How I got it wrong, which is the useful part

Three signals were available and I weighted them badly:

- The schema said the field was a **string**. That is a *type*, not a
  *constraint*, and I read it as permission.
- The documentation said **"a local address"** and gave a **loopback example**.
  Both were accurate descriptions of a loopback-only field. I read "local" as
  "on your network" when it meant "on this machine".
- The one authoritative source — what the system accepts — was a single API call
  away and I reached for it only after building a conclusion on the other two.

This is the fourth time this project has produced a confident wrong answer from
a partial signal, and the first where the wrong answer was *optimistic*. The
previous three were false negatives caught before they cost anything. This one
was a false positive, and a false positive is worse: it would have been
discovered during the cutover, on a household gateway, rather than during
verification.

**The rule stands and gains a clause:** do not conclude capability from a
permissive-looking type or an example. Submit the thing you intend to use and
see whether the system takes it. Validation is documentation that cannot be out
of date.

### What survives from D-022

The name-resolution finding is unaffected and remains solid: the gateway
resolves the relevant devices by multicast name and **connects** to them, which
was verified by connection rather than lookup. Whatever mechanism ends up doing
the forwarding, it will be running on a host that can reach those devices by
name.

Also confirmed along the way, and worth keeping: **Tailscale Services are
available on the current plan** — one was defined successfully, and it received
its own tailnet address and a stable name of its own, independent of whichever
node hosts it. That is a stronger stable identifier than the handoff assumed was
available. It is simply not a way to reach a *different* device.

### Where this leaves Phase 1.5

Two live paths, both consistent with the constraint:

1. **Option D, as the handoff predicted.** The gateway already knows every
   device's current address; a scheduled reconciler syncs per-host routes
   through the API. It converts a missing DHCP feature into an automation
   problem, is fully reproducible from the repo, and needs no forwarding
   configuration at all.
2. **A loopback forwarder.** Because the constraint is *loopback only* rather
   than *no forwarding*, a small proxy on the gateway listening on loopback and
   resolving the device by name would satisfy it — and the Service mechanism
   would then publish that loopback port under a stable tailnet name. This keeps
   the property Option B was chosen for: **no advertised routes at all**, which
   is stricter than any `/32` scheme.

The second is more faithful to the design intent and adds a component. The first
is what the handoff already chose as the fallback and adds a script. Neither is
started here; the ordering correction in D-008 puts the cutover after Phase 2
regardless.

---

## D-024 — Simplest thing that works: per-host routes, both wide routes retired

**Status:** applied and verified.

After D-023 killed the forwarding approach, I recommended building a proxy
component. The owner asked whether that was overcomplicating a simple thing.
**It was**, and the way out was to check the premise the complexity rested on.

### The premise I inherited without testing

The whole phase is built on *the site gateway cannot reserve addresses, therefore
addresses move, therefore per-host routes are unsafe*. The first clause comes
from the handoff. The second does not follow from it, and nobody had checked it.

Two pieces of evidence sat in the automation platform the entire time:

- The NVR integration is configured against a **hard-coded address** and is
  running fine.
- The camera integration is already configured **by hostname**, using the site
  gateway's own DNS. Someone solved this problem months ago.

Configurations pinned to addresses have been working in this house for a long
time. The addresses may not be *guaranteed* stable, but they are stable enough
that the household already depends on it.

This is the same failure as the break-glass episode: a fact asserted in a
document, inherited as a constraint, never checked against the system that could
have answered it in one query.

### What I also got wrong about importance

I spent this phase on the naming mechanism. **The finding of this phase was the
two wide routes** — every tailnet node reaching every device on the home network.
The naming mechanism is a detail of how three devices stay reachable afterwards.
I optimised the detail and nearly shipped a new component to serve it.

The acceptance criterion also reads *"no route wider than `/32` **or** no
advertised route at all"*. Per-host routes are a satisfying answer, not a
compromise. I had promoted the parenthetical alternative into a requirement.

### What was done

The gateway now advertises three per-host routes — one camera for the stream
tier, and the two actuators for the action tier's granted/denied pair. They were
advertised, approved, and verified serving **before** anything was removed.

Then both wide routes were retired by **withdrawing their approval in the control
plane**, not by reconfiguring the devices. That needed no access to a personal
workstation or a media appliance, and it reverses with one click.

**Result: the exposed set went from every host on the home network to three.**
The wide route is gone from every node. Household paths — the automation UI over
both the tailnet and the local network, the broker, the NVR — all verified
answering before and after.

### On keeping the appliance as a fallback router

Declined, on the owner's question. Keeping the appliance's wide route would have
made it the primary and left the exposure exactly as it was — retiring one of two
identical routes is worse than useless, because it looks like progress.

Giving it the three per-host routes as redundancy was the coherent version, and
that was declined too. If the gateway is down, the actuator's control plane is
down with it — the routes would outlive their own purpose. The redundancy existed
because the previous route server was a desktop that sleeps; the gateway is
always-on and purpose-built, so the failure mode that justified it no longer
occurs. And the appliance's tag says it originates nothing, which should be true
rather than aspirational.

If gateway availability becomes a real concern, the answer is a second always-on
node appropriate to trust — not the media appliance.

### Acceptance, honestly

| Criterion | State |
|---|---|
| Chosen option recorded as a decision, with verification results | done |
| No route wider than `/32` into the home network | **done** |
| Flat-network limitation written into the threat model | done |
| Every exposed device reachable by a stable identifier that **survives a lease change** | **not strictly met** |

The last one is the honest gap. Per-host routes do not survive an address change
on their own; the evidence is that addresses do not move here in practice, not
that they cannot. The mitigation is that the exposed set is three devices, a
change is a one-line fix, and the telemetry canary the handoff already designed
would make it visible.

If that proves wrong, the escalation path is recorded and cheap: the reconciler,
or the loopback forwarder — and the Service defined during D-022's investigation
is still in place for the latter.

---

# Phase 2 — Deny-by-default with tests

## D-025 — Deny-by-default is live. The tests are the deliverable, and they earned it twice.

**Status:** applied and verified.

The tailnet's policy is now written from zero. **No grant is wider than a single
port and there is no `*` anywhere in the grants section.** Anything not written
down is refused.

### What is granted, and what is conspicuously not

Seven grants, each naming a source role, a destination and one port. The
household's remote access to the automation UI is the first of them, carrying an
`accept` assertion, because it is the entire blast radius of this project.

What is absent is the more interesting half:

- The **network appliance appears in no `src`.** Its tag says it originates
  nothing; now the policy says so too.
- **One of the two identical actuators is named. The other appears in no grant
  at all.** Same model, same port, same gateway — and the difference is
  asserted, not asserted-about.
- **Nothing reaches the site gateway's administration interface**, which the
  earlier wide route had published to every node.

### The tests rejected the policy twice, and both were valuable

**Once by accident.** The first version used an autogroup as a test principal.
The tailnet refused the whole file: valid in a grant, rejected in a test as an
unknown principal. Nothing was applied. That is the mechanism working on a
mistake nobody planned — which is better evidence than a staged one, because
nobody chose the failure.

**Once on purpose**, to satisfy the acceptance criterion. A grant was added that
would let the sensor role reach the production stand-in, contradicting an
assertion. The refusal named both problems precisely:

```
test(s) failed for user: tag:sensor
  "tag:prod:22" (tcp): want: Drop, got: Accept
test(s) failed for user: tag:collector
  "tag:prod:22" (tcp): want: Accept, got: Drop
```

The first line is the case the design cares about most: **a silent widening of
access**. Nobody's connection would have broken; nothing would have looked
wrong. The assertion is the only thing that notices. The second is the mirror
image — an assertion claiming access that does not exist.

The file was not applied either time. The live policy was verified unchanged
afterwards, by hash.

### Verified after applying

The household guarantee holds — the automation UI answers over the tailnet. The
operator path to the production stand-in works. And deny-by-default bites where
it should: the broker port, granted only to the collector role, is now refused
from an operator laptop that could reach it an hour ago.

### The route table follows the policy, which is worth seeing

After applying, the operator laptop installs a route to **only** the granted
actuator. The denied control and the camera get no route at all — the policy
grants this node nothing to them, so no path is offered.

All three still answer, because the laptop is physically on the same network.
That is not a failure; it is the documented limitation, visible on one machine:
**remote access is controlled, the local segment is not.**

---

## D-026 — The formatting drift from D-021 is deterministic, and now closed

D-021 recorded that the service reformats the policy on save, and warned that a
byte-wise comparison in a future GitOps workflow would report drift that is not
drift.

The drift was measured rather than worked around. It is exactly one rule:
**inline comment spacing inside arrays is collapsed to a single space**, while
column alignment between an object's keys and values is preserved. Thirty-seven
bytes across seven lines, all of them aligned comments in test assertion lists.

The template was changed to match. **The rendered output is now byte-identical
to what the tailnet stores**, verified by hash, so the repository and the live
policy agree exactly and a future drift check can be a plain comparison.

Writing the template in the formatter's own style is cheaper than teaching every
future check to forgive the difference.

---

## D-027 — A structural lint that needs no credential

Phase 2's acceptance asks for the tests to run in CI. They cannot yet: the
tailnet's own test evaluation happens when the policy is applied, and wiring
that into CI needs an API credential that does not exist (Q-003).

Rather than leave the gap empty, `scripts/policy-lint.py` runs on every pull
request and checks what can be checked without evaluating reachability:

- **no `*` in any grant** — the one rule the design states absolutely;
- every grant names a port;
- every tag referenced is declared, every host alias referenced is declared;
- no literal address anywhere outside the `hosts` block;
- braces and brackets balance.

**It was negative-tested before being trusted** — a wildcard grant and an
undeclared tag were each introduced and each caught, and the template restored
and re-verified by hash afterwards. A lint nobody has watched fail is a lint
nobody should rely on.

This is explicitly **not** a substitute for the tailnet's tests, and the workflow
says so in its own header. It catches a different class: the mistakes visible in
the text. The reachability assertions still only run at apply time, and closing
that gap is what the credential in Q-003 is for.

---

# Phase 5 — AWS without static credentials

## D-028 — The OIDC subject constraint is guarded three ways, because it fails open

**Status:** written and committed. **Not applied** — see D-031.

The handoff calls an unconstrained `sub` claim *the single most common
misconfiguration of this pattern* and asks for it to be called out. A comment
is a weak way to call something out, so it is guarded instead.

**Why this particular mistake deserves three layers.** The OIDC provider is
shared across all of GitHub. A trust policy that pins only the audience proves
one thing: the token came from GitHub Actions. It does not say *whose* Actions.
Any repository belonging to anyone can mint a token that satisfies it.

And it **fails open**. A missing or wildcarded subject does not break the
workflow — the deploy works, the pipeline is green, and the account is open to
the internet. Nothing surfaces it. Compare a mistyped role ARN, which fails
immediately and loudly; that error is self-correcting and this one is not.

So:

1. The policy uses `StringEquals` against one exact subject — not `StringLike`,
   which is the operator that makes a wildcard possible in the first place.
2. The variable supplying the ref **rejects wildcards** in its own validation,
   so the mistake cannot be made through configuration either.
3. `scripts/tf-lint.py` fails the build if the operator is loosened or a
   wildcard appears, and was negative-tested against both before being trusted.

Three layers is not belt-and-braces for its own sake. It is proportionate to a
failure that is invisible, silent, and total.

---

## D-029 — Join the existing state bucket instead of creating one

**Status:** accepted, and it removes more than it adds.

The first draft created a state bucket and a lock table, and documented the
bootstrap loop that follows — a stack holding the state that describes it must
be applied once with local state and then migrated.

Read-only reconnaissance made that unnecessary. **The account already has a
Terraform state bucket**, versioned and encrypted, carrying several projects
under prefixes. This stack joins it under its own prefix.

That deletes about ninety lines, and it deletes the bootstrap loop entirely —
which mattered more, because the loop is invisible until it bites and its error
on a fresh clone looks like a typo.

The deploy role is scoped to **this stack's prefix**, not the whole bucket.
Other projects keep their state there and this role has no business reading it.

Locking uses the S3 lock file rather than a DynamoDB table. The account has no
lock table; adding one would create something to pay for and maintain in order
to replace a feature that now exists natively.

This is the same instinct as Phase 1.5: look at what is already there before
building.

---

## D-030 — Identity Center is not built here, and the reason is architectural

**Status:** accepted. The file exists and is deliberately empty.

Identity Center lives in the organisation's management account. This stack
deploys into a workload account and its credentials cannot administer the
organisation. Writing the permission sets here would produce a plan that cannot
be applied by the identity it is written for — which is worse than not writing
it, because it looks finished.

The design intent is recorded in the file so it is not lost: **permission sets
are assigned to groups in the internal identity store, never to individuals.**
When a real identity provider eventually arrives, only the *source* of the
groups changes; the assignments do not.

Worth noticing for its own sake: the tailnet has **no** identity provider at all
and cannot do group-based assignment. AWS can. The same principle is available
on one side of this system and not the other, which is a more honest picture of
a real environment than a design where it is available everywhere.

---

## D-031 — Acceptance measured, not asserted; and what blocks applying

**The criterion:** *no long-lived AWS access key exists anywhere in the lab.*

**Measured, read-only:** the target account has **zero IAM users**, therefore
zero long-lived access keys. Not "we did not create any" — none exist to begin
with, and the stack adds none: the GitHub role is assumed with a token, the
collector role with a certificate.

The operator host does hold a static key, for an unrelated account outside the
organisation. Confirmed with the owner as out of scope — it belongs to a
separate system the lab does not use. Recorded here rather than omitted, because
a criterion that quietly excludes the one counterexample in sight is not worth
claiming.

### Not applied, and the two reasons are different

**Terraform is not installed on the operator host.** Nothing has been planned or
applied, so every resource in this directory is unverified against a real API.
Committed anyway: the code is the artifact the phase is judged on, and the
handoff explicitly says scripts and stacks are worth committing whether or not
they can run today.

**Applying creates and modifies infrastructure**, which needs the owner's
go-ahead with the exact commands shown, per the operating rules. It has not been
sought yet because the first reason blocks it regardless.

What *was* verified against the real account, read-only: the session, the
absence of IAM users, the absence of conflicting roles, the existing state
bucket's configuration, and — usefully — that **a GitHub OIDC provider already
exists**. An account holds only one per URL, so creating a second fails. The
stack adopts the existing one through a toggle that was written before the check
and set by it.

---

## D-032 — Adopt the account's existing federation pattern instead of inventing one

**Status:** accepted, and it is a straight improvement over what I wrote first.

The account already runs Terraform from GitHub Actions for a neighbouring
project. Reading how *that* authenticates answered a question I had been about
to decide alone.

**Its roles pin the subject to a GitHub Environment, not to a branch:**
`repo:OWNER/REPO:environment:NAME`. My first draft pinned a ref.

The environment form is better, and not for consistency's sake. **A GitHub
Environment can require a reviewer.** Pinning the subject to one means applying
infrastructure needs a human approval that is separate from permission to merge
— which is exactly what the review of Q-003 recommended, arriving here as an
existing convention rather than as advice.

There is a second property worth stating, because it is what makes the gate
real. The workflow's `environment:` declaration is simultaneously what allows
the reviewer gate **and** what makes the token's subject match. Remove it to
skip the approval and the subject stops matching, so the role refuses the
assume. **The approval and the credential are the same mechanism.** A gate that
can be removed by deleting one line is not a gate; this one cannot.

### An observation about the neighbouring project, offered rather than acted on

Those roles use `StringLike` on the subject, with exact values and no wildcards.
**That is correct today.** Every value is a literal, so it behaves identically
to `StringEquals`.

The reason this repository uses `StringEquals` anyway is that `StringLike` is
the operator that *makes a wildcard possible*. A single character added to a
value silently converts a pinned subject into an open one, with no error and no
sign in a diff that anything has changed in kind. `StringEquals` cannot be
widened that way — a wildcard in it matches a literal asterisk and simply stops
working, which is a failure that announces itself.

Not a vulnerability, and not this repository's to fix. Recorded because a
hardening that costs one word is worth knowing about, and because the lint here
would flag it, which is worth explaining rather than leaving as an apparent
disagreement between two projects in the same account.

### Consequence for the operator host

The provider previously required a named profile. In Actions there is no
profile at all — credentials come from the assumed role. It is now optional:
required on the operator host, where there is no default profile by design and
picking the wrong account is the mistake this project is most exposed to; empty
in CI, where the question does not arise.

---

## D-033 — Correction to D-032: the approval gate does not exist on this repository

**Status:** accepted. **Supersedes D-032's central claim.** Nothing built on it
has been applied, so the cost is a paragraph rather than an incident.

D-032 said the environment pin makes approval and credential the same
mechanism, and concluded: *"A gate that can be removed by deleting one line is
not a gate; this one cannot."*

**That is true where the gate exists. On this repository it does not.**

GitHub's protection rules — required reviewers, wait timer — are available on
the free plan **only for public repositories**. On a private one they need
Enterprise. This repository is private, by a Phase 0 decision, and has zero
environments configured.

### What makes this worse than a missing feature

`environment:` in a workflow **still works** without protection rules. The
environment is created implicitly, the token carries the
`environment:<name>` subject, and the role assumes cleanly. The deploy
succeeds. The pipeline is green.

**The only thing absent is the stop.**

So the arrangement I described would have reported success and enforced
nothing — the exact failure this project keeps finding elsewhere and has now
produced in its own design. D-028 was written a few hours earlier about a
control that fails open and looks correct; I then built one.

### How the mistake happened

I read the pattern off a neighbouring project's live IAM policies, saw
`environment:` subjects, and inferred the approval gate from the shape. The
inference was reasonable and the shape was real — that project is **public**,
so it has the gate. I carried the conclusion across a difference in plan
eligibility I never checked.

This is the handoff's own rule, broken again: *do not design around a feature
without confirming it is available on the plan actually in use.* It was
confirmed for the tailnet twice. It was not confirmed for GitHub.

### What survives, and what is now honest

**Keep the environment pin.** It still constrains *which* workflow context can
assume the role, which is real and worth having. What it does not do here is
gate on a human.

**State the absence.** The workflow and the Terraform now say plainly that
there is no approval gate on a private repository, so nobody reads
`environment:` as protection it is not providing.

**The option is the same one the neighbouring project took.** It moved its
publication step earlier for exactly this reason — the gate is only real once
the repository is public. This project plans to go public anyway, and Phase 0
built the entire disclosure boundary as preparation for it. Whether to flip now
is the owner's call and is recorded as an open question, not assumed.

---

## D-034 — Bootstrap ordering: the first apply is local, once

**Status:** accepted, adopted from the neighbouring project rather than derived.

The chicken-and-egg was real: GitHub Actions cannot assume a role that does not
exist, and the role is created by the stack Actions would run.

The neighbouring project solved this and wrote it down: **both bootstraps run
locally, once, under a named profile.** The first apply creates the provider and
the deploy role; every apply after that runs from Actions via OIDC.

Adopted unchanged. Two of its three bootstrap problems do not arise here —
D-029 already removed the state-bucket loop by joining an existing bucket, and
the OIDC provider already exists in the account. **Only the deploy role needs
the local first apply.**

Its rejected alternatives are worth keeping too, because they are the ones that
look tempting at the moment of being blocked: creating the role by hand in the
console (not reproducible), or the bucket with raw CLI calls (loses the
configuration that makes the bucket safe). Neither is chosen here either.

The consequence for sequencing is the same one that project drew: **the phase
that writes this code does not apply it.** Applying is a separate, explicit
step with the commands shown first.

---

## D-035 — The repository stays private, and the reason is not safety

**Status:** accepted, resolving Q-005.

Q-005 asked whether to publish now, since a real approval gate on the apply
workflow only exists for a public repository. **The answer is no**, and the
reasoning is worth recording because it separates two conditions that are easy
to conflate.

**Publication is gated on having something worth showing that can be shown
without exposing sensitive information.** Not on wanting a feature.

Two preconditions, only one of which is still open:

- **Safety is already met, and is enforced rather than assessed.** The
  disclosure boundary landed in the first commit — before any real value was
  written down anywhere — and the sweep has passed on every commit since. It has
  caught three genuine slips: a hostname left in a placeholder file, a private
  address in a script's own error message, and a twelve-digit placeholder that a
  scanner cannot distinguish from a real account id. Each was caught before it
  reached history, which is the only place a leak cannot be undone.
- **Readiness to show is the actual gate**, and it is editorial. Whether the
  work is finished enough to publish is the owner's judgement, not a technical
  condition.

So the position is not *"it is not safe to publish yet"*. It is **safe, and not
yet finished**. Written down so a later session does not reopen the safety
question Phase 0 settled, and does not mistake the editorial gate for a
technical one.

### Consequence for the apply workflow

There is no approval gate on the apply, and there will not be one until the
repository is published on its own schedule. That absence is stated in the
workflow and in the Terraform variable so nobody reads the environment pin as
protection — D-033.

Applies stay manual, rare, and preceded by a plan shown in full. That is a
weaker control than a required reviewer and it is not pretended otherwise.

---

## D-036 — Phase 5 runs from the production stand-in, against the handoff's rule

**Status:** accepted, with the rule's reasoning checked rather than waved past.

The handoff is explicit: run the work from the operator laptop, not from the
production stand-in. Phase 5 is being run from the stand-in. The deviation is
deliberate and the rule's two reasons are worth taking one at a time, because
one of them still half-applies.

*(That sentence originally quoted the handoff verbatim, which carried a real
node name across from the private overlay into a committed file. The sweep
caught it before `git add` — see the note at the end.)*

**Reason one — lockout — does not apply.** The rule exists because the work
*"consists of changing who can reach what over the tailnet"*, and a node
reachable only over the tailnet can drop its own access mid-run and be unable to
repair what it broke. Phase 5 changes nothing about the tailnet. It creates IAM
roles and a bucket in a cloud account, and no failure mode of it can affect a
tailnet path.

**Reason two — "a target, not an operator" — partly does.** That node is the
production stand-in, and Phase 2 deliberately restricts access to it. Running
from it means my session depends on a policy this project wrote. That is a
smaller version of the same hazard, and the handoff already prescribes the
mitigation: *anything long-running on that node runs under tmux, driven from the
laptop.* A dropped session then costs a reconnect rather than a half-finished
apply.

**What makes it the better host anyway** is a property that only became visible
on inspection. It already has Terraform, and a newer version than the operator
host would have got. It authenticates by SSO with **no credentials file, no
static keys and no environment variables** — so running the phase there does not
weaken the criterion the phase is judged on.

### The thing worth noticing about that machine

It is a Lightsail instance, and **Lightsail does not support IAM instance
roles.** It therefore cannot be given an identity the way a normal cloud server
can — which is the same constraint as the on-prem collector, arrived at from the
opposite direction.

That is exactly the gap IAM Roles Anywhere exists to fill, and it means the
pattern being built in this phase has a second legitimate subject already in the
lab. Not adopted now — the collector comes first, and a certificate authority
does not exist yet — but recorded, because "a machine that cannot hold a role"
is easier to reason about when there are two of them and they arrived for
different reasons.

Interactive human work on it stays on SSO, which is correct: Roles Anywhere is
for unattended machine identity, not for a person at a terminal.

### A leak vector worth naming

The quotation above was the fourth thing the disclosure sweep has caught, and
the first of its kind. The others were values I typed: a hostname left in a
placeholder file, a private address in a script's own error message, a
twelve-digit placeholder indistinguishable from a real account id.

This one was different. **Quoting the private handoff verbatim carries its real
names into a committed file.** The sanitisation map exists precisely because
that document names devices, and it is easy to forget while quoting a sentence
whose *point* is the rule, not the name.

The habit that follows: when quoting the source document, quote the reasoning
and paraphrase the subject. If the exact wording matters, run the sweep before
staging rather than after — which is what happened here only by luck of shell
ordering, since the sweep sat in an `&&` chain ahead of `git add`.

---

## D-037 — Phase 5 applied. And the account id belongs in secrets, not variables.

**Status:** applied and verified against the API.

Eleven resources created, nothing changed, nothing destroyed. **Verified by
reading AWS back**, not by trusting the apply log — the log says what Terraform
attempted, which is a different claim:

| Checked | Result |
|---|---|
| Deploy role's trust policy, read from IAM | `StringEquals` on both subject and audience; one exact subject; no wildcard |
| IAM users in the account, after the apply | **zero** — so zero long-lived access keys |
| Archive bucket | public access blocked, versioning on, lifecycle into both Glacier classes |
| Collector role's permissions | `PutObject` and `ListBucket`. Nothing else — it uploads and cannot read back |

Roles Anywhere created nothing, as intended: no certificate authority exists
yet, so the role sits with nothing able to assume it. That is the correct
resting state, not a half-built one.

### The mistake nearly made at the last step

The workflow originally read the account id, the state bucket and the role ARN
from repository **variables**. That is the ordinary choice, and none of the three
is secret in the usual sense — an account id is semi-public and an ARN appears
in every policy that references it.

**Repository variables are printed in workflow logs verbatim.** This repository
is private today and is intended to become public (D-035). Run logs become
readable when it does. So the arrangement would have published the account id
*retroactively*, out of logs nobody thinks to review at the moment of flipping
visibility — long after the decision that made it visible.

They are secrets now. GitHub masks secret values wherever they appear in log
output, **including inside Terraform's own output**, which prints bucket names
and ARNs freely and would otherwise have leaked the same value by a second
route. The masking is doing real work rather than ceremony.

The region stays a variable. It is genuinely public and masking it would make
logs harder to read for nothing.

### Why this one is worth writing down

The disclosure boundary has held for five phases by controlling what enters
git. **This is the first place a real value could have escaped without ever
being committed.** The sweep would not have caught it — correctly, since nothing
was wrong with any tracked file.

The general form: a boundary defined as "what is in the repository" misses
everything the repository *produces*. Logs, artifacts, published plan output,
issue comments from automation. Worth carrying into Phase 6, where drills
generate exactly that kind of output.

### D-037 addendum — the same lesson, twice in an hour

Minutes after writing the entry above, the apply left two working files on the
host that ran it — the binary plan and the apply log. **Both contain the account
id in full, both were untracked, and both were one `git add -A` from being
staged.** That command is used routinely here.

The sweep would have caught them at that point, since staged files are tracked.
But that is the second line of defence working, not the first, and it only
works because the sweep runs before every commit rather than in CI alone.

Added to `.gitignore`. The point is not the two filenames — it is that this
class keeps appearing and will keep appearing: **the outputs of running the
thing, rather than the thing.** Plan files, logs, rendered templates, captured
drill results. Each one arrives looking like a temporary artefact and sits in
the working tree exactly where a broad `add` will find it.

Phase 6 produces this class deliberately — a drill's value *is* its recorded
output. The habit to carry there: decide where a run's output goes before
running it, not after looking at it.

---

## D-038 — Phase 5 closes: the loop is verified, and CI cannot apply

**Status:** done and verified end to end.

A workflow run with **no stored credential of any kind** authenticated to AWS as
the deploy role, read the entire stack, and reported *"No changes. Your
infrastructure matches the configuration."* That is the phase's claim
demonstrated rather than described.

### Two things the first attempt got wrong, both found by measuring

**The subject was not the one I expected.** The assume failed against a trust
policy structurally identical to a working one in the same account — same
provider, same audience. Rather than keep guessing, a temporary step printed the
claims the token actually carried (only `sub` and `aud`; the token itself is a
credential and was never printed).

GitHub issues subjects as `repo:OWNER@<owner-id>/REPO@<repo-id>:...`, embedding
immutable ids beside the names. That is a genuine improvement — a subject pinned
to names alone can be inherited by whoever claims the name after a repository is
deleted. Older roles in this account predate it, which is precisely why matching
a working neighbour was misleading rather than helpful.

**The role could not read what it manages.** Terraform needs read access to
every resource it plans, which is more than it appears. The first policy granted
state access and little else.

### Fixing it in the narrowing direction

The obvious repair was to widen the role until the plan worked. That would have
produced a role able to create IAM roles unattended, on a repository with **no
approval gate** (D-033). So the split went the other way: **CI plans, a person
applies after reading the plan.**

The role now holds read on the resources it manages plus writes confined to this
stack's state prefix. Nothing it can do changes infrastructure.

**Deliberately not the ReadOnlyAccess managed policy.** That grants read across
the whole account, and this account holds another project's state and secrets.
*Read-only is not the same as harmless*, and a lab about least privilege should
not reach for an account-wide grant because scoping is tedious.

One action stays unscoped and is labelled where it sits: listing OIDC providers
has no resource to scope to, IAM requires a wildcard, and the data source calls
it before it can call Get. It reveals which providers exist and nothing else.

The apply path was **removed** from the workflow rather than left present and
failing. A capability that exists but errors is worse than one that is absent,
because the obvious fix for the error is to widen the role.

### Acceptance

*No long-lived AWS access key exists anywhere in the lab.* Measured after every
apply: **zero IAM users in the account**, therefore zero access keys. The deploy
role is assumed with a token; the collector role will be assumed with a
certificate. Neither has a credential that can be copied off a machine.

---

## D-039 — Two facts found while answering a cost question

Both are recorded because they change later phases, and both contradict
something previously assumed.

### Glacier's cost is in transitions, not storage

Storage is negligible — a hundred gigabytes in Deep Archive is pennies a month.
**Lifecycle transitions are charged per object**, on the order of five cents per
thousand into Deep Archive.

So an archive of many small clips costs more to move than to keep. If the
upload path is ever built, it should batch — daily archives rather than
per-event files. Written down now because the mistake is only visible on a bill,
months after the decision that caused it.

The archive today is empty and costs nothing. It exists to give the
certificate-based credential something to authorise, and that is worth saying
plainly rather than calling it a working archive.

### Basic device posture appears to be available on the free plan

The handoff states flatly that *device posture checks are not on the Personal
plan*, and gates Phase 3 behind a paid seat on that basis.

The vendor's pricing page says Personal includes **basic posture — operating
system and client version**. That matches what is already visible: every device
page in this tailnet shows `node:os`, `node:osVersion`, `node:tsVersion`,
`node:tsReleaseTrack`, `node:tsAutoUpdate` and `node:tsStateEncrypted` today,
and the stock policy's commented example builds a posture rule from exactly
those attributes.

If that holds, **a substantial part of Phase 3 is available now**, and only
integration-backed posture and just-in-time access need a paid seat. That would
change the phase plan meaningfully.

**Not acted on.** The handoff's own rule is not to design around a feature
without confirming availability on the plan in use — a rule this phase has now
broken twice. So this is a finding to verify by writing a posture rule and
seeing whether the tailnet accepts it, not a conclusion.

Costs, for the record: the free plan is the current one. The gated phases run as
one time-boxed sprint on a single seat — one month, one user.

---

## D-040 — Posture is enforced on the free plan; the handoff is wrong

D-039 recorded this as a finding to test, not a conclusion. It has now been
tested, and the answer is yes.

### What was asserted

The handoff states that *device posture checks are not on the Personal plan*,
and gates Phase 3 behind a paid seat on that basis.

### What the tailnet actually does

Two experiments, run against the live policy file.

**First: a posture rule was written and the tailnet was asked to accept it.** A
`postures` block was added and referenced from the action-tier grant via
`srcPosture`. The save was **rejected**, with:

```
test(s) failed for user: <operator>
  address "actuator-granted:52432" (protocol "tcp"): want: Accept, got: Drop
```

That rejection is the proof. A plan that ignored posture would have accepted the
file and quietly granted the connection; the existing `accept` assertion would
have kept passing. Instead the control plane evaluated the posture, found the
source did not satisfy it, computed `Drop`, and refused the file because a test
said `Accept`. **Posture is not merely parsed on the free plan — it is
evaluated, and it changes the verdict.**

**Second: the enforcement was asserted from both sides.** The rule was rewritten
against attributes the device genuinely reports, and `srcPostureAttrs` tests were
added in matching pairs — the same principal, the same destination, the same
port, differing only in what the device claims about itself:

- reported as encrypted state, stable track → `Accept`
- `tsStateEncrypted: false` → `Drop`
- `tsReleaseTrack: "unstable"` → `Drop`

The file saved. Every assertion passed. A one-sided test would have proved only
that the rule does not break anything; the deny halves are what show the
attribute is load-bearing.

The attributes available without payment, confirmed on a real device page rather
than from documentation: `node:os`, `node:osVersion`, `node:tsVersion`,
`node:tsReleaseTrack`, `node:tsAutoUpdate`, `node:tsStateEncrypted`.

### Household paths, re-verified after the change

| path | expected | observed |
|---|---|---|
| operator → gateway:8123 | granted | HTTP 200 |
| operator → gateway:1883 | denied | timeout |
| operator → prod:22 | granted | open |
| operator → actuator-granted:52432 | granted under posture | open, over the tailnet interface |

One caveat on method, recorded because it would otherwise look like a passing
test that is not one. The measuring device was on the home LAN at the time, so
probes to the two LAN-only addresses that are *not* routed over the tailnet
resolved over the local interface and proved nothing about the policy. Only the
`/32` that Tailscale actually routes traversed the tunnel. **A deny-side probe
run from inside the LAN is not evidence.** The authoritative deny evidence is the
`tests` section, which the control plane evaluates at save time and which
rejected two earlier drafts.

### Consequence for the plan

Phase 3 is largely unblocked at no cost. What still needs a paid seat is narrower
than the handoff implies: posture sourced from an external device-management
integration, and just-in-time access. Those stay in the one-month single-seat
sprint. The rest of Phase 3 can proceed now.

The handoff is amended, not worked around. This is the third time a factual claim
in it has failed when queried directly against the system it describes.

### A note on the policy file's whitespace, and a wrong explanation caught

After the posture work the rendered file stopped matching the live one by
twenty-eight bytes: four lines in the action-tier grant were padded so their
values aligned with the newly added, much longer `srcPosture` key.

I explained this as the console reformatting on save — padding keys to the width
of the longest in each object — and wrote that into both this log and the
template. **The explanation was invented to fit the observation and was wrong.**

It was cheap to test, because a save was needed anyway. The next render was
uploaded and read back: **byte-identical, hash for hash**, including the `tests`
blocks where `src` and `deny` sit beside `srcPostureAttrs` and are *not* padded
to its width. A formatter of the kind I described would have padded them. The
control plane stores the file verbatim.

So the twenty-eight bytes were my own earlier hand-editing in the console, from
before the render-and-upload routine was in use. The alignment is kept in the
template because it reads better, not because anything requires it.

Two things are worth keeping from this:

- The integrity check is stronger than assumed. Since nothing rewrites the file,
  **any** difference between the render and the live policy is a real
  difference — there is no benign class of drift to explain away. That is only
  true because it was tested rather than assumed.
- This is the same failure that produced the add-on forwarding error earlier in
  the project: a plausible mechanism, consistent with what was in front of me,
  asserted without submitting it to the system that could have refuted it in one
  step.

**Method note, against my own conduct here:** far too many turns went into
locating that difference by inspection. The routine that works is to render the
template and upload the whole file, then compare hashes — not to reconcile
fragments. Reconciling by hand is what produced the drift in the first place.

---

## D-041 — CI reaches the tailnet by federation, read-only; no write credential exists

Supersedes the earlier answer to the credentials question, which was two OAuth
clients: a read-only one for pull-request checks, and a write-scoped one for
applying, placed behind a GitHub Environment with a required reviewer.

### What changed the answer

Three facts, each checked against the system rather than taken from the
handoff.

**Federation exists, and on this plan.** The console offers *OpenID Connect*
trust credentials alongside OAuth ones, with GitHub as a preset issuer, on the
free plan. A workflow presents the OIDC token GitHub signs for that job;
Tailscale exchanges it for a short-lived API token. Nothing is stored, so
nothing needs rotating, and there is nothing to leak. This is the same move
Phase 5 made for AWS, and it removes the whole class of problem the OAuth answer
was managing — secret storage, issue dates, rotate-on-departure.

**Read scope is enough to run the real tests.** `policy_file:read` covers the
validate endpoint, which takes a proposed policy, parses it, and runs its `tests`
section against the live tailnet without applying anything. The pull-request
check can therefore exercise exactly the evaluation that refuses a bad save in
the console — and it needs no write access to do so.

**The read scope does not come alone.** Selecting `policy_file:read` makes the
console also select, and lock, `devices:core:read` and
`devices:posture_attributes:read`. They cannot be cleared while the policy read
is selected, and they clear with it. The reason is visible in this very policy:
its tests name devices and assert on posture, and the validator cannot evaluate
those without reading both. Both extra scopes sit in a section the form shows
collapsed, so a credential created by ticking one box and generating would carry
three scopes while its creator believed it carried one. The form was checked
section by section before anything was generated.

**The safeguard for the write client is not available.** The design put the
write credential behind a required reviewer, so applying would need an approval
separate from merging. On a private repository that control needs an Enterprise
plan (D-033). Without it, a write credential in CI is a credential to the
tailnet's global access control, obtainable by any workflow that names the
environment. The control that justified building it is missing. So it is not
built.

This is the same answer the owner chose for AWS in Phase 5: **CI verifies, a
person applies.**

### What CI does

| trigger | job | effect |
|---|---|---|
| pull request touching the policy | `validate` | the real tailnet parses the render and runs every test; nothing is applied |
| push to main, daily, manual | `drift` | the policy in force is compared byte for byte with the render of main |

The drift check is only meaningful because of D-040: the console stores the file
verbatim, so any difference is a real one — an apply is pending, or someone
edited the console. The check prints hashes and sizes, never content: the live
file carries the real values.

### Details that matter

- **The subject is exact.** The console accepts `*` in the subject field. That
  is the same trap as `StringLike` in an AWS trust policy, which `tf-lint.py`
  refuses there. The subject is the id-bearing form GitHub actually issues for
  this repository (found the hard way in Phase 5), pinned to one environment:
  `repo:<owner>@<owner-id>/<repo>@<repo-id>:environment:tailnet-read`.
- **A failed validation is HTTP 200.** The only difference from a pass is a
  non-empty body. A check keyed on the status code would pass a policy the
  tailnet itself refuses. The script tests the body, and that path was tested
  offline against a simulated failure before any credential existed.
- **The values reach CI as environment secrets**, four of them, one per template
  placeholder. The renderer's CI mode reads only the environment and never falls
  back to the inventory; it names missing values without printing any. The API
  script redacts them from its own output as well, so the log masker is the
  second layer rather than the only one.
- **When the exchange fails, the script prints the `sub` and `aud` claims** the
  token actually carried — never the token. That one diagnostic is what resolved
  the Phase 5 federation failure; this time it is built in rather than added
  under pressure.
- **Leak sweep versus Tailscale key shapes, measured.** Fabricated
  `tskey-client-`, `tskey-auth-` and `tskey-api-` strings were each committed to a
  throwaway repository with the sweep; each was caught. The first attempt at this
  was invalid — the control file failed too, because the sweep excludes itself by
  path and had been copied to the wrong one. Only once the control passed clean
  did the three catches mean anything.

### Residual risk, stated

- **Any workflow on any branch that names `tailnet-read` obtains the token and the
  four values.** Deployment-branch restrictions, which would narrow that, are not
  available on this plan for a private repository. Today the only person who can
  push a branch is the owner. Pull requests from forks receive neither OIDC tokens
  nor secrets, so this holds when the repository goes public.
- **What that token reaches is disclosure, not control.** It can read the live
  policy, which contains the real addresses and the operator identity, and the
  device inventory with each device's posture attributes — names, tailnet
  addresses, operating systems and versions, tags. That is a map of the tailnet
  and of which devices are behind on updates. Nothing reachable with it changes
  what anyone can connect to.
- **Verified on the first run, both sides.** The exchange request, mirrored
  from Tailscale's own client source, was accepted as written. On the pull
  request that introduced the workflow, the tailnet parsed the render and every
  test passed; the render CI produced from environment secrets was
  byte-identical to the local one and to the policy in force. Then a throwaway
  pull request moved the broker port from `deny` to `accept` in one test.
  `validate` failed with exit code 1 — a test failure, not an infrastructure
  error — named that exact assertion, and printed the operator as
  `<operator_identity>`: the script's own redaction, the second layer, doing its
  job. Neither run's log contains any of the four real values or a token. A
  check only ever seen passing has not been shown to check anything; this one
  has now been seen refusing.
- **Drift, verified on both sides.** On the merge to main, the policy read back
  through the API was byte-identical to the render — same 10983 bytes, same
  hash — so the API returns exactly what the console editor holds and the
  comparison needs no normalising. Then the workflow was dispatched by hand on a
  throwaway branch whose template differed by one comment line. `drift` reported
  `DRIFT`, 11054 bytes against 10983: the difference was exactly that line.
  Neither log contains a real value.
- **Found by that control, not looked for: the validator refuses a policy file
  whose last line is a `//` comment.** The same dispatch ran `validate`, which I
  expected to pass — a trailing comment is valid HuJSON. It failed:
  `parsing comment: unexpected EOF`, positioned at the comment's first
  character. Tailscale's parser requires a line comment to end in a newline; the
  file sent did end in one, byte for byte. So the newline is lost before parsing,
  somewhere on the server side. That last step is an inference from their
  parser's source and the error position, not an observation, and whether a
  console save would refuse the same file was not tested — it would mean saving
  the live policy to find out. It costs nothing today: the template ends in `}`.
  It is recorded because a comment appended at the end of the file is exactly
  the kind of edit someone makes without expecting it to fail.

### Done

The trust credential exists, with the exact subject and the three read scopes
the console insists on — the owner approved that set after being shown it.
The `tailnet-read` environment holds the two non-secret identifiers and the four
values, set from the inventory through standard input so none reached a command
line. Revoking the credential in the console ends CI's access at once; there is
no secret to rotate.

---

## D-042 — Production was reachable by SSH from the whole internet, around the tailnet

Found while verifying that the development host came back after a reboot. Not
looked for — which is the point worth making about it.

### What was found

The production host is a small cloud instance. Its provider firewall allowed
`22/tcp` from `0.0.0.0/0` and `::/0`, and sshd listened on every interface. So
there were two SSH paths to production:

| path | what answers | what decides who gets in |
|---|---|---|
| over the tailnet | Tailscale SSH, `check` mode | tailnet identity, plus a periodic browser re-authentication |
| over the public address | OpenSSH | possession of a key — nothing the tailnet policy can see |

Every grant, test and `ssh` rule in this repository governs only the first
path. The owner's own workstation, and the desktop application's remote
sessions on the host, all used the second.

The same firewall had `80/tcp` open to `::/0`. That one is inert today: nothing
listens on 80, and the instance has no public IPv6 address — the only global
IPv6 on the box is the tailnet's private one. It is recorded because it is the
kind of rule that becomes live the day someone enables IPv6 or starts a web
server.

sshd accepts keys only: password and keyboard-interactive authentication are
off, and root may log in only with a key. That keeps this a finding rather than
an incident.

### Why the uncontrolled path was the one in use

This is the part worth keeping. The tailnet path was protected by Tailscale SSH
in `check` mode, which periodically stops a connection until someone completes a
browser sign-in. A person at a terminal can do that. A program cannot: a
non-interactive `ssh` over the tailnet simply hung on the prompt, and so would
the desktop application's remote sessions. The stricter control made the
controlled path unusable for the clients that actually needed it — so they used
the uncontrolled one, and the strictness bought nothing.

A control that is too strict for its real clients does not make them safer. It
routes them around itself.

### A correction to earlier entries

D-040 and the Phase 3 commit record "SSH to production" as verified. What was
verified was a TCP connection to port 22 over the tailnet. A real login on that
path would have stopped at the browser check. The network grant was correct;
the claim that SSH worked was broader than the evidence.

### What was changed

In order, each step verified before the next, with a way back at each point:

1. **Tailscale SSH turned off on the production host.** sshd now answers on the
   tailnet address as well. Its host key was compared with the key already
   trusted on the public path and is identical, so nothing has been substituted.
   On the tailnet path, the control is now OpenSSH key authentication, reachable
   only by those the `tag:prod:22` grant admits — the policy tests that deny
   `tag:prod:22` to every other role still hold. Undo: one command on the host.
2. **The workstation's SSH alias now resolves to the host's tailnet name.** The
   public address is kept under a separate break-glass alias. The tailnet name's
   host key was added to `known_hosts` only after its fingerprint matched the
   trusted one. A non-interactive login over the new path was verified, and the
   host sees it arriving from a tailnet address. Undo: restore the backed-up
   config.

### What did not go as expected

The desktop application does not use the system `ssh` binary. Its connection is
held by the application process itself, which had resolved the alias earlier
and kept the address. The live test — ending only the application's public
connection, with the host's SSH daemon and the remote session left untouched —
showed it reconnect within seconds, **over the public address again**. My
inference is that it picks up the new address only when the application
restarts. That is not verified.

### Not yet done, and why

**Port 22 is still open to the internet.** Closing it now would cut the desktop
application off from the host, because its tailnet path is not proven. The
order stays:

1. restart the application, confirm its connection arrives from a tailnet
   address, confirm the remote session still works;
2. only then replace the provider firewall rules: `22/tcp` closed to the
   internet, the stale `80/tcp` rule removed.

Closing 22 does not lock anyone out of the host for good. The provider firewall
is controlled through the cloud provider's API, which does not depend on the
host being reachable. Reopening 22 is one call from anywhere with the account's
single-sign-on access. That is the break-glass path, and it should be tested
once before it is needed.

**The policy's `ssh` rule for `tag:prod` is now dead configuration.** It still
says production SSH requires a periodic browser check, and nothing enforces that
any more, because Tailscale SSH is off on the only host with the tag. A rule that
reads like a control and is not one is the same failure this entry is about. It
should be removed or rewritten against a host that still runs Tailscale SSH.
That is a policy change, left for the owner to decide.

---

## D-043 — The repository goes public; the audit found a gap in the boundary

Supersedes D-035, which kept the repository private until it could be shown
without disclosing anything. The owner decided it now can: the project is
presented as work in progress, and `STATUS.md` says plainly what is not done.

### What was audited, and how

The disclosure sweep in CI reads tracked files at the tip of a branch. Making a
repository public exposes far more than that, so the audit covered what
publication actually exposes:

| exposed by publishing | result |
|---|---|
| every version of every file in history, including every pull request's head | clean |
| branch names; pull request titles, bodies and comments | clean |
| commit author and committer addresses | platform no-reply addresses only |
| workflows that run untrusted code with secrets (`pull_request_target`) | none |
| the logs of all 81 workflow runs | one identifier, below |
| **commit messages** | **one commit, below** |

The scanner used the same rules as the CI sweep, plus concrete values the sweep
does not know: every relevant account id, the owner's addresses, the tailnet's
name, public addresses. It reports locations, never values. Before its clean
results were believed, it had to catch planted values in each mode. That rule
earned its keep twice: one pass read 1 of 81 logs because a shell loop did not
split its input, and one control ran the committed script instead of the edited
one. Both "clean" results were false until fixed.

### What was found

**Commit messages were never swept.** One commit on a Phase 1 branch named
three nodes by their real names in its message. `main` never carried it —
that phase was squash-merged — but GitHub keeps every pull request's commits
reachable for good, so publishing the repository publishes the message. The
names are generic device-role names. The owner accepted them as they are.

The finding is not those three words. It is that the boundary checked files
and not messages, while a message is as public as the code it describes. Now:

- the sweep also reads commit messages, for every commit a pull request brings
  in and every commit a push to `main` adds, with the same rules and the same
  redaction of denylisted terms;
- in CI, a missing denylist **fails** the sweep instead of skipping it. That is
  what a pull request from a fork sees, since forks receive no secrets, and a
  check that quietly omits its most specific part still reports green.

Both were tested against controls: the known commit is caught, a planted
address in a fresh message is caught, clean history passes, a missing denylist
fails in CI and only notes itself locally.

**The tailnet credential's client identifier was printed in five run logs.** It
was passed as a repository variable, and variables are printed verbatim in step
logs. Tailscale does not treat it as secret: using it requires a signed token
whose subject names this repository and environment exactly, and a pull request
from a fork cannot obtain one. It is now passed as a secret so it is masked from
here on. The five existing logs were left as they are.

### Not changed by publishing

Secrets stay secret on a public repository. Pull requests from forks get no
secrets and no federated identity tokens, so neither the tailnet check nor the
cloud plan can run for them — they fail closed.

---

## D-044 — A live evidence page, built from CI's own record

The repository is public, and the question a reader actually has is whether any
of it is true now. A status file answers that only as of when someone last
edited it. So the lab publishes a page on which every status is read, not
written.

### How it works

A scheduled workflow asks GitHub, at build time, for the latest result of each
check on `main`, and renders what comes back: pass, fail or "no data", when it
ran, which commit, and a link to the run. The claims it covers:

- the policy in force is byte-identical to `main`;
- every policy test passes on the live network;
- the tests can fail — the pull request that was broken on purpose, whose
  expected result is a refusal;
- the cloud infrastructure matches its code — a read-only plan whose log must
  say "No changes", not merely a job that succeeded;
- nothing real can merge, and no secret is in history;
- `main` accepts only changes that passed its checks, for everyone — as stated
  by GitHub's public record of the branch, and no more than that record says.

Each reading shows its age, and one older than its schedule turns amber in the
visitor's browser. A stalled schedule therefore shows up as stale, never as a
standing green. Figures that come from the code rather than from a run — grant
and assertion counts, decisions and corrections — sit in a section labelled
"from the code, not measured".

### What the page can reach

The job that builds the page holds no tailnet credential and no cloud
credential. It reads public CI metadata and writes the Pages site; the
`github-pages` environment accepts deployments from `main` only. This keeps the
property the rest of the lab is built on: nothing in CI can change the network
or the cloud.

The page is swept for real-world values before it is published, like source
code. It is built from API data, and API data is input.

### Three false results caught while building it

Each one would have put a wrong status on a page whose whole claim is that its
statuses are right.

- **A passing plan rendered as a failure.** A job log is served by redirecting
  to a signed storage URL, which rejects the API token. Following the redirect
  automatically carried the token along; the download failed, and the plan
  check read as failed. Now the redirect is followed by hand, without the token.
- **The same plan, still failing, once the log arrived.** Terraform colours its
  output, and the escape codes sit between the words of the sentence being
  matched. They are stripped first. The matcher was then tested against a
  no-changes log, a log with changes, and an empty one.
- **The page's own links read as leaked account ids.** GitHub Actions job ids
  are twelve digits, the same shape as a cloud account id, so the disclosure
  sweep flagged every "open the run" link. The sweep now blanks GitHub Actions
  run and job URLs before matching — the URL only, not the line. A control
  confirmed that an account id placed on the same line as such a link is still
  caught.

One overstatement was also removed before it shipped: the branch card first said
`main` "requires a pull request". The public branch record lists the required
checks and who they apply to, but not whether a pull request is required, so the
page now says only what the record says.

### Also changed

- `validate` now runs on every trigger, including the daily schedule — before,
  it ran only on pull requests, so there was no current reading of it on `main`.
- The cloud plan runs weekly as well as by hand.
- The build job re-enables the scheduled workflows on each run. GitHub disables
  schedules in a public repository after 60 days without activity. Whether
  re-enabling an already enabled workflow resets that clock is GitHub's
  behaviour to confirm, not something verified here; if it does not, the page's
  ageing makes the stall visible.

### Still open

The page is served from GitHub Pages at the project address. The custom domain
needs one DNS record in a zone this repository's cloud access cannot reach, so
it waits on the owner.

---

## D-045 — The evidence page gets a picture, and the picture is parsed

A reviewer's first question is not "is it green" but "what is this". The page
answered the second question only in prose. It now opens with one diagram of
the whole lab: the contours (CI, the network's control plane, the cloud
account, the tailnet overlay, the home network), each subnet by size and
purpose, which tool manages each part and why, and who may reach what.

### What on it is drawn, and what is parsed

Contours, positions and the words on each tile are drawn by hand, like any
architecture diagram. The access arrows are not:

- every green arrow is a grant parsed from the policy template, labelled with
  the port the grant names, and a grant routed through the hub is drawn
  through the hub;
- every red arrow is a refusal asserted by the policy's tests;
- a grant between roles the layout does not know is listed under the diagram
  rather than silently left out.

So the picture cannot show a path the policy does not grant, and a grant added
tomorrow appears on the next build. A table under the diagram says what each
part is for, how it is managed and which decision explains it.

### Live counts, without giving the page a credential

The tiles carry live node counts. The page still holds no network credential:
the job that already reads the tailnet with its read-only identity now also
writes an aggregate — nodes by role, OS and state, routes by prefix length —
and publishes it as a build artifact that the page reads. The aggregate is built
from an allowlist of derived numbers; nothing from a device record is copied
through. An artifact of a public repository can be downloaded by anyone, so it
is swept before upload, and the aggregator was tested offline against a device
list full of names, addresses and routes: none reached the output.

### A parser bug caught by counting

The diagram's parser first found 25 refusals. The template has 30. The missing
five were the operator's tests: the `{{operator_identity}}` placeholder is itself
made of braces, and the block parser read it as nesting and lost those blocks.
Placeholders are now named before parsing, and the count matches. Without the
cross-check the diagram would have looked complete while leaving out the one
refusal it most wanted to show — the identical smart plug an operator is denied.

### The Phase 0 inventory

`docs/01-inventory.md` is now marked as the Phase 0 snapshot it always was, and
points to the live counts. It had become a trap: a public document still naming
a tag that was renamed and a sign-in method that was corrected.

### Layout, layers, and where the lab could grow

The first version routed arrows as diagonal curves, and the result looked busy
even when every arrow was correct. The layout was redrawn around the flows
instead: the hub sits directly above the devices it routes to, the operators and
the production host share a row so the SSH grant is one straight line, the
planned roles form their own block, and every arrow runs horizontally and
vertically with rounded corners. No contour title sits where an arrow lands.
Three toggles — granted, refused, who changes what — let a reader strip the
picture down to the access map alone.

A band along the bottom shows the growth path, explicitly marked as not built:
an identity provider for many users and their groups, device management as the
source of posture, just-in-time access, log streaming to a SIEM, IAM Identity
Center for people's cloud access, and the certificate authority that would
switch Roles Anywhere on. Each tile says what it plugs into and which phase or
decision it belongs to. None of them has an arrow: a diagram that draws
connections to things that do not exist invites reading them as real.

---

## D-046 — An outside review, and what was done with it

A review of the evidence page made six recommendations and one warning: the
scaffolding is ahead of the thing it governs — many decisions, tests and CI
jobs around seven grants and a handful of live hosts. The warning is accepted.
This entry records the response in one place rather than as several decisions.

**Done now, because each one makes an existing claim more honest rather than
adding machinery:**

- **Posture is labelled as self-reported.** On this plan the posture attributes
  are reported by the client on the device itself. They establish how a device
  is configured, not that it is intact, and a compromised node is not
  constrained by them. The diagram now says "posture: self-reported", the
  table says why, and the page's top block says it in plain words. That gap is
  the reason the device-management tile exists.
- **A reader gets ninety seconds.** A block above the diagram gives the one
  number (3 of about 40 devices in the house reachable from the overlay,
  measured live), what is checked daily, what is not built and what it would
  cost, and what to read with care.
- **The rest of the house is on the diagram.** About 40 devices by type,
  counted by hand from the hub's registry — a snapshot with a date, not a live
  reading, because giving CI a credential into the home to keep a count fresh
  is the wrong trade. Two rules shaped it. The camera count is not published,
  and a total plus every other category would let anyone subtract it — so the
  total is rounded and the remainder is folded into one group. And the first
  classifier put the robot vacuum among the cameras because it carries a camera
  entity; the owner caught it, and vacuum is now checked before camera.
- **The growth path carries prices**, from the vendors' own pages: an identity
  provider and device-management posture need Tailscale's Standard tier
  ($8/user/month), just-in-time access and log streaming its Premium tier
  ($18/user/month), IAM Identity Center has no charge, and a certificate
  authority is free self-hosted or $50–400 a month managed.
- **`terraform plan` runs on pull requests** that touch the stack, as well as
  weekly — with the trust that implies written into the workflow.

**Already true, or out of date in the review:** the before-and-after exposure
reading was missed, and `STATUS.md` already says so without reconstructing it.
The review's note on two OAuth clients predates D-041: there are none.

**Parked:** a button that starts a check from the public page, with a live view
of the run. It is exactly the kind of machinery the review warns against, and
it would need a stored credential able to start workflows — the one thing the
page tells readers this lab does not have.

**Next, in the review's order, and each needing the owner:** the collector as a
real host with one telemetry stream through the existing grants; then the
lost-comms drill on that stream, for the page's first number that comes from
watching the system rather than counting the repository; and the "after" half of
the exposure reading from a disposable node.

---

## D-047 — An address is not an identity: the exposed camera was the wrong camera

### What was wrong

Since Phase 1.5 the lab exposed one camera to the tailnet — one `/32` route
through the hub, one grant, to the collector role only. It was meant to be the
one camera the owner has released for the project. **It was a different
camera, one the owner had not released.**

The error was mine, and its cause is specific. The camera was identified by its
DHCP hostname. Both cameras on the network are the same make and announce the
same hostname, and that name has been seen following the other camera across a
lease change. The identification was never checked against anything that
belongs to the device itself.

It surfaced when planning the first real telemetry: before building on the
camera, the owner asked which one it was. Three independent sources agreed —
the device's MAC at that address, the owner's camera register, and the machine
that runs the recorder.

### Why nothing was reached

The grant named only the collector role, and no node holds that role yet.
Clients install only the subnet routes their policy lets them use, so no node
had even installed the route. The exposure was latent: it would have become real
on the day the collector came up — which was the next step on the plan.

### What was done, with the owner's go-ahead

1. **The route was withdrawn at the hub**: removed from the add-on's advertised
   routes, the add-on restarted. The household paths were checked before and
   after: the automation UI and the granted socket, both over the tailnet.
2. **Its approval was removed in the console.** The console itself flagged it:
   *1 route is approved but not advertised anymore.* A leftover approval is not
   inert — if the hub ever advertises that route again, after a restore or by
   mistake, it is live at once, with no admin step. Withdrawing a route means
   both halves.
3. **The camera left the policy**: its host alias, its grant and the tests that
   named it. The collector's tests now assert that it reaches the broker and
   nothing else on the home side.

Two devices are now exposed, both verified today by their own identifiers
rather than by address: the granted socket by its HomeKit accessory id, the
control socket by its MAC.

### What else it exposed

- **The live route count was counting the wrong thing.** It reported routes an
  admin had approved as if they were routes in effect. It now reports the
  intersection of approved and advertised, and separately the approvals left
  behind with no route. Checked against a constructed case with one of each.
- **Every remaining `/32` rests on an address that can move.** The network has
  no DHCP reservations, and addresses have already changed hands between
  devices. A `/32` that is correct today can point at a different device after a
  power cut, silently. The next control is therefore not another grant but a
  check: each exposed address, verified every day against the identifier of the
  device it is supposed to be. That also gives the evidence page a figure that
  comes from watching the system.
- **The released camera comes back differently.** Not as a `/32` to an address,
  since it too has held more than one — but through a restream on a host the
  lab controls, named by camera.

---

## D-048 — The broker's documented ACL is a no-op, and I restarted a service I had not surveyed

### The attempt

The first telemetry path was to run through the home broker: a new login for
the collector, allowed to read one topic tree and nothing else, using the
access-control-list method in the broker add-on's own documentation.

### The finding

**The documented ACL does not restrict anything.** Tested from the collector's
own node with its own login: a subscription outside its tree timed out, which
proves nothing on its own — but a publish, which the list forbids, was accepted
and delivered to the collector's own subscriber. The reason is in the add-on's
source. Its authentication plugin asks an internal endpoint whether a user is a
superuser and whether an access is allowed, and that endpoint answers yes to
both, for every user. The documented list is loaded and never consulted. A
login described as read-only was, in effect, a superuser on the broker the
automation hub listens to.

A vendor's documented control can be a no-op. Only a test from the restricted
side, with a positive control, tells you which.

### My mistakes in the same step

- **I judged the broker unused from its recent log window**, which showed only
  health checks. A log shows who connected recently, not who is connected. A
  long-lived client — the recorder on another machine — had connected before the
  window and appeared only after I restarted the broker.
- **The access list I wrote did not include that client.** Had the list worked,
  the recorder would have lost the broker. It was saved by the same defect that
  made the list useless.
- **I had asked the session that knows the house exactly this question, and
  acted before its answer arrived.**

The broker was restarted twice for a few seconds each; the recorder reconnected
by itself both times.

### Rolled back

The login and the list were removed and the broker restored to its previous
configuration. The collector's login was then tested again and refused. The
password was destroyed everywhere it had been written, along with the test
message the collector had published.

### What stands

The collector exists as a real node with the collector role. From it, with a
positive control, the grants were measured rather than assumed: the broker port
is reachable, and the automation UI, the hub's SSH, production and both sockets
are all refused. That is the first time the policy's refusals have been seen
from a live node of the role rather than only in its tests.

### The next design reverses the direction

The collector does not need to reach into the home at all. The hub will push
readings out to the collector instead: one grant from the hub to the collector's
ingest port, and the collector's grant into the home withdrawn entirely. No
broker, and no shared secret — the connection's tailnet identity is the
credential, because the policy lets nothing else reach that port. The collector,
which lives outside the house, then has no way in.

## D-049 — Telemetry is pushed out of the house, not pulled from it

### The change

The collector's grant into the home is withdrawn. In its place the hub may open
one port on the collector:

| before | after |
|---|---|
| collector → hub, broker port | hub → collector, ingest port |

The collector now reaches nothing inside the house. The tests say so from its
side — the broker, the automation UI, the hub's SSH, the push port in the
reverse direction and both sockets are all asserted refused — and from the
hub's side: it may deliver to the ingest port and may not administer the
collector.

### Why the direction matters

The collector is the more exposed of the two machines: it lives outside the
house, on a cloud host that other work also uses. The hub is the most trusted
node inside it. A pull design gives the exposed machine a standing path into
the trusted one, and D-048 showed what that path led to — a broker whose access
list is not enforced. A push design gives the trusted machine a path out to one
port, and the exposed machine no path in at all. If the collector is
compromised, the house is not reachable from it; that is now a tested claim
rather than an intention.

The cost is accepted: a compromised hub could send the collector false
readings. The hub already controls every device in the house, so this adds
nothing it could not already do.

### No broker, and no shared secret

Nothing in the push path touches the home broker or its existing clients. The
policy is the credential: the ingest port is reachable only from the roles the
policy names — the hub, and later the sensor and mobile-unit roles that were
already granted it. The receiver listens only where tailnet traffic arrives, so
nothing else on the cloud host reaches it either.

### Order of work

1. Policy: validated by CI against the live tailnet, applied by hand with the
   live file hashed against the render, merged, then drift-checked.
2. Receiver on the collector node. Reversible by removing one container.
3. The hub's side — one outbound call on a timer, one reading. This changes
   the household's automation hub, so it is agreed with the session that knows
   the house before anything is applied, and applied by the owner: the address
   lives in the hub's secrets file, the call has a short timeout, and nothing in
   the house waits on it. The hub had never loaded the component that makes
   the call, so the first load is a full restart of the hub — the household's
   price for the lab's stream, a minute or two without the camera feeding the
   pet-fountain automation. The owner accepted that cost. The configuration is
   validated before the restart, which guards the different risk of a restart
   that does not come back, and the house is checked afterwards by the session
   that knows it.

Acceptance is the one the outside review set (D-046): the collector reads as a
live node; a reading sent by the hub arrives at the collector; the reverse
direction on the same port is asserted refused and passes.

### The receiver, measured

Deployed before the policy change, so the change could be seen taking effect.
It binds to the node's tailnet address only. Measured, each with a control:

- from an operator's laptop, to the ingest port: refused — no grant names it
  (control: the same laptop reaches the hub's UI, which is granted);
- from the cloud host itself, to the container's bridge address: refused —
  nothing listens there;
- from inside the node's own namespace: accepted, one self-test reading
  written. The service works; only the policy stands between it and the house.

### The first reading, and what was measured around it

The policy change was applied by hand after CI validated it, the live file
hashed byte-identical to the render, and CI's drift check agreed after the
merge. Then, from the collector node itself, every port on the hub it was
tested against was refused — including the broker port, which the same node
had reached before this change (D-048). That is the before/after for this one
grant, measured rather than inferred.

The hub side was applied by the session that manages the house, with the
owner's approval there: configuration validated, one restart of about two
minutes, then every dependent integration checked back. The first reading,
fired by hand:

| | |
|---|---|
| sent by the hub (its clock) | 23:52:57.58 UTC |
| arrived at the collector (its clock) | 23:52:57.91 UTC |
| response | 204 |
| sender, as the collector's own node identified it | the hub, `tag:gateway-home` |

The sender is identified by the tailnet, not by an address the receiver
trusts. A test request sent earlier from a container behind the hub arrived
with the hub's identity too: the tailnet sees machines, not the processes on
them, so "the hub" here means anything the hub's host lets out.

The first unattended push followed on the five-minute tick (sent 23:55:00.44,
arrived 23:55:00.52, 204) and the stream has repeated on its own since.
Nothing is buffered on the hub, so a gap at the collector is a lost reading —
which is what the lost-comms drill (R-3) will count.

### What the restart cost the house, stated as checked

Checked after the restart by the session that manages the house, not assumed:
every integration came back, and no automation is unavailable. Of the
camera-derived entities the pet-fountain automation depends on, all are
present and all but one hold a value; the exception holds a value only after
the recorder publishes its next event, which needs the cat. The automation
itself is on and still reads the occupancy sensor, which is live again. It has
**not yet been seen to fire** since the restart — that also needs the cat, and
it stays an open item until it does.

## D-050 — The evidence page keeps itself current, and still holds nothing

### What changed

The page used to be true as of its build. Two things made that weaker than it
looked. A push starts the checks and the page at the same moment, so the page
routinely published the reading from the change before; and between builds,
nothing on it moved except the ages.

- **The page rebuilds when a check on main finishes**, not when the push lands,
  so it carries the run it is about.
- **A live layer in the visitor's browser** reads GitHub's public Actions API —
  the same record the build reads — with no token. It shows what is running
  this minute, job by job and step by step; lights the arrow on the diagram
  that the running check travels; and moves a card forward when a newer run of
  its check has finished. A card whose claim needs the run's log — "the plan
  reports no changes" — is not flipped by the browser, which cannot read logs
  without a credential; it says a newer run exists and waits for the rebuild.
- **The budget is visible.** GitHub allows sixty unauthenticated requests an
  hour per visitor address; the page reads every three minutes when idle, every
  thirty seconds while something runs, never while the tab is hidden, and waits
  for the reset when fewer than eight are left. It says how many remain.

### What it deliberately does not do

**It does not start anything.** A button that starts a check needs an endpoint
holding a credential that can dispatch workflows, exposed to the public. The
page holds none, and that is the property worth keeping. If a button is ever
added it belongs behind a small function with a capped, audited dispatch —
listed as not built, with that price, on the page itself.

### Also on the page now

- **What is in the project and not built**, each with why and what it would
  take, read from a file in the repository. An item leaves the list when it is
  built. The diagram's grey tiles say "not built" instead of implying a fleet.
- **Its own domain.** A single `CNAME` in the parent zone, the domain bound to
  the repository's Pages site, and HTTPS enforced once the certificate issued.

### A second stream: cat visits, as events

The pet camera — the one camera the owner released for the lab — joins the
stream the same way, pushed and never pulled. The collector gets no path to the
camera, the recorder, or the house, and holds no camera credential.

- **Events, not images.** At the end of each visit the hub sends the recorder's
  event: its id, start and end, the label, and two scores. The session that
  manages the house chose the source: the recorder's own end-of-visit event
  rather than the occupancy sensor. The sensor reads "no cat" when the detector
  is dead, gives no score, and has no id to check afterwards; an event id can
  later be joined to human verdicts on whether it really was the cat.
- **Named, never addressed.** The trigger filters on the camera's name in the
  recorder. The recorder itself reaches the camera by an address, and that
  address is not reserved: the house re-verifies it by hardware identifier.
  That check belongs to the house, which is recorded there; the lab's part is
  never to name anything by address.
- **Images stay home.** Frames from this camera routinely contain people
  crossing the room. Sending footage to a new destination is the owner's
  decision, and it was not asked for.
- **Cost: none to the house.** The call component was already loaded, so this
  took two configuration reloads, no restart.

Delivery was proven first with one real past event sent by hand — the command
called directly, and nothing published on the house's message bus. The trigger
was proven by the cat twenty minutes later: a 443-second visit whose end
reached the collector about 0.65 s after the recorder closed it (three clocks,
so approximate), identified as sent by the hub. It had looked missing for eight
minutes only because the event had not ended.

## D-042, closed — production's SSH is off the internet

Done in the order D-042 set, each step verified before the next:

1. **The desktop application restarted onto the tailnet path.** Before: 190
   logins over the public address in a week, the last one minutes before the
   restart. After: none; every login and every live session arrives from a
   tailnet address, the remote session included — confirmed from the host's
   own socket table, not from the session's environment, which still carried
   the address it was started with.
2. **The host's tailnet key no longer expires.** It would have dropped off the
   tailnet in six months, and with the public path closed that is a lockout.
   Tagged infrastructure should not expire under its operator.
3. **The only way in is asserted.** A policy test now requires the operator to
   reach `tag:prod:22`, so a policy change that dropped it fails before the
   tailnet accepts it.
4. **A snapshot, then the firewall.** The rule that admitted `22/tcp` from
   `0.0.0.0/0` and `::/0` is gone. Port 22 now admits only the cloud provider's
   own browser-console range — the break-glass path stays, everything else is
   refused.

Verified afterwards: SSH over the tailnet works; the public address times out
where it answered before; every live session on the host is on the tailnet.
The stale `80/tcp` rule for `::/0` belongs to the other project on this host
and is left to it.

Not yet done: **the break-glass path has not been exercised.** It should be,
once, before it is needed.

## D-051 — The policy cut the household's own paths, and its tests guarded only the lab's refusals

### What happened

Before this policy the tailnet allowed everything, and the household relied on
that without writing it down. Phase 2 replaced it with deny-by-default and
granted the one household path I knew about: the automation hub's UI. The
session that manages the house found the rest — by measuring, with the owner
away from home — and listed every path the house depends on. Two had been cut
since the day Phase 2 was applied, and nothing had noticed:

- **SSH from the owner's devices to the home server.** It carries the server's
  duty timers, the recorder tunnel, and the laptop's remote wake.
- **SSH to the hub's shell.** Worse than an omission: a test *required* it to be
  refused. I had judged that an operator needs the UI and not a shell. That
  shell is the documented reason the house uses Tailscale at all: when the
  automation hub is broken, its UI is gone and the shell is the only way to fix
  it from outside. The laptop's hourly backup of the hub rides on it too.

### Why the tests missed it

Thirty-one of the policy's assertions are refusals and a handful are accepts,
all about the lab's own roles. The household appeared once, as the UI. A test
suite built to prove that paths are refused proves nothing about the paths
nobody listed. Least privilege applied to a household you have not inventoried
does not reduce its exposure; it removes its recovery paths.

### What changes

- SSH between the owner's own devices is granted back, `autogroup:member` to
  `autogroup:self` on 22 only — nothing a member does not already own, and no
  tagged node — and asserted. The assertion was committed first without the
  grant and the tailnet refused it, so it is known to reach the path.
- The hub's shell is put to the owner as a separate decision, because it
  reverses a refusal the policy asserted on purpose.
- The household's paths are now an inventory kept by the session that manages
  the house, and every path on it is to carry an accept assertion here. The
  route to the whole home subnet stays ungranted: it would expose every camera
  on the network, and only one is released.

**Update, same night.** The owner decided the hub's shell: members may reach
`tag:gateway-home:22`, asserted as an accept, and every other role — collector,
sensors, mobile units, the appliance, production — is now asserted refused it.
The diagram shows the house's recovery paths it draws from the policy, and,
for the first time, the two home devices the lab uses without any route to
them: the released camera, whose visits reach the collector only as events
pushed by the hub, and the robot vacuum, the unbuilt mobile unit's candidate.

**A correction to D-040, found in the same change.** D-040 recorded that the
control plane stores the policy file verbatim and reformats nothing, and the
template repeated it. The drift check after this apply disagreed: the live file
was 20 bytes longer than the render. The console had expanded one test's deny
list — a single line that had grown past a width — into one entry per line;
with that list written the same way, the render matched the live file byte for
byte. The D-040 test was true only because every line it saved was already in
the console's format. The integrity check stands, since a file in that format
is stored as given; long lists are now written one entry per line, and the
drift check, not the claim, is what catches it.

**D-049, the last open item closed.** The first real visit after the hub's
restart was checked by the session that manages the house: the occupancy
sensor turned on and off with the cat, the pet-fountain automation held and
released the pump on time, and the lab's own automation ran once. The visit
event at the collector matches the recorder's stored record on id, label,
camera, start, end and the median score. The single-frame score does not — it
moved between the live message and the stored record — so the median is the
field that counts, and the other is never used to join or compare.
