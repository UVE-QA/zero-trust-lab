# The apply path: CI can change this account, but only after a person says so.
#
# Until the repository was published, this could not exist. GitHub's required
# reviewers are an Environment protection rule, and on a private repository
# that rule needs an Enterprise plan (D-033), so the split was "CI plans, a
# person applies from a terminal". Public repositories get the rule for free,
# which makes the approval a property of the pipeline rather than of somebody
# remembering to run a command (D-055).
#
# The role below is assumable ONLY by a job running in the `aws-apply`
# environment, which requires a named reviewer to approve each run. The plan
# role keeps its own environment and stays read-only.
#
# WHAT KEEPS THIS FROM BEING A BACK DOOR
#
#   - It is scoped to this stack's own resources: the roles this prefix owns,
#     the archive bucket, and this stack's state prefix. It is not admin.
#   - It CANNOT MODIFY ITSELF. The deny below is the important line: without
#     it, one approved run could rewrite this policy and the gate would be
#     over. Changes to the apply role are therefore applied by a person, from
#     a terminal, exactly as everything was before.
#   - It cannot read or write the other project living in this account.

locals {
  github_apply_subject = "repo:${var.github_owner}@${var.github_owner_id}/${var.github_repo}@${var.github_repo_id}:environment:${var.github_apply_environment}"
  apply_role_arn       = "arn:aws:iam::${var.account_id}:role/${var.name_prefix}-github-apply"
}

data "aws_iam_policy_document" "github_apply_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.github_oidc_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # The whole control: this exact repository, in the reviewed environment.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = [local.github_apply_subject]
    }
  }
}

data "aws_iam_policy_document" "github_apply_permissions" {
  # --- Terraform state -------------------------------------------------
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

  # --- The archive bucket this stack owns -------------------------------
  statement {
    sid    = "ManageTheArchiveBucket"
    effect = "Allow"
    actions = [
      "s3:CreateBucket",
      "s3:DeleteBucket",
      "s3:Get*",
      "s3:List*",
      "s3:Put*",
      "s3:Delete*",
    ]
    resources = [
      aws_s3_bucket.archive.arn,
      "${aws_s3_bucket.archive.arn}/*",
    ]
  }

  # --- The roles this stack owns, by name prefix ------------------------
  statement {
    sid    = "ManageThisStacksRoles"
    effect = "Allow"
    actions = [
      "iam:GetRole",
      "iam:CreateRole",
      "iam:DeleteRole",
      "iam:TagRole",
      "iam:UntagRole",
      "iam:ListRoleTags",
      "iam:UpdateAssumeRolePolicy",
      "iam:GetRolePolicy",
      "iam:PutRolePolicy",
      "iam:DeleteRolePolicy",
      "iam:ListRolePolicies",
      "iam:ListAttachedRolePolicies",
    ]
    resources = ["arn:aws:iam::${var.account_id}:role/${var.name_prefix}-*"]
  }

  # THE LINE THAT KEEPS THE GATE SHUT. The statement above matches every role
  # this prefix owns, and this role is one of them. Without this deny, a single
  # approved run could widen this policy to anything, and every run after it
  # would be unreviewed in effect. Changes to the apply role itself are applied
  # by a person.
  statement {
    sid    = "ButNeverItself"
    effect = "Deny"
    actions = [
      "iam:CreateRole",
      "iam:DeleteRole",
      "iam:UpdateAssumeRolePolicy",
      "iam:PutRolePolicy",
      "iam:DeleteRolePolicy",
      "iam:AttachRolePolicy",
      "iam:DetachRolePolicy",
      "iam:TagRole",
      "iam:UntagRole",
    ]
    resources = [local.apply_role_arn]
  }

  # --- Reads the plan needs, same as the plan role ----------------------
  statement {
    sid       = "ReadTheOidcProvider"
    effect    = "Allow"
    actions   = ["iam:GetOpenIDConnectProvider"]
    resources = [local.github_oidc_arn]
  }

  statement {
    sid       = "ListProvidersCannotBeScoped"
    effect    = "Allow"
    actions   = ["iam:ListOpenIDConnectProviders"]
    resources = ["*"]
  }

  statement {
    sid    = "CountIamPrincipalsForTheEvidencePage"
    effect = "Allow"
    actions = [
      "iam:ListUsers",
      "iam:GetAccountSummary",
    ]
    resources = ["*"]
  }

  # Read-only for now. Phase 5 creates a trust anchor and a profile here, and
  # that addition is itself an apply a person will make -- see the deny above
  # for why that ordering is the point rather than an inconvenience.
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

resource "aws_iam_role" "github_apply" {
  name                 = "${var.name_prefix}-github-apply"
  description          = "Assumed by the gated apply workflow via OIDC, only from a reviewed environment. No access key exists for it."
  assume_role_policy   = data.aws_iam_policy_document.github_apply_assume.json
  max_session_duration = 3600
}

resource "aws_iam_role_policy" "github_apply" {
  name   = "${var.name_prefix}-github-apply"
  role   = aws_iam_role.github_apply.id
  policy = data.aws_iam_policy_document.github_apply_permissions.json
}

output "github_apply_role_arn" {
  description = "Set as AWS_APPLY_ROLE_ARN in the repository. Useless without a token whose subject matches the reviewed environment."
  value       = aws_iam_role.github_apply.arn
}

output "github_apply_trusted_subject" {
  description = "The only OIDC subject that can assume the apply role."
  value       = local.github_apply_subject
}
