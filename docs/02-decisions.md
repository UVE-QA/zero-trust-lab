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
