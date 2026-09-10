# zero-trust-lab

A Zero Trust reference implementation built on real hardware, not a simulation.
It models a distributed field-operations topology — a telemetry collector,
sensors that cannot run an agent, a gateway per site, operator devices of
varying trust — on a home tailnet where every one of those roles already exists
physically.

The deliverable is a repository from which the whole access model can be rebuilt
from scratch, with tests that block unsafe policy from ever being applied.

**Start here:** [`STATUS.md`](STATUS.md) — what is done, what is open, what is
next. Then [`docs/00-handoff.md`](docs/00-handoff.md) for the design and its
constraints, and [`docs/02-decisions.md`](docs/02-decisions.md) for why things
are the way they are.

## Layout

| Path | What |
|---|---|
| `docs/00-handoff.md` | The specification. Sanitised; the original never leaves `local/`. |
| `docs/01-inventory.md` | Roles and counts. No names, no addresses. |
| `docs/02-decisions.md` | ADR-style, append-only. Reasoning, not just outcomes. |
| `policy/policy.baseline.hujson` | Pre-lab snapshot. **Never edited.** The rollback target. |
| `policy/README.md` | Tag taxonomy, and what the baseline actually contains. |
| `scripts/leak-sweep.sh` | The disclosure boundary. Run it before every commit. |
| `local/` | **Gitignored.** Every real value lives here and is never committed. |

## The disclosure rule

This repo is private now and intended to become public. Git history is
permanent, so there is no sanitising later — the boundary is enforced from the
first commit instead of promised.

Nothing containing a real hostname, address, account id or device model may be
committed, in any file, including docs. `scripts/leak-sweep.sh` enforces it and
`.github/workflows/leak-scan.yml` runs it on every PR alongside a secret
scanner. Site-specific strings reach CI through the `LEAK_DENYLIST` repository
secret, so the denylist itself never enters the repo.

Run it before you commit:

```bash
LEAK_DENYLIST="$(cat local/leak-denylist.txt)" ./scripts/leak-sweep.sh
```

CI catching a leak on a pushed commit is already too late.

## Constraints that shape everything

- **No identity provider.** Passkey account, so no SCIM and no group sync. The
  policy is built on tags and autogroups, which is the right unit anyway.
- **Personal (free) plan.** Phases 0–2 run on it indefinitely. Posture (Phase 3)
  and just-in-time access (Phase 4) are gated behind a trial or a paid seat.
- **The tailnet is in production for a household.** People who did not volunteer
  for this depend on it daily. Nothing they rely on gets reconfigured.
- **The home network is flat.** No IoT VLAN, and none is being built. The lab
  therefore demonstrates control of *remote* access, not full segmentation —
  stated plainly rather than hidden.
