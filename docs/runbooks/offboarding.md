# Runbook — offboarding

**Purpose.** Remove a person's access to everything this lab governs, and know
how long it takes and what is left behind.

**Status:** rehearsed on paper against the live inventory on 2026-09-13, not
executed — there is one person, and removing his access would end the lab. The
inventory below was read from the systems themselves, not from memory. The one
revocation that *has* been measured is a machine's, in the join-and-revoke
drill: gone from the network in about 1.6 s.

---

## What exists to revoke

Read read-only on 2026-09-13:

| where | what | how it ends |
|---|---|---|
| tailnet | 4 user-owned devices, one person | remove the user in the console; every device of theirs goes with it |
| tailnet | 4 tagged machines (hub, production stand-in, collector, appliance) | they belong to the tailnet, not the person, and survive |
| tailnet | 1 trust credential, OIDC, read-only, no secret | revoke it in the console; nothing to rotate |
| GitHub | 1 collaborator, the owner | remove from the repository |
| GitHub | 5 secrets, 1 variable, 4 environments | secrets hold no personal credential — they hold an account id, a bucket name, two role ARNs and a private denylist |
| GitHub | 0 deploy keys, 0 webhooks | nothing to remove |
| cloud | 3 roles with this lab's prefix, all assumed by federation | they are assumed by a repository, not by a person |
| cloud | **0 IAM users, no root access keys** | nothing to remove, and now checked weekly rather than asserted (D-054) |
| production host | 2 authorised SSH keys: the operator's, and the provider's default | remove the operator's key; the provider's is the break-glass path |
| collector | 2 containers, 2 volumes, no credential in either | they hold telemetry, not identity |
| the house | the hub's own logins, the vendor clouds, the household's accounts | **not the lab's to revoke** — they belong to the household and its own records |

## The order to do it in

1. **The tailnet user.** One removal takes the person and all four of their
   devices out of every grant at once, because every grant names a role or an
   identity rather than an address. Measured for a machine: under two seconds.
2. **The GitHub collaborator.** This ends the ability to merge, to dispatch the
   apply, and to approve it — the three things that can change the account or
   the policy.
3. **The trust credential**, if the leaver had console access: revoke it and CI
   loses its read-only view of the network until a new one is made.
4. **The operator's key on the production host**, which is the only long-lived
   secret in the lab that belongs to a person.
5. **Nothing in the cloud account**, because no identity there belongs to a
   person. That is the point of the OIDC work (D-028, D-038): there is no user
   to disable, no key to rotate, and no ex-employee's credential to find later.

## What is left behind, honestly

- **The cloud account itself.** Whoever can sign in to it has a shell on the
  production host through the provider's console (D-042). Offboarding is
  therefore an account-level task first and a lab task second.
- **The house.** The hub, the cameras and the vendor clouds have their own
  accounts, and the lab has no authority over them. A person who was in the
  household stays in the household's records until the household removes them.
- **Copies.** Anything already downloaded — a policy render, a telemetry file,
  a screenshot of this page — is gone from the lab's reach the moment it is
  copied. No revocation reaches it.

## What would make this shorter

An identity provider: one account to disable instead of a tailnet user and a
GitHub collaborator. That is the first item in the growth path on the evidence
page, priced there, and this runbook is the reason it is first.

## To rehearse it for real

Add a second identity — a throwaway account with a device of its own — grant it
nothing beyond the member baseline, and remove it while measuring. That is the
honest version of this drill and it needs a second person's account, or a
second account of the owner's, which is a decision rather than a task.
