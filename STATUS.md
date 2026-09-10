# Status

**Phase 0 — Capture and inventory. Nearly complete; two items open.**
Last updated 2026-09-09.

Phase 1 has not been started.

---

## Done

| | |
|---|---|
| Disclosure boundary landed **before** any real value was recorded | `scripts/leak-sweep.sh`, `.github/workflows/leak-scan.yml` |
| `.gitignore` covers `local/`, `*.tfstate*`, `*.pem`, `*.key`, `.env` | verified, all five |
| Leak scan runs and passes on the first PR | both jobs green on PR #1 |
| `LEAK_DENYLIST` repository secret set | site-specific term sweep now enforced in CI |
| Sanitised handoff committed; the original never leaves `local/` | `docs/00-handoff.md` |
| **Baseline policy file exported and committed** | `policy/policy.baseline.hujson`, verified byte-identical by digest — D-006 |
| Node inventory captured; every node has an intended role | `local/inventory.yaml`; public view in `docs/01-inventory.md` |
| MQTT broker located | on the intended gateway node — D-004 |
| Actuator: check 3 done, checks 1 and 2 blocked | D-005 |

The sweep is not decorative. It caught a real hostname left in the placeholder
example file while that commit was being drafted (D-002).

## Open

### 1. Admin console from a phone off-tailnet — not verified

**What was actually checked:** from the operator laptop, the console resolves to
a public address and routes over the physical interface, not the tailnet, and
returns HTTP 200. That establishes the console is not a tailnet-dependent
service.

**What that does not establish** — and the acceptance check asks for it — is
that the console is reachable *and can be authenticated* from a phone on
cellular with the tailnet down. Passkey authentication on the phone is the part
that cannot be inferred from a routing table.

**Do this before any policy change.** It is the break-glass path: open the
console on a phone with WiFi off and confirm you can sign in and reach the
policy editor. One minute, and it is the thing that makes a bad policy
recoverable.

### 2. Actuator checks 1 and 2 — blocked, and the premise is in question

Decided: **confirm the firmware variant before unpairing anything.** The
handoff's plan (unpair from the phone-vendor ecosystem, adopt via HomeKit
Controller) rests on the unit being the HomeKit firmware variant. Two
observations sit against that — the device publishes no HomeKit advertisement at
all, and it serves an HTTP endpoint more characteristic of the standard
firmware. If it is standard firmware, the local-LAN integration the handoff
rules out may work directly and no unpairing is needed.

Confirm against the physical unit before acting. See D-005 — the inference there
is explicitly *not* an identification.

## Findings

| id | severity | summary |
|---|---|---|
| **D-003** | high | An approved `/24` route into the home LAN is already live, served by a user-owned personal desktop. The gateway role is not unassigned as the handoff assumes; Phase 1.5 is a migration, not a build. Not touched. |
| **D-004** | info | MQTT broker located, not assumed. On the intended gateway node, plaintext on all interfaces, anonymous refused, no TLS. Settles the grant direction. LAN exposure documented as residual risk, deliberately not fixed. |
| **D-005** | medium | The actuator publishes no mDNS name — Option B's own verification step failing. Every existing Matter actuator ruled out as a substitute: all Thread, verified per node. |
| **D-006** | info | The baseline is the stock default: allow-all plus root SSH to `autogroup:self`, which on a single-user tailnet is every machine. |

## The starting state, stated plainly

Worth having in one place, because Phase 2 is judged against it:

- 7 nodes, **0 tagged**. No machine identity exists yet.
- Key expiry enabled on all 7.
- No access rules have ever been written. The policy file is stock.
- Allow-all grant `*:*:*`, plus Tailscale SSH check-mode to `autogroup:self` as
  root — one user owns every node, so that is the whole tailnet.
- A live, approved `/24` route extends all of the above to every device on the
  home LAN, including devices that cannot run a client and cannot refuse a
  connection.

## Next session, in order

1. Close the two open items above. The phone check first — it is one minute and
   it gates everything that follows.
2. Re-run the actuator mDNS browse **from the gateway node**. The Phase 0 result
   was taken from the operator laptop; same L2 segment, so it should agree, but
   the check as written says from the gateway.
3. Decide D-003. The live `/24` is the largest gap in the current state, and
   retiring it can remove remote access the household uses daily — it needs an
   explicit decision and a rollback note before it is touched.
4. Only then start Phase 1.

## Method notes worth keeping

- `timeout(1)` does not exist on macOS. Several probes in this session silently
  did not run because of it. Background-and-kill instead.
- `dns-sd` buffers when its output is not a tty. A capture that comes back with
  no listing **and no header line** is a buffering artifact, not a negative
  result. Force a pty before believing an empty browse.
- Verify a captured file by digest, not by reading it. The baseline was
  confirmed by comparing a SHA-256 computed in the source page against the
  committed file.
