terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }
}

provider "aws" {
  region = var.region

  # Empty in GitHub Actions, where credentials come from the assumed role and
  # there is no profile at all. Required on the operator host, where there is
  # no default profile by design and picking the wrong account is the mistake
  # this project is most exposed to.
  profile = var.profile != "" ? var.profile : null

  # Guard against pointing at the wrong account. Terraform refuses to run if
  # the credentials in scope do not belong to the account named in tfvars --
  # which is the failure this project is most exposed to, since the operator
  # host carries credentials for several accounts.
  allowed_account_ids = [var.account_id]

  default_tags {
    tags = {
      Project   = "zero-trust-lab"
      ManagedBy = "terraform"
    }
  }
}
