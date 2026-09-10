# Policy

## Files

| File | Role |
|---|---|
| `policy.baseline.hujson` | The pre-lab snapshot. **Never edited.** The rollback target. |
| `policy.hujson` | The lab's policy. Written from zero in Phase 2; does not exist yet. |

## The baseline

Captured 2026-09-09 from the admin console, before anything was changed.
Verified byte-identical to what the tailnet was serving: SHA-256
`f732d21e94ee9c09ca3c8a90d627ff26c0bf888de14e1e0364054777716e21cf`, 2255 bytes,
compared against a digest computed in the console page itself rather than
eyeballed.

**It is the stock default, unmodified.** Nobody has ever written a rule on this
tailnet. Two things in it matter:

```jsonc
{"src": ["*"], "dst": ["*"], "ip": ["*"]}
```

Every node may reach every node on every port. Combined with the live `/24`
subnet route recorded in D-003, that extends to every device on the home LAN,
including ones with no Tailscale client and no way to refuse a connection.

```jsonc
"ssh": [{ "action": "check", "src": ["autogroup:member"],
          "dst": ["autogroup:self"], "users": ["autogroup:nonroot", "root"] }]
```

Tailscale SSH is enabled in check mode to any member's own devices, as root.
Every node on this tailnet is owned by the same single user, so `autogroup:self`
is *all of them*. Worth stating plainly before Phase 1 tags anything: this is
the path an operator laptop currently has into the production stand-in, and
Phase 4's just-in-time work is meant to replace exactly it.

The file is verbatim, comments included. It carries Tailscale's own example
address in a commented-out `tests` block, which lives in the CGNAT range and so
matches the disclosure sweep's tailnet-address rule. The sweep carries a
narrowly scoped exception for that one literal rather than the rollback target
being edited to please a scanner — see D-006.

## Tag taxonomy

Tag by role in the system, never by hardware model or owner. Defined in
`docs/00-handoff.md` §5; not yet applied to anything — as of Phase 0 the tailnet
has zero tagged nodes.

| Tag | Role |
|---|---|
| `tag:collector` | telemetry / NVR sink |
| `tag:prod` | production server stand-in |
| `tag:gateway-home` | subnet router for the IoT segment |
| `tag:sensor` | simulated push-only field sensors |
| `tag:drone` | simulated mobile units |
| `tag:appliance` | network-attached appliance with no role over the tailnet — appears in no `src` |

Rules:

- **Do not name a tag after a word the household already uses for something
  else.** `tag:appliance` was originally `tag:kiosk`, until it turned out that
  "kiosk" already means a display mode running on two personal handhelds here.
  A policy that reads as though it governs one device while actually governing
  another is worse than an ugly name — see D-019.
- **A node is either user-owned or tagged, never both.** Tagging strips the
  owning user's identity and replaces it with the tag's, so a tagged node cannot
  be a posture subject and a personal daily driver must never carry an
  infrastructure tag.
- Operator devices stay untagged so posture can be evaluated on them.
- Keep the taxonomy small. A node with many tags inherits the union of their
  rules and the policy stops being readable.

## Rollback

Restoring `policy.baseline.hujson` returns the tailnet to allow-all. That is a
working state for the household and an open one for everything else — it is the
break-glass, not a resting place. The console is reached over the public
internet, not over the tailnet, so a bad policy cannot lock anyone out of the
place where it gets undone.
