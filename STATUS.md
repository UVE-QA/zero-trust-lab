# Status

**Phase 0 — Capture and inventory. Complete except for two items that need the
owner.** Last updated 2026-09-09.

Phase 1 has not been started.

Open work: **3 questions** in `local/questions-for-review.md` (Q-001 … Q-003).
None of them blocks the rest of Phase 0. Their substance is mirrored below and
in `docs/02-decisions.md`, so this repo is readable without that private file.

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

### 2. Actuator checks 1 and 2 — blocked, and the premise is in question (Q-002)

The device is not in the automation hub at all, so both hub-UI checks are
unrunnable. Decided: **confirm the firmware variant before unpairing anything.**
Two observations sit against the handoff's assumption that this is the HomeKit
firmware variant — it publishes no HomeKit advertisement at all, and it serves
an HTTP endpoint more characteristic of the standard firmware. If it is
standard firmware, the local-LAN integration the handoff rules out may work
directly and nothing needs unpairing.

D-005 is explicit that this is an inference, not an identification. Confirm
against the physical unit before acting on it.

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
| **D-005** | medium | The actuator publishes no mDNS name — Option B's own verification step failing. Every existing Matter actuator ruled out as a substitute: all Thread, verified per node. |
| **D-006** | info | The baseline is the stock default: allow-all, plus root SSH to `autogroup:self`, which on a single-user tailnet is every machine. |

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

**Read first:** this file, then `docs/02-decisions.md` (D-003 and D-005 are the
live ones), then `local/questions-for-review.md` for anything answered since.

**Do not start Phase 1 until** the phone check above is done and Q-001 is
answered. Phase 1 tags machine identities; Q-001 decides where the gateway role
lives, and tagging is the step that assigns it.

**In order:**

1. **The phone check.** One minute. It gates everything after it.
2. **Re-run the actuator mDNS browse from the gateway node**, not from the
   operator laptop. The Phase 0 result was taken from the wrong vantage point —
   same L2 segment so it should agree, but the check as written says from the
   gateway, and D-005 turns on it.
3. **Read the answers** to Q-001 … Q-003 and fold them into
   `docs/02-decisions.md` as amendments, not edits. The decisions file is
   append-only.
4. **Q-001 first among them.** The live `/24` is the largest gap in the current
   state and retiring it can remove access the household uses daily.
5. **Then Phase 1** — re-authenticate every non-human node with a tagged auth
   key, and record in the inventory which nodes now have key expiry disabled by
   default as a result.

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
- **Probe rather than assume.** The broker's location, the actuator's transport
  and every Matter node's network type were all established by measurement.
  Two of the three contradicted the specification.
