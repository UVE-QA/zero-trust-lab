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
  region  = var.region
  profile = var.profile

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
