# Status

**Phases 0, 1, 1.5 complete** — merged. **Phase 2 applied**, in review.
Last updated 2026-09-09.

Eight phases in total: 0, 1, 1.5, 2, 3, 4, 5, 6. Phases 3 and 4 are gated
behind a paid plan or trial and run as one time-boxed sprint; 5 and 6 are
available on the current plan.

> **The tailnet is deny-by-default.** Seven grants, each naming a source role,
> a destination and **one port**. No `*` anywhere in the grants section.
> Anything not written down is refused. The household guarantee is the first
> grant in the file and carries an assertion (D-025).

> **Exposure into the home network is three hosts.** It was every host on the
> network, reachable through two wide routes; both are retired and the gateway
> now serves one route per exposed device (D-024).

---

## Done

| | |
|---|---|
| Disclosure boundary landed **before** any real value was recorded | `scripts/leak-sweep.sh`, `.github/workflows/leak-scan.yml` |
| `.gitignore` covers `local/`, `*.tfstate*`, `*.pem`, `*.key`, `.env` | verified, all five |
| Leak scan passes on the first PR, with the term denylist active | both jobs green on PR #1 |
| Sanitised handoff committed; the original never leaves `local/` | `docs/00-handoff.md` |
| **Baseline policy exported and committed** | `policy/policy.baseline.hujson`, byte-identical by digest — D-006 |
| Node inventory captured; every node has an intended role | `local/inventory.yaml`; public view in `docs/01-inventory.md` |
| MQTT broker located, not assumed | on the intended gateway node — D-004 |
| Actuator: check 3 run and recorded | it fails — D-005 |
| Question log started | `local/questions-for-review.md` |

The sweep is not decorative: it caught a real hostname left in the placeholder
example file while that very commit was being drafted (D-002).

## Open — needs the owner

### 1. Admin console from a phone off-tailnet — not verified (task 7)

**What was actually checked:** from the operator laptop the console resolves to
a public address, routes over the physical interface rather than the tailnet,
and returns HTTP 200. That establishes it is not a tailnet-dependent service.

**What that does not establish,** and the acceptance check asks for it: that the
console can be *reached and authenticated* from a phone on cellular with the
tailnet down. Passkey authentication on the phone cannot be inferred from a
routing table.

**Do this before any policy work.** WiFi off, open the console, confirm you can
sign in and reach the policy editor. One minute, and it is what makes a bad
policy recoverable.

### ~~2. Actuator~~ — **DONE.** All three checks pass (D-013)

**Resolved since the last update.** The transport check passes: the device is a
HomeKit-over-WiFi accessory, an ordinary IP host on the LAN, confirmed from its
own advertised records rather than inferred. The mDNS check passes too — see
D-007 for why it was first reported as failing.

The firmware question is settled **against** my earlier inference: it is the
HomeKit variant, so the handoff's §5 reasoning needs no amendment and the
local-integration route stays closed.

**Resolved:** both units are free for the lab and neither is needed by the
household. That is better than a spare — D-010 uses them as a matched
granted/denied pair, which demonstrates that least privilege here is per-host
rather than per-protocol. A single device cannot show that.

**Done since:** the owner released the granted unit from the other ecosystem. It
now advertises itself as unpaired, and the automation hub raised a pairing flow
for it **sourced from zeroconf** — which also closed the gateway-vantage
question (D-012). The denied control was left untouched throughout, as intended.

**The one remaining step:** complete the pairing in the hub's UI. The flow is
live and waiting on the accessory's setup code, printed on the device. That is a
pairing secret and is deliberately not routed through this session — it takes
the owner seconds in the UI. Check 2 is a formality once paired; the protocol is
local by construction.

### 3. Tailscale OAuth client — not blocking Phase 0 (Q-003)

The baseline export did not need it; a live console session was used and the
result verified by digest. But Phase 2 cannot land without it: the GitOps apply
workflow is decision D-001's whole premise. Q-003 lays out the scopes and argues
for two clients rather than one — a read-only client for PR validation, and a
write-scoped client used only on `main`, so a PR can never reach a credential
that rewrites the global policy file.

## Findings

| id | severity | summary |
|---|---|---|
| **D-003** | high | An approved `/24` route into the home LAN is already live, served by a user-owned personal desktop. The gateway role is not unassigned as the handoff assumes — Phase 1.5 is a migration, not a build. Not touched. Decision needed: Q-001. |
| **D-004** | info | MQTT broker located, not assumed. On the intended gateway node, plaintext on all interfaces, anonymous refused, no TLS. Settles the grant direction. LAN exposure documented as residual risk, deliberately not fixed. |
| **D-005** | ~~medium~~ | **RETRACTED — see D-007.** Claimed the actuator publishes no mDNS name. It does. The negative was a tool artifact. The rest of D-005 (all existing Matter actuators are Thread, so none is an IP host) still stands. |
| **D-006** | info | The baseline is the stock default: allow-all, plus root SSH to `autogroup:self`, which on a single-user tailnet is every machine. |
| **D-007** | — | Correction to D-005. The actuator publishes a stable mDNS name that resolves, so **Option B is viable**. The firmware is confirmed to be the HomeKit variant, so the handoff's §5 reasoning stands unamended and my earlier "standard firmware" inference was wrong. Both units are already paired, so adoption does require unpairing. |
| **D-008** | high | Measures what the subnet route is load-bearing for: **almost nothing.** Everything used remotely is already a tailnet node in its own right. The one real exposure is the site gateway's admin interface, published to the whole tailnet. Also establishes that route acceptance is a client-side toggle — not an access control. Corrects the ordering: policy first, then migrate, then withdraw. |
| **D-009** | — | The blast-radius measurement uses a disposable ephemeral node, not a loosened trusted one: nothing has to be remembered and undone, and it measures the leaked-key claim rather than a proxy for it. Deferred to the Phase 2 window, with the sequencing hazard written up. |
| **D-010** | — | Both actuators are free for the lab, so they are used as a matched granted/denied pair rather than one plus a spare. Proves least privilege is per-host, not per-protocol. Costs one device change, not two — the control needs no changes at all. |
| **D-011** | high | The granted actuator answers its local API over plaintext to a request signed with an **empty key** — no meaningful authentication at all, while its identical twin rejects the same request. The only thing between the local network and a physical state change is reachability. This is the lab's action-tier argument with evidence behind it, not a defect to patch. An addendum records that the unauthenticated read is **live state**, so anything on the LAN can watch the actuator in real time. |
| **D-012** | — | Closes the gateway-vantage discovery check left open by D-007 — and it closed itself, as a side effect of releasing the actuator. The hub raised a zeroconf-sourced pairing flow, which is the check answered from the right vantage point. Recording it as open rather than guessing was the cheaper plan. |
| **D-013** | — | Actuator qualification **complete**, all three checks pass. And the D-011 hole **survives adoption**: pairing the device to a managed platform did not close its unauthenticated vendor interface. "We moved it onto a platform we control, so it is handled" is false comfort — the network grant is the only control with authority over that path. |
| **D-014** | superseded | Reported the break-glass path broken and blamed a missing passkey. The observation was right, the cause wrong — see D-015. |
| **D-015** | superseded | **Correction.** The account authenticates via a consumer identity provider, not a passkey — the handoff's claim otherwise is factually wrong, and that unchecked premise shaped the wrong test and the wrong fix. |
| **D-016** | closed | **Break-glass verified**, phone on cellular, off tailnet. The gate on Phase 2 is lifted and no second credential was created. Records the guard: when a document supplies a fact about a system you can query, query it before building on it. |

### Phase 1

| id | state | summary |
|---|---|---|
| **D-017** | open | **Two** subnet routers into the home network, not one — the second is deliberate failover redundancy, and it is the node the model most wants isolated. The property that makes a good backup router is the property that makes a poor thing to trust: availability and least privilege pull opposite ways and both are right. Also corrects a device mix-up in D-008. |
| **D-018** | accepted | Tags assigned from the console rather than by re-authenticating with a tagged auth key: no credential minted, no re-registration on a node reachable only over the tailnet or one in daily household use, reversible in the same place. The handoff's method stays right for provisioning new nodes. |
| **D-019** | accepted | `tag:kiosk` renamed to `tag:appliance` — "kiosk" already means a display mode on two personal handhelds here, so the policy would have read as governing one device while governing another. General rule: do not name a tag after a word the environment already uses. |
| **D-020** | open | Tagging from the console does **not** disable key expiry, contrary to the handoff. Measured, not assumed. Better posture, but tagged nodes will now expire in ~6 months and re-authenticating them needs the auth key the method avoided minting. Trade-off left explicitly open rather than settled in passing. |
| **D-021** | — | Phase 1 applied and verified against a before/after baseline; nothing the household depends on moved. Names the unmet part of the acceptance criterion. Two operational facts: the service **reformats the policy on save** (false drift for the future GitOps check), and the console editor **can show an empty diff while holding new content** — make the UI show you the change before saving. |

### Phase 1.5

| id | state | summary |
|---|---|---|
| **D-022** | superseded | Reported the gateway's forwarding capability as natively supported. Wrong — see D-023. The name-resolution half stands: the gateway resolves the exposed devices by multicast name and **connects** to them, verified by connection rather than lookup. |
| **D-023** | accepted | **Correction.** The forwarding target is validated against loopback only, so it cannot reach another device at all. Fourth confident wrong answer from a partial signal in this project, and the first *optimistic* one — a false positive would have surfaced during cutover on a household gateway. New clause: do not conclude capability from a permissive-looking type or an example; submit what you intend to use and see whether the system takes it. |
| **D-024** | applied | **Both wide routes retired; three per-host routes serve from the tagged gateway.** The simple answer won: the premise that addresses move had never been checked, and the automation platform showed two integrations pinned to addresses and hostnames working for months. Records that I inverted the importance — the finding was the wide routes, not the naming mechanism. |

### Phase 2

| id | state | summary |
|---|---|---|
| **D-025** | applied | **Deny-by-default is live.** Seven grants, one port each, no wildcard. The tests rejected the policy **twice** — once by accident on an invalid test principal, once deliberately on a grant that would have widened access silently. The second is the case the design cares about most: nobody's connection breaks, nothing looks wrong, and only the assertion notices. |
| **D-026** | closed | The formatting drift warned about in D-021 was measured rather than worked around: one rule, inline comment spacing inside arrays. The template now matches, so rendered output is **byte-identical** to what the tailnet stores and a future drift check can be a plain comparison. |
| **D-027** | applied | A structural lint needing no credential, guarding the one rule stated absolutely — no `*` in a grant. Negative-tested before being trusted. Explicitly *not* a substitute for the tailnet's own tests, which still only run at apply time until Q-003's credential exists. |

## The starting state, stated plainly

Phase 2 is judged against this, so it belongs in one place:

- 7 nodes, **0 tagged**. No machine identity exists yet.
- Key expiry enabled on all 7.
- No access rule has ever been written. The policy file is stock.
- Allow-all grant `*:*:*`, plus Tailscale SSH check-mode to `autogroup:self` as
  root — one user owns every node, so that is the entire tailnet.
- A live, approved `/24` route extends all of the above to every device on the
  home LAN, including devices that cannot run a client and cannot refuse a
  connection.

The starting state is not "no policy". It is an implicit policy of full access,
routed through someone's desktop. That is the strongest available argument for
the deny-by-default work.

---

## Primer for the next session

**Before starting a phase:** `gh pr list --state open`. If the previous phase is
still in review, merge it or branch from its branch — not from `main`. This was
got wrong twice; the handoff's "one phase per PR" rule exists for exactly this.


**Read first:** this file, then `docs/02-decisions.md` (D-003 and D-005 are the
live ones), then `local/questions-for-review.md` for anything answered since.

**Do not start Phase 1 until** the phone check above is done and Q-001 is
answered. Phase 1 tags machine identities; Q-001 decides where the gateway role
lives, and tagging is the step that assigns it.

**In order:**

1. **The phone check.** One minute. It gates everything after it.
2. ~~Re-run the actuator mDNS check from the gateway node.~~ **Closed — D-012.**
   It resolved itself: releasing the actuator from its previous controller made
   the hub raise a zeroconf-sourced pairing flow for it, which is the check,
   from the right vantage point, answered by the system. No shell on the gateway
   was ever needed.
3. **Then Phase 1** — re-authenticate every non-human node with a tagged auth
   key, and record in the inventory which nodes now have key expiry disabled by
   default as a result.

**Carry into Phase 2 (D-010):** the first policy commit gains a pair of
assertions that were not previously possible — the granted actuator accepted and
the identical control host denied, same port, same source, same instant. Those
belong alongside the household-access assertion, because they are what makes the
actuator tier a demonstration rather than a claim.

**Carry into Phase 2:** `docs/runbooks/blast-radius.md` must be executed *around*
the first policy apply, not after it. The before-reading only exists while the
tailnet is still allow-all, and it is not recoverable later — reverting a
production tailnet to allow-all to take a reading is never the trade. Read that
runbook before scheduling the apply, not while doing it.

`scripts/fleet-up.sh` / `fleet-down.sh` are needed for that runbook and do not
exist yet. They cannot be written usefully until the policy file declares
`tagOwners`, since an ephemeral node needs a tagged auth key — so they belong at
the start of Phase 2, not earlier. Teardown must be reliable: every node
consumes a tagged resource and the plan caps them.

**Ordering that changed on review (D-008):** the route is not the lever, the
policy is. Do Phase 2 with the route untouched, then migrate the gateway with
both nodes overlapping, then withdraw the route. Withdrawing it first would
remove household access before a replacement works, and would reduce real
exposure later, not sooner.

**Before every commit:**

```bash
LEAK_DENYLIST="$(cat local/leak-denylist.txt)" ./scripts/leak-sweep.sh
```

**Where things live:** every real value is in `local/`, which is gitignored.
`local/sanitisation-map.md` maps real names onto the role names used in
committed docs — you need it to read `docs/00-handoff.md` against the actual
tailnet.

## Method notes worth keeping

Each of these nearly produced a wrong answer in Phase 0:

- **`timeout(1)` does not exist on macOS.** Several probe commands silently did
  not run. Background-and-kill instead.
- **`dns-sd` buffers when its output is not a tty.** A capture that comes back
  with no listing *and no header line* is a buffering artifact, not a negative
  result. Force a pty before believing an empty browse.
- **Verify a captured file by digest, not by reading it.** The baseline was
  confirmed by comparing a SHA-256 computed in the source page against the
  committed file.
- **A premise from a document is not a measurement.** The handoff's claim about
  how the account authenticates was wrong, and building a safety check on it
  produced a confident wrong finding plus a fix for a problem that did not
  exist. The account page was one click away in an already-open console. When a
  document supplies a fact about a system you can query, query it.
- **Probe rather than assume.** The broker's location, the actuator's transport
  and every Matter node's network type were all established by measurement.
- **Verify a negative against a positive control.** This one cost a wrong
  finding. The service-discovery CLI buffers off a tty: a browse that finds
  nothing never flushes, producing a file identical to one from a browse that
  never ran. Checking for the header line is necessary but not sufficient, since
  both failure modes produce a headerless empty file. Either prove the tool
  works by making it find something known to exist in the same invocation style,
  or bypass it and speak the protocol directly. D-007 is what happens without
  this rule.
