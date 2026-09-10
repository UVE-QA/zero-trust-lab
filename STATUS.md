# Status

**Work in progress, built in the open.** Last updated 2026-09-10.

**Live evidence:** every check below, read from CI when the page was built —
[uve-qa.github.io/zero-trust-lab](https://uve-qa.github.io/zero-trust-lab/) (D-044).

Phases 0, 1, 1.5, 2 and 5 are done; Phase 3 is largely done. Phase 4 needs a
paid plan and is deliberately deferred. Phase 6 — the drills — is next. Every
claim below links to the decision that records it, and most to the CI run or
pull request that proves it.

> **The tailnet is deny-by-default.** Seven grants, each naming a source role,
> a destination and one port. No `*` in the grants section. Anything not written
> down is refused.

> **The policy is tested by the tailnet itself, on every change.** 36
> assertions — 30 of them are things that must be *refused* — run against the
> live tailnet on each pull request, with no stored credential. A daily job
> checks that the policy in force is byte-identical to `main`.

---

## Where each phase stands

| Phase | What | State | Evidence |
|---|---|---|---|
| 0 | Capture, inventory, disclosure boundary | done | D-002, D-006, PR #1 |
| 1 | Machine identities as tags | done | D-018 – D-021, PR #2 |
| 1.5 | Segmentation: two `/24` routes into the home network → three `/32` | done | D-024, PR #3 |
| 2 | Deny-by-default, with tests that refused two unsafe drafts | done | D-025, PR #4 |
| 3 | Device posture — shown to be enforced on the free plan | mostly done | D-040, PR #6 |
| 4 | Just-in-time access | deferred: paid plan | — |
| 5 | Cloud access with no static credentials (GitHub OIDC → AWS) | done | D-028, D-038, PR #5 |
| 6 | Drills: blast radius, lost device, offboarding, lost comms | next | — |

Since Phase 5, and not a phase of its own: the tailnet's tests now run in CI by
workload identity federation, read-only, with no secret stored anywhere —
proven from both sides, including a deliberately broken pull request the
pipeline refused (D-041, PR #7, PR #8).

## Open, stated plainly

- **Production SSH is still reachable from the internet** (D-042). The tailnet
  path is fixed and verified; the public port stays open until the one client
  that still uses it is proven on the tailnet path, so that closing it cannot
  lock anyone out. In progress.
- **Exposed LAN devices are addressed by IP on a network without DHCP
  reservations** (D-047). A camera that turned out to be the wrong one was
  withdrawn; the two remaining sockets were verified by their own identifiers.
  A daily identity check on each exposed address is next.
- **The policy's `ssh` rule for production is dead configuration** since
  Tailscale SSH was turned off on that host (D-042). It reads like a control and
  is not one. To be removed.
- **The blast-radius "before" reading was never taken.** It could only be taken
  while the tailnet was still allow-all, and that window closed with Phase 2.
  The exposure change is therefore stated from configuration — two `/24`
  routes became three `/32` — not from a before/after reachability
  measurement. The "after" reading is still possible and is in the plan.
- **Phase 4 waits on a paid plan** — one time-boxed month on a single seat.

## Plan

**Next few days**

1. ~~Open the repository~~ — done, with the gaps a public repository opens
   closed in the same step: commit messages swept as well as files, the sweep
   fails rather than skipping when its denylist is unavailable, identifiers
   masked in logs, `main` protected for everyone (D-043).
2. Finish D-042: prove the remaining client on the tailnet path, then close
   production SSH to the internet and remove a stale firewall rule, then remove
   the dead `ssh` rule from the policy.

**Next one to two weeks**

3. ~~A live evidence page~~ — done (D-044); custom domain pending one DNS
   record. Next on it: cloud IAM users counted, and routes into the home
   network wider than `/32` counted, each by a read-only job of its own.
4. ~~`validate` on a schedule~~ — done.

**Next, after an outside review (D-046) — substance before more machinery**

- ~~The collector as a real host, with one telemetry stream~~ — done. The
  hub pushes one reading every five minutes to a collector outside the house,
  which has no path in (D-049). Open: the pet-fountain automation has not yet
  been seen firing since the restart that change needed.
- The lost-comms drill on that stream: the first number on the evidence page
  that comes from watching the system rather than counting the repository.
- The "after" half of the exposure reading, from a disposable node.

**Weeks two to three — Phase 6**

5. Blast radius, "after" reading, from a disposable node.
6. Lost device: time to revoke, and what stops working.
7. Offboarding: what has to be revoked, and what never existed to revoke.
8. Lost comms: what keeps working in the household when the control plane
   cannot be reached.

**After that**

9. Posture on the production SSH grant, replacing the re-authentication step
   that was lost with Tailscale SSH.
10. Optional: the collector role via certificate-based cloud access.
11. Phase 4, if and when the paid month is taken.

---

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

- **A control too strict for its real clients routes them around itself.**
  Tailscale SSH in `check` mode hangs any non-interactive client on a browser
  prompt, so every such client used the public path the policy could not see
  (D-042).
- **Test the scanner, not just the code.** Twice in one audit a scan came back
  clean because it had silently read almost nothing: once a zsh loop that did
  not split its input, once a clone that ran the committed script instead of the
  edited one. A clean result counts only after the same scanner has caught a
  planted value.

## Running the checks locally

```bash
LEAK_DENYLIST="$(cat local/leak-denylist.txt)" ./scripts/leak-sweep.sh
./scripts/policy-lint.py
./scripts/tf-lint.py
```

Every real value lives in `local/`, which is gitignored. The live-tailnet tests
need the CI identity and run only in GitHub Actions.
