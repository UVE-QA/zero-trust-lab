# Runbook — blast radius

**Purpose.** Put a number on what a node registered with a leaked credential can
actually reach, before and after the first deny-by-default policy.

**Status:** not yet executed. Scheduled for the Phase 2 apply window.
Design rationale in D-009; the exposure it is confirming is D-008.

---

## Why this is measured with a throwaway node

The claim under test is that *any node an auth key could register* reaches the
whole home LAN. A node registered exactly that way is the claim itself rather
than an approximation, so the measurement is done from a disposable ephemeral
node — not by loosening a node that is already trusted.

An ephemeral node also removes itself when it stops. There is no "remember to
turn it back off" step, and therefore no exposure that outlives the measurement.

The node runs on the off-premises host so that it has no local network path to
the home LAN. Anything it reaches, it reached across the tailnet.

---

## The sequencing constraint — read before starting

**The before-reading exists only while the tailnet is still allow-all.** Both
readings must happen in one window around the policy apply.

> **Never revert a production tailnet to allow-all in order to take a reading.**
> If the before-reading is missed, record that it was missed and proceed with
> the after-reading alone. Re-exposing a household network to recover a number
> is not a trade this project makes.

---

## Procedure

**1. Pre-flight**

- Confirm the rollback target is committed and matches what the tailnet is
  serving. Verify by digest, not by eye.
- Confirm the break-glass path: the admin console is reachable and can be
  authenticated from a phone that is off the tailnet.
- Note the current tagged-resource count against the plan's cap.

**2. Bring up the measuring node**

- One ephemeral node, tagged as a sensor, on the off-premises host.
- Route acceptance **on** — without it the node installs no route and the
  measurement returns nothing, which would look like a pass.
- Confirm it actually holds the route before measuring. A silent absence of a
  route is indistinguishable from a silent absence of access, and that confusion
  has already produced one retracted finding in this project (D-007).

**3. Before-reading**

- Enumerate what the node can reach across the route: which hosts answer, on
  which ports.
- Record the result verbatim into the private overlay, and the counts and
  classes only into this file.
- Expect it to reach everything. That is the point.

**4. Apply the policy**

- Merge the Phase 2 policy. The `tests` section must pass first — a failing
  assertion causes the tailnet to reject the file.

**5. After-reading**

- Repeat step 3 without changing anything else about the node.
- The delta between the readings is the deliverable.

**6. Tear down**

- Destroy the node. Confirm the tagged-resource count returns to its pre-flight
  value.
- Teardown is not housekeeping. An accumulating fleet hits the plan's cap and
  blocks unrelated work.

---

## Recording the result

| | Before | After |
|---|---|---|
| Hosts reachable across the route | | |
| Ports reachable | | |
| Site gateway admin interface reachable | | |
| Automation UI reachable | | |

The last two rows carry most of the meaning: the first should change and the
second must not. A household path that breaks is a policy bug, and it should
have been caught by an `accept` assertion before the apply rather than by this
table.

## Observed results

_Not yet run._
