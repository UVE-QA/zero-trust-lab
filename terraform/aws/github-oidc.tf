# ---------------------------------------------------------------------------
# GitHub OIDC federation: this repository -> AWS, with no stored access key.
#
# THE THING TO GET RIGHT IS THE `sub` CONDITION.
#
# A trust policy that does not constrain `sub` will accept a token from ANY
# GitHub Actions run, in any repository, belonging to anyone. The provider is
# shared across all of GitHub; the audience alone proves only "this came from
# GitHub Actions", which is not a claim worth anything on its own.
#
# So: StringEquals on one exact subject, not StringLike, and no wildcard. The
# variable that supplies the ref rejects wildcards, and scripts/tf-lint.py
# fails the build if this condition is weakened.
# ---------------------------------------------------------------------------

data "aws_iam_openid_connect_provider" "github" {
  count = var.github_oidc_provider_exists ? 1 : 0
  url   = "https://token.actions.githubusercontent.com"
}

resource "aws_iam_openid_connect_provider" "github" {
  count = var.github_oidc_provider_exists ? 0 : 1

  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]

  # AWS verifies GitHub's certificate against its own trust store for this
  # well-known provider, so the thumbprint is vestigial. It is required by the
  # API, so a current value is supplied rather than a placeholder.
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

locals {
  github_oidc_arn = var.github_oidc_provider_exists ? data.aws_iam_openid_connect_provider.github[0].arn : aws_iam_openid_connect_provider.github[0].arn

  # repo:OWNER/REPO:environment:NAME -- one exact subject.
  #
  # Pinned to an environment, not a branch, so a required reviewer on that
  # environment gates the apply. Matches the pattern already established in
  # this account.
  # repo:OWNER@<owner-id>/REPO@<repo-id>:environment:NAME
  #
  # The ids are not decoration. A subject pinned to names alone can be
  # inherited by whoever claims the name after a repository is deleted; the id
  # form cannot. This exact string was read off a real token rather than
  # constructed from documentation -- an earlier version of this file assumed
  # the name-only form, matched a working role in the same account that uses
  # it, and failed to assume.
  github_subject = "repo:${var.github_owner}@${var.github_owner_id}/${var.github_repo}@${var.github_repo_id}:environment:${var.github_environment}"
}

data "aws_iam_policy_document" "github_deploy_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.github_oidc_arn]
    }

    # Proves the token was minted for AWS STS rather than replayed from
    # somewhere else that also trusts GitHub's provider.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # Proves WHICH workflow. This is the whole control.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = [local.github_subject]
    }
  }
}

resource "aws_iam_role" "github_deploy" {
  name                 = "${var.name_prefix}-github-deploy"
  description          = "Assumed by this repository's workflow via OIDC. No access key exists for it."
  assume_role_policy   = data.aws_iam_policy_document.github_deploy_assume.json
  max_session_duration = 3600
}

# What the workflow may actually do.
#
# CI PLANS. A HUMAN APPLIES. That split is deliberate, and it follows from
# there being no approval gate on this repository (D-033): a role that can
# create IAM roles unattended, with nobody required to look, is a worse trade
# than typing a command. When the repository is published and a required
# reviewer becomes available, this can be revisited.
#
# So the permissions below are read plus state. Terraform needs to READ every
# resource it manages in order to produce a plan -- which is more than it first
# appears, and is why the first attempt failed.
#
# Deliberately NOT the ReadOnlyAccess managed policy. That grants read across
# the entire account, and this account holds another project's state and
# secrets. "Read-only" is not the same as "harmless", and a lab about least
# privilege should not reach for an account-wide grant because scoping is
# tedious.
data "aws_iam_policy_document" "github_deploy_permissions" {
  # --- Terraform state: the only writes this role has -------------------
  statement {
    sid    = "TerraformStateForThisStackOnly"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = ["arn:aws:s3:::${var.tfstate_bucket}/${var.tfstate_prefix}/*"]
  }

  statement {
    sid       = "ListOnlyThisStacksPrefix"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::${var.tfstate_bucket}"]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["${var.tfstate_prefix}/*"]
    }
  }

  # --- Reading the stack, to plan it -----------------------------------
  statement {
    sid    = "ReadTheArchiveBucketItManages"
    effect = "Allow"
    actions = [
      "s3:Get*",
      "s3:List*",
    ]
    resources = [
      aws_s3_bucket.archive.arn,
      "${aws_s3_bucket.archive.arn}/*",
    ]
  }

  statement {
    sid    = "ReadTheRolesItManages"
    effect = "Allow"
    actions = [
      "iam:GetRole",
      "iam:GetRolePolicy",
      "iam:ListRolePolicies",
      "iam:ListAttachedRolePolicies",
      "iam:ListRoleTags",
    ]
    resources = [
      aws_iam_role.github_deploy.arn,
      aws_iam_role.collector.arn,
    ]
  }

  statement {
    sid       = "ReadTheOidcProvider"
    effect    = "Allow"
    actions   = ["iam:GetOpenIDConnectProvider"]
    resources = [local.github_oidc_arn]
  }

  # The only unscoped action here. Listing providers has no resource to scope
  # to -- IAM requires "*" for it -- and Terraform's data source calls it
  # before it can call Get. It reveals which providers exist, and nothing else.
  statement {
    sid       = "ListProvidersCannotBeScoped"
    effect    = "Allow"
    actions   = ["iam:ListOpenIDConnectProviders"]
    resources = ["*"]
  }

  statement {
    sid    = "ReadRolesAnywhereWhenItExists"
    effect = "Allow"
    actions = [
      "rolesanywhere:ListTrustAnchors",
      "rolesanywhere:GetTrustAnchor",
      "rolesanywhere:ListProfiles",
      "rolesanywhere:GetProfile",
      "rolesanywhere:ListTagsForResource",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "github_deploy" {
  name   = "${var.name_prefix}-github-deploy"
  role   = aws_iam_role.github_deploy.id
  policy = data.aws_iam_policy_document.github_deploy_permissions.json
}

output "github_deploy_role_arn" {
  description = "Set as the role-to-assume in the workflow. Not a secret -- an ARN is useless without a token whose subject matches."
  value       = aws_iam_role.github_deploy.arn
}

output "github_trusted_subject" {
  description = "The exact OIDC subject this role trusts. Worth reading back after apply."
  value       = local.github_subject
}
