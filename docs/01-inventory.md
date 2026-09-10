# Inventory — public view

Roles and counts only. Node names, addresses, the tailnet domain and device
models live in `local/inventory.yaml`, which is gitignored. If a reader of this
file could identify a device or reach an address, it does not belong here.

**Captured:** 2026-09-09, Phase 0. Source: `tailscale status --json` from the
operator laptop, plus mDNS browsing and read-only TCP probes from the same host.
Nothing was reconfigured.

## Tailnet

| | |
|---|---|
| Nodes | 7 |
| Tagged (machine identity) | **0** |
| User-owned | 7 |
| Distinct users | 1 (passkey account, no IdP) |
| Key expiry enabled | 7 of 7 |
| Earliest key expiry | 2027-03 |
| Access rules defined | none — default allow-all |
| Advertised subnet routes | 1, approved, `/24` (see finding F-01) |

## Nodes by intended role

| Role | Count | Intended tag | Ownership after Phase 1 |
|---|---|---|---|
| Operator workstation | 1 | none | user-owned — must stay so; it is the physical console |
| Operator mobile | 2 | none | user-owned — posture subjects, and the break-glass path |
| Production stand-in | 1 | `tag:prod` | tagged |
| Automation hub / gateway | 1 | `tag:gateway-home` | tagged |
| Shared desktop (runs the NVR) | 1 | none | user-owned **permanently** — another person's daily machine |
| Media appliance | 1 | `tag:kiosk` | tagged |

Roles with no host yet: `tag:collector` (waiting on dedicated hardware; modelled
by a container in the interim), `tag:sensor` and `tag:drone` (ephemeral
containers, created and destroyed by the fleet scripts).

## Non-tailnet devices

Reachable only through the gateway; none of them can ever run the client.
Observed on the LAN by service type, not enumerated by device:

| Service type | Meaning |
|---|---|
| Matter over IP | 5 instances — a Matter fabric is live |
| Thread border router + radio link | a Thread mesh exists |
| HomeKit accessory protocol | advertised as a type, but **no instance responded** to a browse |
| BLE proxies | 2 |
| Vendor hub protocol | present |

Counts of cameras and their placement are deliberately not recorded here or in
`local/`, per the disclosure rules in `docs/00-handoff.md` §2.7.

## State of the Phase 0 acceptance check

| Item | State |
|---|---|
| `.gitignore`, `local/`, leak scan landed before any real value | done |
| Baseline policy file exported and committed | **not done** — see `STATUS.md` |
| Inventory complete, every node has an intended role | done |
| Actuator qualified | **partial** — two of three checks blocked |
| Admin console reachable off-tailnet | **not done** |
