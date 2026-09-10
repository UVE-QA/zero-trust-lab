# Zero Trust Lab — Implementation Handoff

**Status:** Phase 0 in progress
**Audience:** the next session that picks this up

> **Sanitised copy.** The working original lives in `local/` and is never
> committed. Real hostnames, addresses, the tailnet domain, device models, the
> ISP, the AWS account id and anything describing the physical layout have been
> replaced with role names and placeholders here. The substitution table is in
> `local/`. `scripts/leak-sweep.sh` enforces the boundary on every commit.

---

## 1. What this is

A working Zero Trust reference implementation built on real hardware, not a
simulation. It doubles as a portfolio artifact for infrastructure/security roles
that ask for "designed or maintained zero-trust, WireGuard-based networks."

The lab models a distributed field-operations topology — a telemetry collector,
remote sensors that cannot run an agent, a gateway per site, operator devices of
varying trust — using a home tailnet where every one of those roles already
exists physically.

**Deliverable:** a repo from which the entire access model can be rebuilt from
scratch, with tests that block unsafe policy from ever being applied.

---

## 2. Hard constraints — read before designing anything

### 2.1 No identity provider

There is **no IdP**. The tailnet authenticates with passkeys; the account is a
`@passkey` identity, not a federated one.

Consequences the worker must design around:

- **No SCIM.** No group provisioning, no automatic deprovisioning. Groups can
  still be declared manually in the `groups` section of the policy file — they
  just have to be maintained by hand.
- **Do not attempt to use AWS IAM Identity Center as the tailnet IdP.**
  Tailscale authenticates over OIDC; Identity Center federates to third-party
  applications primarily over SAML. Treat this as unsupported unless verified
  otherwise against current Tailscale docs. Do not build the design on it.
- **Build the policy on tags and autogroups.** They are available on every plan
  and they are the right unit anyway: a tag is a role in the system, and roles
  are what the model is about. Groups and users can be added later without
  restructuring.

This constraint is not a defect of the lab — it is the realistic starting state
of an early-stage company, and documenting how far Zero Trust can be taken
*without* an IdP is itself the interesting result.

### 2.2 The tailnet is in production for a household

The home automation hub, the cameras and the connected appliances are used daily
by people who did not volunteer for this experiment. If no access rules are
defined at all, Tailscale applies a default allow-all policy — which is almost
certainly the current state. The first restrictive policy will break things.

**Mandatory before the first policy change:** export the current policy file to
`policy/policy.baseline.hujson` and commit it. That is the rollback target.

### 2.3 Devices that cannot run the client

Cameras, radio-attached appliances and Thread/Matter devices have no Tailscale
client and never will. They are reachable only through a gateway. This is the
whole point — it mirrors field sensors exactly.

### 2.4 What Tailscale does not solve here

Vendor cloud traffic from cameras and appliances is out of scope: Tailscale
secures traffic between tailnet nodes and does not protect a device from any
other traffic. LAN-level isolation of IoT is a VLAN/firewall concern and belongs
in the docs as a known gap, not in the policy file.

### 2.5 The tailnet is on the Personal (free) plan

Confirmed. This is a design constraint, not a detail.

**Verify current limits against the comparison table on the pricing page before
starting.** Tailscale reworked its plans on 8 April 2026 — Personal Plus was
retired and its six-user allowance folded into the free Personal plan. Any
documentation page that still reads "Personal, Personal Plus and Enterprise" was
written before that rework and cannot be trusted on availability. Third-party
sources also disagree with each other. The pricing page is the only authority.

As published mid-2026, Personal gives six users, unlimited user devices, and
roughly 50 tagged resources, with most features available. Device posture
checks, device approval and network flow logs begin at Standard; just-in-time
access begins at Premium; basic Tailscale SSH on Personal is capped at five
hosts.

Consequences for the phase plan:

- **Phases 0–2 run on the free plan indefinitely.** Tags, `/32` routes,
  deny-by-default grants and the `tests` section — the core of the lab and its
  most valuable part — cost nothing.
- **The tagged-resource cap bounds the simulated fleet.** Four tags go to real
  infrastructure, leaving roughly forty-five for simulated sensors. Ample, but
  `fleet-down.sh` must actually clean up or the tailnet will hit
  "Reached use limit" and block unrelated work.
- **Phases 3 and 4 are gated.** Run them as a time-boxed sprint on a business
  trial — Tailscale recommends signing up with a separate work email to get the
  full feature set — or on one month of a paid seat. Capture the result as
  documentation and a screen recording committed to the repo. The artifact
  outlives the subscription; the subscription should not outlive the sprint.

Do not design around a feature without confirming it is available on the plan
actually in use at the time of implementation.

### 2.6 Blast radius — smaller than it looks, but aimed at the wrong things

Another household member uses the automation hub daily. The appliances depending
on it are pet-care devices.

**Access rules do not affect local network traffic.** They are deny-by-default,
directional and enforced at the node — traffic between devices on the same LAN is
outside their scope. The hub talking to those appliances over the local network
is therefore unaffected by any policy in this repo, no matter how restrictive.

What is actually at risk is **remote** access to the automation UI, from outside
the house. That is the entire blast radius.

Two rules follow:

- **The pet-care appliances are out of scope.** They are not exposed to the
  tailnet, they get no routes, and no experiment touches them. There is nothing
  to gain — they are already outside the policy's reach — and an appliance
  someone depends on daily is not an acceptable cost for a lab.
- **A grant for household access to the automation UI goes in the first policy
  commit**, with an `accept` test covering it. That test must fail the build if a
  later change breaks it. The one thing that can genuinely break should break CI,
  not someone's evening.

### 2.7 The repo is private now and public later — build for public from commit #1

Public release is wanted but not at the cost of exposing the home network.

**Decision: create the repo private, hold it to public-grade hygiene from the
first commit, flip it to public when it is ready.** Do not create it public
immediately, and do not plan to sanitise later. Git history is permanent —
"we'll clean it before publishing" means rewriting history, which is unreliable
and visibly awkward. Flipping a clean private repo to public is safe; cleaning a
dirty one is not.

What must never enter the repository, in any commit:

- Terraform state or plan output. State holds secrets in plaintext.
- Private keys, certificates, auth keys, OAuth client secrets, API tokens.
- Real device names or models, the tailnet name, or its MagicDNS domain.
- Real addresses — tailnet CGNAT addresses and private LAN addresses.
- The AWS account id.
- Camera count, placement, the ISP, or anything describing physical layout.

**Split the threat model.** `docs/00-threat-model.md` stays generic and
publishable: actors, asset classes, what the architecture defends against and
what it provably does not. The specific findings — which device is exposed, over
which port, and what that leaves reachable — live in the private overlay. The
generic document is the one worth reading anyway; the specific one is an attack
map for a particular home.

**Mechanics:**

- `local/` is in `.gitignore` from commit #1 and holds every real value:
  inventory, addresses, ARNs, account id. The repo ships
  `local/inventory.example.yaml` with placeholder values only.
- `.gitignore` also covers `*.tfstate*`, `*.pem`, `*.key`, `.env`.
- The policy file is tag-based almost throughout; the only real-world values in
  it are the `/32` host routes. Template those from `local/inventory.yaml` and
  render at apply time rather than committing rendered output containing real
  addresses.
- Terraform takes the account id as a variable, never a literal.

**Sanitisation is a test, not a checklist item.** `.github/workflows/leak-scan.yml`
runs on every PR: a secret scanner over full history, plus `scripts/leak-sweep.sh`,
a regex sweep for tailnet and LAN address patterns, a twelve-digit account id, any
MagicDNS domain, MAC addresses and credential formats. Site-specific strings —
device names, the tailnet name — are supplied to CI through the `LEAK_DENYLIST`
repository secret so the denylist itself never enters the repo. A hit fails the
build. Same principle as the policy `tests` section: the repository refuses a bad
commit rather than relying on someone remembering. Run it locally before
committing — CI catching a leak on a pushed commit is already too late.

A repo that enforces its own disclosure boundary is itself part of the portfolio.

---

## 3. Where the worker runs — decision

**Run locally on the operator laptop. Do not run this from the Linux server, and
not from the shared desktop either — see below.**

Rationale, in priority order:

1. **Lockout.** The work consists of changing who can reach what over the
   tailnet. The Linux server is reachable *only* over the tailnet. An agent that
   applies a grant which drops its own SSH path terminates mid-run and cannot fix
   what it broke. The laptop has a physical console and is never dependent on the
   artifact under test.
2. **The Linux server is a target, not an operator.** It plays the production
   server in the model. Rules will be written that deliberately restrict access
   to it. Something that is being tested should not be the thing running the test.
3. **Line of sight to the IoT segment.** The automation hub and the IoT devices
   are on the home LAN. The laptop reaches them directly. The Linux server can
   only reach them *through the subnet router being configured* — so it cannot
   independently verify that the router is working.
4. **Credentials live locally.** AWS SSO session, git identity, Tailscale OAuth
   client secret.

**Which machine: the laptop, not the shared desktop.** The shared desktop is
another household member's daily machine, it runs the NVR, and it is itself a
subject of the lab as a user-owned node in posture scenarios. Running the
operator on a machine that is simultaneously under test and someone else's
workstation repeats the Linux-server mistake with domestic consequences.

**The laptop drops off the network when it sleeps. Treat that as a design
requirement, not an obstacle.** If a sleeping laptop can break the lab, something
is resident on it that should not be. The worker's host must be stateless: the
repo is in git, Terraform state is in S3, and long-running observation belongs on
always-on nodes. Sleep then costs exactly one re-run of one command.

Rules that follow:

- **Anything long-running lives on the Linux server under tmux**, driven from the
  laptop. The container fleet, and any step measured in hours, run there.
- **Drills are instrumented by the always-on side.** The lost-comms drill is
  measured by the telemetry stream arriving at the collector, never by a process
  on the laptop.
- During a session, hold sleep off with `caffeinate -dimsu` in a separate
  terminal. Note it does not survive closing the lid — on battery the machine
  sleeps regardless — so keep the lid open or stay on power.

**What still runs on the Linux server:** the simulated sensor fleet (Linux
containers), driven over SSH from the laptop. It is managed, not resident.

**Safety net to establish before any policy work:** the Tailscale admin console
is reached over the public internet, not over the tailnet, so a bad policy cannot
lock anyone out of the console. Confirm admin console access from a phone on
cellular before starting. That is the break-glass path.

---

## 4. Repository structure

```
zero-trust-lab/
├── README.md                      # what this is, how to run it, current state
├── STATUS.md                      # living: done / in progress / next
├── Makefile                       # make validate | plan | apply | audit | fleet-up
│
├── docs/
│   ├── 00-handoff.md              # this file (sanitised)
│   ├── 00-threat-model.md         # actors, assets, what we defend against
│   ├── 01-inventory.md            # roles and counts only; real values in local/
│   ├── 02-decisions.md            # ADR-style, append-only, why not just what
│   ├── 03-topology.md             # diagram + data flows
│   └── runbooks/
│       ├── offboarding.md
│       ├── lost-device.md
│       ├── rollback-policy.md
│       ├── lost-comms.md
│       └── rehome-collector.md
│
├── policy/
│   ├── policy.hujson              # the tailnet policy file — single source
│   ├── policy.baseline.hujson     # pre-lab snapshot, never edited
│   └── README.md                  # tag taxonomy, naming rules
│
├── terraform/
│   ├── aws/
│   │   ├── archive.tf             # S3 + Glacier lifecycle for camera archive
│   │   ├── roles-anywhere.tf      # trust anchor + profile + role for collector
│   │   ├── github-oidc.tf         # OIDC provider + deploy role for this repo
│   │   ├── identity-center.tf     # permission sets, internal-store groups
│   │   └── backend.tf             # S3 state + DynamoDB lock
│   └── README.md
│
├── scripts/
│   ├── leak-sweep.sh              # disclosure sweep; runs in CI and locally
│   ├── inventory-audit.py         # nodes with expiry off / stale / untagged
│   ├── jit-grant.sh               # set custom posture attr with expiry
│   ├── jit-revoke.sh
│   ├── fleet-up.sh                # N ephemeral tagged containers on the server
│   └── fleet-down.sh
│
├── local/                         # GITIGNORED — every real value lives here
│   └── inventory.example.yaml     # committed; placeholders only
│
└── .github/workflows/
    ├── policy-check.yml           # PR: validate + run policy tests
    ├── policy-apply.yml           # main: apply policy file
    ├── leak-scan.yml              # PR: secret scan + disclosure sweep
    └── terraform.yml              # PR: plan / main: apply
```

### Ownership split — important

- **The tailnet policy file is managed by the GitOps workflow, not by
  Terraform.** Tailscale publishes an official GitOps ACL action for exactly
  this. Two systems writing the same global file will fight.
- **Terraform owns AWS only.** State in S3 with locking.

Record this in `docs/02-decisions.md` as decision #1.

---

## 5. Tag taxonomy

Tag by role in the system, never by hardware model or owner.

```
tag:collector      # telemetry / NVR sink
tag:prod           # the production server stand-in
tag:gateway-home   # subnet router for the IoT segment
tag:sensor         # simulated push-only field sensors
tag:drone          # simulated mobile units (telemetry + control channel)
tag:kiosk          # media appliance — deliberately isolated, appears in no src
```

Operator devices stay user-owned (not tagged) so posture can be evaluated on
them. A device with many tags inherits the union of all their rules and the
policy becomes unreadable fast — keep the taxonomy small and document it in
`policy/README.md`.

**The collector has no dedicated host yet.** The NVR runs on a machine that is
also someone's daily desktop, so that machine stays user-owned and untagged.
Until dedicated hardware is deployed, `tag:collector` has no home and
collector-side grants cannot be exercised against the real NVR. Model the
collector role with a container on the Linux server for policy and test purposes,
and note in the decisions file that the real collector joins at deployment — that
moment is the `rehome-collector` runbook.

**Real temperature/humidity sensors are available and should be used — for the
data path, not for identity work.** Several exist; some are unbound from
automations and one spare can be dedicated to the lab outright.

They are not network hosts. They speak a low-power radio protocol to a border
router, have no IP presence of their own, no tailnet node and no key. The
blast-radius drill cannot be run against them because there is nothing to leak.
The container fleet is still required for anything involving machine identity.

What they give instead is the real telemetry path: sensor → gateway over radio →
collector over the tailnet. Only the second hop is governed by policy, and that
is exactly the shape of a field deployment — sensors reach a site gateway over a
non-IP radio, and the gateway forwards telemetry onward. More honest than a
container pretending to be a sensor.

**Transport for that hop is MQTT — decided, do not re-litigate.** Rationale: the
automation hub supports it natively, the grant is trivial to express and to test,
and counting missed readings at the receiving end is straightforward — which is
what makes the spare sensor usable as an instrument in the lost-comms drill.

**A broker very likely already exists. Find it before standing one up.** The NVR
publishes detection events over MQTT, so Mosquitto is probably already running —
either as an add-on on the automation hub, or as a process on the desktop
alongside the NVR. Locate it first:

```
ps aux | grep -i mosquitto
lsof -nP -iTCP:1883 -sTCP:LISTEN
```

and check the hub's add-on list, plus the host configured in the NVR's own MQTT
settings.

**The grant direction depends on where it lives, so do not write the rule before
confirming:**

- Broker on the automation hub — it sits on the gateway, and the collector
  subscribes across the tailnet:
  `{ "src": ["tag:collector"], "dst": ["tag:gateway-home"], "ip": ["tcp:1883"] }`
- Broker on the desktop beside the NVR — matches the original shape, but that
  machine is a user-owned node, not a tagged collector. Either move the broker or
  record that the collector role temporarily lives on a user-owned node.

**Treat the existing broker as a shared component.** Once the lab publishes to
the same broker that the NVR and the hub already depend on, it stops being a
lab-only piece. Two rules follow: the lab uses its own credentials and its own
topic prefix, and **no reconfiguration is made that affects existing clients.**

That last rule overrides an earlier instruction. Binding the broker to the
tailnet interface only is no longer on the table — it is almost certainly
listening on all interfaces so that the NVR can reach it over the LAN, and
rebinding would break a working system. So the plaintext-on-LAN exposure stays,
and it is recorded in `docs/00-threat-model.md` as a **finding**, not as
something to fix. Inheriting a system you are not entitled to redesign is
precisely the situation this lab exists to model; documenting the residual risk
honestly is the correct output, not silently removing it.

Tests to write regardless of direction: the reverse direction on 1883 is denied,
and no sensor, kiosk or socket can reach 1883 at all.

**Dedicate the spare sensor as the lab's measuring instrument.** Its readings
traverse the whole chain to the collector, so a gap in the stream is objective
evidence that something broke and exactly when. This turns the drills from
impressions into numbers — see Phase 6.

**Smart sockets add the actuator class the lab is otherwise missing.** A couple
are available. Everything else in the model is read-only — a sensor reports a
number, a camera emits a stream — and a read-only model makes tiered access look
arbitrary. A socket changes physical state, which is a different class of risk
and the one that justifies the stricter controls.

The resulting ladder, which is what Phases 3 and 4 should demonstrate against:

| Class | Example | Control |
|---|---|---|
| Telemetry | temp/humidity sensor | plain grant, no posture |
| Stream | camera | grant plus source posture |
| Action | smart socket | posture plus time-boxed JIT |

This mirrors a drone's control channel versus its telemetry, and it is far more
convincing than demonstrating just-in-time access for the right to read a
temperature.

**Use the WiFi socket, not the Thread one.** Both are available as spares. Only
the WiFi socket is an IP host: it has an address on the LAN and a port, so it can
be the target of a route and of a grant, which is precisely what the action tier
needs — a rule to a specific host and port that exists only inside a JIT window,
with a test to prove it. A Thread socket has no tailnet-side presence and is
reached through the border router and the automation hub, behaving identically to
the temperature sensor already in scope; a second instance of that behaviour adds
nothing.

The WiFi socket is also the more honest subject. A cheap WiFi actuator on a flat
network is exactly what least privilege is meant to contain, whereas a Thread
device is isolated by its own protocol and makes the controls look more effective
than they are. Keep the Thread socket for the smart home proper.

**The socket has been identified: a HomeKit-over-WiFi accessory, not Matter.**
That is fine — Matter is not what the lab needs. The requirements are an IP host
on the LAN and local control, and HAP over WiFi provides both. Do not spend
effort chasing a Matter device.

The real question is where control lives, and there is a fork:

- A HomeKit accessory pairs to exactly one controller. It is currently paired to
  the phone-vendor's home ecosystem, so local control runs through that
  ecosystem's hub and the automation hub cannot reach it locally. In that
  configuration the actuator sits outside the gateway's scope, which defeats its
  purpose here.
- The vendor-specific local-LAN integration is not a way out. On
  HomeKit-variant firmware the device validates TLS strictly and will not connect
  to a local broker with a self-signed certificate — a firmware wall, not a
  configuration problem. Replacement firmware is also out; the hardware is not
  ESP-based.

**Decided: unpair it from the phone-vendor ecosystem and add it to the automation
hub via its HomeKit Controller integration.** Confirmed acceptable by the owner.
The hub then drives it locally over HAP with no cloud round trip, and the
actuator falls under the gateway like everything else. The socket is a seasonal
one currently switched off, so unpairing it costs nothing.

Useful side effect: HAP advertises over Bonjour, so this device resolves reliably
by mDNS name. It needs no static address and Option B covers it directly.

Same scoping rule as the pet-care appliances: **only a spare socket, driving
something inconsequential.** A socket anything depends on does not enter the lab.

**The robot vacuum is not a participant.** It reaches the vendor cloud directly
and will continue to under any policy in this repo. Use it in
`docs/00-threat-model.md` as the concrete illustration of the limitation in
section 2.4 — a device on the network whose traffic access policy does not touch,
and the reason that gap needs VLAN-level treatment rather than more grants. It is
more useful as an example than as a node.

**A node is either user-owned or tagged — not both.** Tagging a device strips
the owning user's identity from it and replaces it with the tag's. Never tag a
personal daily-driver machine to give it an infrastructure role: you lose it as a
user device for posture work, and you gain a production role on a laptop that
someone carries around. Infrastructure roles belong on dedicated hardware, or on
a container/VM until dedicated hardware exists.

---

## 6. Implementation phases

Each phase ends with a commit, a `STATUS.md` update, and the stated acceptance
check passing. Do not start a phase before the previous one's check passes.

### Phase 0 — Capture and inventory

- Export current policy file → `policy/policy.baseline.hujson`. Commit first.
- `scripts/inventory-audit.py`: every node with tags, owner, key-expiry state,
  last seen. Real values to `local/inventory.yaml`; only roles and counts to
  `docs/01-inventory.md`.
- Confirm admin console reachable from a phone off-tailnet.
- Land `.gitignore`, `local/` and the `leak-scan.yml` workflow **in the first
  commit**, before any real value is written down anywhere. The inventory goes
  into `local/`, not into `docs/`.
- **Qualify the spare WiFi socket in the automation hub.** Three checks, all in
  the hub UI:
  1. *Transport.* Devices & Services. If the socket sits under the Matter
     integration, open Thread and check whether it appears in the Thread network
     topology. A Matter device absent from the Thread mesh is Matter-over-WiFi.
     Cross-check that it holds an ordinary LAN address.
  2. *Local control.* The integration page states how data is updated — Cloud
     Polling, Local Polling or Local Push. Cloud Polling means switching goes
     through the vendor and no access policy governs it.
  3. *Address.* Confirm it resolves by mDNS from the gateway; HAP devices
     advertise over Bonjour, so this should hold and no static address is needed.

  For this particular socket, expect to unpair it from the phone-vendor ecosystem
  and re-pair it to the hub via HomeKit Controller — see section 5. Record the
  outcome in `local/inventory.yaml`, never in `docs/`.

**Acceptance:** the baseline file is committed, the leak scan runs and passes on
the first PR, and the inventory table is complete. Every node has an assigned
intended role.

### Phase 1 — Tag the machine identities

- Re-authenticate every non-human node with a tagged auth key.
- Note in the inventory that key expiry is disabled by default on tagged devices,
  and which nodes that now applies to.

**Acceptance:** no infrastructure node is authenticated under a personal
identity.

### Phase 1.5 — Segmentation on a flat network

**Confirmed: the home network is flat. There is no IoT VLAN.** Do not treat this
as a blocker and do not rebuild the LAN to unblock it.

**Approach: advertise per-device `/32` host routes, not a subnet.**

```
sudo tailscale up \
  --advertise-routes=<device-a-ip>/32,<device-b-ip>/32 \
  --advertise-tags=tag:gateway-home
```

Each IoT device that needs to be reachable from the tailnet gets its own route.
Nothing else on the LAN is exposed. This is stricter than a narrow CIDR would
have been, requires no network surgery, and is the more instructive pattern
anyway: it maps onto exposing individual field devices rather than a whole site
subnet.

**Blocking constraint: the ISP-supplied gateway cannot reserve IP addresses.**
The `/32` approach as written depends on addresses that never move, and this
network cannot guarantee that. Do not build on `/32` routes until one of the
options below is chosen.

This is a genuinely useful finding, not just an obstacle — "the gateway at the
site is not ours and cannot be configured" is the normal condition of a field
deployment. Write it up that way in `docs/02-decisions.md`. A design that does
not depend on controlling the site network is better than one that does.

**Decision: Option B. Confirmed there is no spare router hardware, and no
hardware is to be bought for this lab.** Option A remains sensible but belongs to
the Thread/Matter and VLAN work, not here — if a router is bought later it should
be bought for that, with the lab benefiting as a side effect.

**Option A (deferred, not part of this work): put an own router behind the ISP
gateway.** It handles DHCP, reservations, and later VLANs. Double NAT is not a
problem for Tailscale — the ISP gateway is behind CGNAT already, there are no
inbound connections to lose, and NAT traversal falls back to DERP.

**Option B (preferred now, no hardware): stop addressing devices by IP.**
Run a forwarding proxy on the gateway node that exposes stable tailnet-side
endpoints and resolves the backing devices by **mDNS hostname** rather than by
address. Consequences:

- No DHCP reservations needed. An address change is absorbed by name resolution.
- No advertised routes at all, so no route approval and no `/32` maintenance.
- Access control becomes per-port on a tagged node instead of per-route, which is
  simpler to express and simpler to test.
- Cost: the forwarding configuration lives on the gateway host, not in the policy
  file, so it sits outside git unless scripted. Script it, commit the script, and
  make it idempotent — otherwise this becomes the one piece of the lab that
  cannot be rebuilt from the repo, which defeats the point.

**Verify before building on Option B — two things, neither assumed:**

1. ~~Where the gateway role can live.~~ **Resolved: the automation hub.** The
   always-on desktop running the NVR was considered and rejected — it is also a
   daily-use personal desktop for another household member, so it must stay
   user-owned and cannot be tagged. Running a second tagged `tailscaled` in a
   container on that machine is not a workaround: containers on macOS run inside
   a VM, host networking does not behave as it does on Linux, and LAN device
   visibility from inside is unreliable — which is precisely the capability the
   gateway exists to provide.

   So confirm what forwarding configuration the Tailscale add-on on the hub
   actually exposes. If it is too constrained, go to Option D, which suits the hub
   better than Option B anyway: it is already the source of truth for every device
   address, so the reconciliation script can live there and no forwarding
   configuration is needed at all.
2. **That each device resolves by mDNS name from the gateway.** One minute to
   check per device. A camera that does not register a hostname cannot use
   Option B and falls back to C or D.

**Option D (fallback if mDNS proves unreliable): reconcile routes from the
automation hub.** It already knows the current address of every device on the
network. A scheduled script pulls those addresses and syncs the corresponding
`/32` routes through the Tailscale API. This converts a missing DHCP feature into
an automation problem — less elegant than B, but fully reproducible from the repo
and entirely within the owner's wheelhouse. If used, it belongs in
`scripts/sync-routes.py` with the same idempotency requirement as everything
else.

**Option C (stopgap, per-device): configure a static address on the device
itself**, outside the DHCP pool. Only works where the vendor allows it — some
cameras do, many do not — and the ISP pool may span the whole subnet with no way
to shrink it, making collisions a matter of time. Acceptable for a single device,
not as the general approach.

If Option A, C or D ends up in use, the following still applies:

- **Static addressing is mandatory.** A `/32` route pointing at an address that
  moved is a silent outage. Pin every exposed device.
- **Maintenance is manual.** Adding a camera means adding a route and getting it
  approved. That friction is a feature — it keeps the exposed set small and
  visible — but it must be documented so it does not look like an oversight.
- **Route approval stays manual.** Do not enable auto-approval.

**Honest limitation to write down, not to hide:** on a flat network, anything
already on the LAN reaches the IoT devices directly, regardless of policy.
Tailscale governs tailnet-originated access only. The lab therefore demonstrates
control of *remote* access, not full segmentation. Say so plainly in the threat
model — a reviewer who spots the gap themselves will trust nothing else in the
repo.

**Why a VLAN is not being done now:** the household is moving toward
Thread/Matter, and Thread border routers and HomeKit discovery depend on mDNS,
which does not cross subnets without a reflector. Splitting IoT onto its own VLAN
would actively fight the smart-home project. If a VLAN is done later it is its own
piece of work with mDNS reflection designed in — not a side effect of this lab.

**Acceptance:** the chosen option is recorded as a decision with its verification
results; every exposed IoT device is reachable from the tailnet by a stable
identifier that survives a DHCP lease change; the tailnet has no route wider than
`/32` into the home LAN (or no advertised route at all, under option B); the
flat-network limitation is written into `docs/00-threat-model.md`.

### Phase 2 — Deny-by-default with tests

Write `policy/policy.hujson` from zero. Grants by port, never `*:*`.

Camera/RTSP path uses `via` so traffic is routed through the declared gateway:

```jsonc
{
  "src": ["tag:collector"],
  "dst": ["<device-a-ip>/32", "<device-b-ip>/32"],  // rendered from local/
  "ip":  ["tcp:554"],
  "via": ["tag:gateway-home"],
}
```

The `tests` section is the deliverable here, not an afterthought. Assertions run
on every policy save and a failing assertion causes Tailscale to reject the
updated file. The `deny` entries carry the value — an `accept` regression
announces itself when someone's connection breaks, a silent privilege expansion
does not.

```jsonc
"tests": [
  { "src": "tag:sensor",
    "accept": ["tag:collector:8443"],
    "deny":   ["tag:prod:22", "tag:collector:22", "tag:sensor:8443"] },
  { "src": "tag:kiosk",
    "deny":   ["tag:collector:8123", "tag:prod:22", "tag:gateway-home:8123"] },
]
```

Cover at minimum: sensor cannot reach prod; sensor cannot reach another sensor;
kiosk reaches nothing; collector cannot reach IoT ports other than RTSP.

**Acceptance:** policy applies cleanly, tests pass in CI, household access to the
automation UI still works, and at least one deliberately-broken policy is shown to
be rejected by the tests.

### Phase 3 — Posture *(gated: requires Standard or a trial)*

Device posture checks are not on the Personal plan. Run this phase and Phase 4
together as one time-boxed sprint on a business trial or a single paid seat.

Before starting the sprint, write the posture rules and their `tests` on the free
plan and leave them commented out. The sprint is then short: uncomment, apply,
verify, document, revert.

Note the architectural limit: **posture conditions apply to the source of a grant
only, never the destination.** Document this in the decisions file — it shapes
what the model can and cannot express, and it is worth knowing regardless of plan.

Policy tests can assert posture behaviour via `srcPostureAttrs` without physically
degrading a device — use that rather than downgrading a real laptop.

**Acceptance:** an unmanaged device is denied a path that a managed device is
granted, proven by a passing test, with the run captured as a screen recording and
written up in `docs/`. The write-up is the deliverable; the live configuration is
temporary.

### Phase 4 — JIT access *(gated: requires Premium or a trial)*

`scripts/jit-grant.sh` sets a `custom:` posture attribute with an expiry via the
API; a grant requires that attribute for SSH to `tag:prod`. Access appears on
request and disappears on its own.

Write and commit the scripts on the free plan — they are useful artifacts whether
or not they can be executed today. Execute during the same sprint as Phase 3.

**Acceptance:** SSH to the production stand-in works during the window and fails
after it, with no manual revocation step, recorded and documented.

### Phase 5 — AWS without static credentials

- **On-prem collector → S3 Glacier: IAM Roles Anywhere.** The device presents an
  X.509 certificate and receives temporary credentials. No permanent access key
  on a machine sitting in a living room. This is the on-prem answer to static keys
  and maps directly onto field sites uploading to cloud storage.

  **Dedicated collector hardware is not deployed yet and this phase does not wait
  for it.** Roles Anywhere binds to a per-device certificate, not to specific
  hardware — the trust anchor, profile and role are hardware-independent.
  Implement against whichever machine currently runs the NVR. When the dedicated
  machine arrives, issue it a certificate and revoke the old one; no Terraform
  changes. Capture that move as the `rehome-collector` runbook: replacing a field
  collector without touching cloud IAM is a more interesting artifact than having
  installed it correctly the first time.

  Note that the S3 bucket and Glacier lifecycle work is independent of which
  machine uploads, and can be done first.
- **This repo → AWS: GitHub OIDC federation.** No access key in repo secrets. The
  trust policy must constrain `sub` to this repo and branch — an unconstrained
  `sub` will accept a token from any GitHub Actions run anywhere. This is the
  single most common misconfiguration of the pattern; call it out in the decisions
  file.
- **Identity Center:** permission sets assigned to groups in the internal identity
  store, not to individuals. When an IdP eventually arrives, only the source of
  the groups changes.

**Acceptance:** no long-lived AWS access key exists anywhere in the lab.

### Phase 6 — Drills, written up as runbooks

Each drill produces a runbook plus an observed-results section.

- **Blast radius.** Register a node with a leaked sensor auth key. Verify it
  reaches exactly one port on one host and nothing else.
- **Lost device.** Time the path from "drone is gone" to "node revoked." Target
  under an hour; record what it actually was.
- **Offboarding.** Suspend, do not delete. Suspended users' devices may still
  appear connected but cannot exchange traffic. Inventory what would have broken
  had it been a delete — specifically any node authenticated under that identity.
- **Lost comms.** Physically disconnect the gateway for an hour. Record what
  degraded, what recovered unattended, what needed hands. This is the drill that
  matters most for field-operations work.

  Instrument it with the dedicated spare sensor: its reading stream is the
  objective signal. Record the timestamp of the last reading before the outage,
  the first after recovery, and how many readings were lost — and state whether
  the gap was buffered and replayed or simply dropped. "It came back" is not a
  finding; "telemetry resumed in 40 seconds with 12 readings lost and no replay"
  is. Use the same signal as a canary after every policy change: a stream that
  goes quiet means the grant is wrong.

**Acceptance:** four runbooks in `docs/runbooks/`, each with real measured
numbers, not aspirations.

---

## 7. Rules for the worker

- **Never apply a policy change without the tests updated in the same commit.**
- **One phase per PR.** The policy file is global and atomic; small diffs are the
  only way to attribute a breakage.
- **Ask before anything destructive.** Deleting users, deleting nodes, disabling
  key expiry, widening advertised routes. Confirm with the owner first.
- **Do not widen an advertised route to make something work.** If a route needs
  to be wider, that is a finding to document, not a fix to apply.
- **Write findings into the repo as they happen**, not in a batch at the end.
  Screenshots do not survive; text does.
- **The repo is the source of truth.** The next session should be able to start
  from `README.md` and `STATUS.md` alone.
- **Real values never leave `local/`.** Run `./scripts/leak-sweep.sh` before
  every commit.
- End of session: update `STATUS.md`, commit, push, and leave a primer for the
  next chat.

---

## 8. Open questions

Resolve these before Phase 2; they change the design.

1. ~~Is the IoT segment on its own VLAN?~~ **Answered: no, the network is flat.**
   Resolved in Phase 1.5 with per-device `/32` routes, then superseded by
   Option B.
2. Which IoT devices actually need to be reachable from the tailnet at all? The
   `/32` approach makes this an explicit list rather than a side effect — start
   with the smallest set that makes the lab meaningful and grow it deliberately.
3. ~~What Tailscale plan is the tailnet on?~~ **Answered: Personal (free).**
   See section 2.5. Phases 3 and 4 are gated behind a trial or a paid seat.
4. ~~Is dedicated collector hardware deployed yet?~~ **Answered: no.** The NVR
   runs on an always-on machine that is also a daily-use personal desktop, so it
   stays untagged. Gateway goes to the automation hub; the collector role waits
   for dedicated hardware. Phase 5 still proceeds against the current NVR host —
   Roles Anywhere binds to a certificate, not to a tag.
5. ~~Who else depends on the automation hub, and what is the acceptable blast
   radius?~~ **Answered: another household member uses it daily; the dependent
   devices are pet-care appliances.** See section 2.6.
6. ~~Should the repo be public eventually?~~ **Answered: public is wanted, but
   only if nothing sensitive is exposed.** Resolved in section 2.7 — private
   repo, public-grade hygiene from commit #1, flip when ready.
