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
  github_subject = "repo:${var.github_owner}/${var.github_repo}:environment:${var.github_environment}"
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

# What the workflow may actually do. Deliberately narrow: it manages the
# lab's own stack and nothing else in the account.
data "aws_iam_policy_document" "github_deploy_permissions" {
  # Scoped to this stack's prefix, not the whole shared bucket. Other
  # projects keep their state in the same bucket and this role has no
  # business reading it.
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

  statement {
    sid    = "ReadArchive"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
      "s3:GetBucketLocation",
    ]
    resources = [aws_s3_bucket.archive.arn]
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
