# terraform/aws

The lab's AWS footprint. **No long-lived access key exists for any of it.**

| File | What |
|---|---|
| `github-oidc.tf` | Federation from this repository. The subject condition is the control — see below. |
| `roles-anywhere.tf` | The collector authenticates with a certificate, not a key. |
| `archive.tf` | Archive bucket with a lifecycle into Glacier. |
| `backend.tf` | Remote state — joins an existing shared bucket under a prefix. |
| `identity-center.tf` | Deliberately empty. The reason is in the file. |

## The one thing to get right

A GitHub OIDC trust policy that does not pin `sub` will accept a token from
**any** GitHub Actions run, in any repository, belonging to anyone. The provider
is shared across all of GitHub; the audience claim alone proves only that a
token came from Actions, which on its own is worth nothing.

So the policy uses `StringEquals` against one exact subject, the variable
supplying the ref rejects wildcards, and `scripts/tf-lint.py` fails the build if
either is weakened. Three layers because this failure **fails open** and looks
correct in review.

## Running it

There is no default profile on the operator host by design, so every command
carries one.

```bash
cp backend.hcl.example backend.hcl              # fill in; gitignored
cp terraform.tfvars.example terraform.tfvars    # fill in; gitignored
terraform init -backend-config=backend.hcl
terraform plan
```

`terraform.tfvars` carries the account id and `backend.hcl` the state bucket
name, which embeds it. Neither is committed.

The provider pins `allowed_account_ids`, so Terraform refuses to run if the
credentials in scope belong to a different account — the failure this project is
most exposed to, since the operator host carries credentials for several.

## What is not built, and why

**Identity Center.** It lives in the organisation's management account; this
stack deploys into a workload account and its credentials cannot administer the
organisation. Putting it here would produce a plan that cannot be applied by the
identity it is written for. See the file for the design intent.

**Roles Anywhere is conditional.** The trust anchor is created only when a
certificate authority is supplied. Until then the role exists and nothing can
assume it, which is the correct resting state rather than a half-built one.

## Rotation and revocation

- **The GitHub role** has no credential to rotate. Revoking access means
  changing the trusted subject or deleting the role.
- **The collector** is revoked by revoking its certificate, not by deleting a
  key. Replacing the machine is `docs/runbooks/rehome-collector.md` and touches
  nothing in this directory.
