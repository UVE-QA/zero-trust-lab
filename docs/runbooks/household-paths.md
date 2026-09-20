# Runbook — the paths the household actually uses

**Purpose.** This lab narrows a network that people live in. A grant can be
correct, tested, and still take away something somebody was using, because the
thing they were using was never written down. This is that list, and the check
to run before narrowing anything (D-073).

---

## Before narrowing a grant or un-approving a route

Ask, in this order:

1. **Who reaches this, and by what name?** A device's tailnet identity and its
   LAN address are different destinations. A grant to one does not carry the
   other.
2. **Does anything reach it from outside the house?** Phones and tablets leave.
   What worked on the sofa may have been working through a subnet route that is
   about to disappear.
3. **Would the failure be visible?** An application that falls back to a LAN
   address fails with a spinner, not an error. Nothing appears in a log,
   because nothing arrives.

## The list

| what | reaches | by | notes |
|---|---|---|---|
| companion app on the phone | the automation hub's UI | the hub's **tailnet** address, as the app's external URL; the LAN address as its internal URL, bound to the home Wi-Fi | fixed 2026-09-20 after two weeks broken (D-073) |
| companion app on the tablet | same | same | the tablet leaves the house too (D-068) |
| operator laptop | hub UI and shell, production SSH, the granted socket | tailnet identities, asserted in the policy tests | |
| the house itself | the socket it switches on an event | the hub's own LAN, not the tailnet | unaffected by any policy here |

Anything not in this table has not been thought about. Add a row before
narrowing something, not after somebody complains.

## Why the automation hub has no external address of its own

The hub publishes neither an external URL nor a cloud service, so a client that
has not been told an address has nowhere to go from outside. Setting one on the
hub would make the apps self-configuring — and it is a change to the household's
own system, so it goes through the owner rather than through this lab.

## The check that would have caught it

None existed. The policy tests assert the operator reaches the hub over the
tailnet, which stayed true throughout. A test for this class of break has to
name the path as the household uses it, which means writing the table above
first — and that is the actual fix.
