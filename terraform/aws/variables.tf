# The account id is a VARIABLE, never a literal. It is a real-world value and
# the disclosure rules keep it out of the repository -- see docs/00-handoff.md.
# Supply it through terraform.tfvars, which is gitignored.
variable "account_id" {
  description = "AWS account id the lab deploys into. Never committed."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{12}$", var.account_id))
    error_message = "account_id must be a 12-digit AWS account id."
  }
}

variable "profile" {
  description = <<-EOT
    Named AWS profile. Required on the operator host, where there is no default
    profile by design. Empty in GitHub Actions, where credentials come from the
    assumed role and no profile exists.
  EOT
  type    = string
  default = ""
}

variable "region" {
  description = "Region for the lab's resources."
  type        = string
  default     = "us-west-2"
}

variable "name_prefix" {
  description = "Prefix for resource names. Kept generic so nothing identifies a household."
  type        = string
  default     = "ztlab"
}

# ---------------------------------------------------------------------------
# GitHub OIDC
# ---------------------------------------------------------------------------

variable "github_owner" {
  description = "GitHub account or org that owns the repository."
  type        = string
}

variable "github_repo" {
  description = "Repository name, without the owner."
  type        = string
}

variable "github_environment" {
  description = <<-EOT
    The GitHub Environment allowed to assume the deploy role, as it appears in
    the OIDC token `sub` claim: repo:OWNER/REPO:environment:NAME.

    Pinned to an environment rather than a branch, matching the pattern already
    in use in this account.

    On a PUBLIC repository an environment can also require a reviewer, making
    the apply need a human approval separate from permission to merge. This
    repository is private, where that rule needs Enterprise -- so the pin
    constrains WHICH workflow context may assume the role, and gates on nobody.
    See D-033; do not mistake the pin for an approval.

    Deliberately one environment and no wildcard. An unconstrained `sub`
    accepts a token from any GitHub Actions run anywhere on GitHub.
  EOT
  type        = string
  default     = "aws-apply"

  validation {
    condition     = !can(regex("[*]", var.github_environment))
    error_message = "github_environment must not contain a wildcard. A wildcard here is the misconfiguration this variable exists to prevent."
  }
}

# ---------------------------------------------------------------------------
# Archive retention
# ---------------------------------------------------------------------------

variable "archive_days_to_glacier" {
  description = "Days before archived objects move to Glacier Instant Retrieval."
  type        = number
  default     = 30
}

variable "archive_days_to_deep_archive" {
  description = "Days before archived objects move to Glacier Deep Archive."
  type        = number
  default     = 180
}

variable "archive_expire_days" {
  description = "Days before archived objects are deleted. Zero disables expiry."
  type        = number
  default     = 0
}

# ---------------------------------------------------------------------------
# IAM Roles Anywhere
# ---------------------------------------------------------------------------

variable "collector_ca_certificate_pem" {
  description = <<-EOT
    PEM of the certificate authority that signs collector certificates. This is
    the trust anchor: any certificate it signs can obtain credentials, so it is
    supplied at apply time and never committed.

    Empty by default so the rest of the stack can be applied before a CA
    exists -- the Roles Anywhere resources are created only when it is set.
  EOT
  type        = string
  default     = ""
  sensitive   = true
}

variable "github_oidc_provider_exists" {
  description = <<-EOT
    Whether the GitHub OIDC provider already exists in this account.

    An account may hold only one provider per URL, and it is commonly created
    by whatever used OIDC first. Creating a second fails; adopting the existing
    one is correct. Set true if `aws iam list-open-id-connect-providers` shows
    token.actions.githubusercontent.com.
  EOT
  type        = bool
  default     = false
}

# ---------------------------------------------------------------------------
# Remote state (an existing, shared bucket -- see backend.tf)
# ---------------------------------------------------------------------------

variable "tfstate_bucket" {
  description = "Existing Terraform state bucket to join. Embeds the account id, so it is supplied at apply time and never committed."
  type        = string
}

variable "tfstate_prefix" {
  description = "This stack's prefix inside the shared state bucket. The deploy role is scoped to it, so other projects' state stays out of reach."
  type        = string
  default     = "zero-trust-lab"
}
