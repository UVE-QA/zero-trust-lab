# Runbook — rehome the collector

**Purpose.** Move the collector role to different hardware without touching
cloud IAM.

**Status:** not yet executed. The collector runs as a container on the cloud
dev host (D-048, D-049); dedicated hardware is not deployed.

---

## Why this runbook is the interesting artifact

Replacing a field collector without touching cloud IAM is a more useful thing to
have demonstrated than having installed the first one correctly. Anyone can
provision a machine. The question a reviewer actually has is what happens when
that machine is replaced, lost, or stolen — and whether the answer involves
editing infrastructure code under time pressure.

Here it does not, and the reason is structural: **the trust anchor binds to a
certificate authority, not to hardware.** Nothing in `terraform/aws/` names a
machine. A new collector is a new certificate; a retired collector is a revoked
one.

---

## Procedure

**1. Issue a certificate for the new machine**

From the same CA that signs the trust anchor. The private key is generated on
the new machine and never leaves it — a key that travels has already failed the
property this pattern exists to provide.

**2. Confirm the new machine can obtain credentials**

Exchange the certificate for temporary credentials and confirm they carry the
collector role. Verify by identity, not by a successful upload: an upload
proves reachability, and the question here is which principal is being used.

**3. Move the workload**

Point the archiving job at the new machine. Both machines are able to upload at
this point, which is deliberate — the replacement is proven before the original
is retired, the same overlap used when the routing role moved.

**4. Revoke the old certificate**

Add it to the CA's revocation list. **This is the step that ends the old
machine's access**, and it is the only step that must not be skipped: deleting
the archiving job leaves a machine that can still authenticate.

**5. Verify the revocation**

Attempt to obtain credentials with the old certificate and confirm it fails.
A revocation nobody has watched fail is a revocation nobody should rely on —
the same rule applied to every other check in this project.

**6. Record the change**

Update the inventory. No Terraform runs; if a change here required one, the
design would be wrong.

---

## What must NOT happen

- **No access key is created for the new machine.** If a step seems to need
  one, the step is wrong.
- **No Terraform apply.** The stack is hardware-independent by construction.
  An apply here means something has been bound to a machine that should not be.
- **The old certificate is not merely deleted from the old host.** A file
  removed from a machine you no longer control is not a revocation.

## Observed results

_Not yet run._
