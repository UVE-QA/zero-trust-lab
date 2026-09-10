# Status

**Phase 0 — Capture and inventory. In progress, three items blocked.**
Last updated 2026-09-09.

Phase 1 has not been started and must not be until the items below clear.

---

## Done

| | |
|---|---|
| Disclosure boundary landed before any real value was recorded | `scripts/leak-sweep.sh`, `.github/workflows/leak-scan.yml`, `.gitignore` |
| `.gitignore` covers `local/`, `*.tfstate*`, `*.pem`, `*.key`, `.env` | verified, all five |
| Sanitised handoff committed; original stays private | `docs/00-handoff.md` |
| Node inventory captured | `local/inventory.yaml` (gitignored); public view in `docs/01-inventory.md` |
| MQTT broker located | on the node that will carry `tag:gateway-home` — D-004 |
| Every node has an assigned intended role | `docs/01-inventory.md` |

The sweep is not decorative: it caught a real hostname left in the placeholder
example file while that commit was being drafted. See D-002.

## Blocked — needs the owner

| # | Item | Blocked on |
|---|---|---|
| 1 | **Export the baseline policy file** to `policy/policy.baseline.hujson` | Admin console sign-in. The account uses passkeys, so this cannot be done unattended, and there is no API credential on the operator host. **This is the rollback target and gates every later phase.** |
| 2 | **Actuator qualification, checks 1 and 2** | The device is not in the automation hub at all — still paired to the other ecosystem. Both checks are hub-UI checks. Unpairing is a change to a household system. |
| 3 | **Admin console reachable from a phone off-tailnet** | Needs a phone on cellular. Cannot be tested from the operator host. This is the break-glass path; confirm it before any policy change. |
| 4 | `LEAK_DENYLIST` repository secret not set | Needs a decision — see below. Until it is set, CI runs the pattern sweep but skips the site-specific term sweep, and says so in its log. |

## Findings recorded this phase

| id | severity | summary |
|---|---|---|
| **D-003** | high | An approved `/24` route into the home LAN is already live, served by a user-owned personal desktop. With no access rules defined the default is allow-all, so every tailnet node already reaches every LAN device. The gateway role is not unassigned as the handoff assumes — Phase 1.5 is a migration, not a build. Not touched. |
| **D-004** | info | The MQTT broker was located rather than assumed. It sits on the intended gateway node, plaintext on all interfaces, anonymous refused, no TLS. Settles the grant direction. The LAN plaintext exposure is a documented residual risk, deliberately not fixed. |
| **D-005** | medium | The chosen actuator publishes no mDNS name, so Option B does not cover it and the Phase 1.5 fallback applies. Also rules out every existing Matter actuator as a substitute — all are Thread, verified per node. |

## Open question for the owner

`scripts/leak-sweep.sh` sweeps for site-specific strings — node names, the
tailnet name — supplied through the `LEAK_DENYLIST` repository secret. The
denylist is drafted at `local/leak-denylist.txt` and has **not** been uploaded.

Uploading it means those real names are transmitted to GitHub and held as an
encrypted repository secret. That is not a commit and never enters history, but
it is still the real names leaving this machine, so it is the owner's call. The
alternatives are to run the sweep only locally before each push, or to accept
that CI enforces the pattern rules alone. The pattern sweep — addresses, domain,
account id, MAC, credential formats — works either way and needs no secret.

## Next session, in order

1. Clear blocked items 1 and 3 above. Do item 1 first: nothing else in Phase 0
   or later should proceed without a committed rollback target.
2. Re-run the mDNS browse for the actuator **from the gateway node**, not from
   the operator laptop. The Phase 0 result was taken from the wrong vantage
   point; same L2 segment, so it should agree, but the check as written says
   from the gateway.
3. Decide D-003: the existing `/24` route is the single largest gap in the
   current state, and retiring it can remove remote access the household uses
   daily. It needs an explicit decision and a rollback note before it is
   touched.
4. Only then start Phase 1.

## Method notes worth keeping

- `timeout(1)` does not exist on macOS. Several probe commands in this session
  silently did not run because of it. Background-and-kill instead.
- `dns-sd` buffers when its output is not a tty. A capture that comes back with
  no service listing **and no header line** is a buffering artifact, not a
  negative result. Force a pty before believing an empty browse.
