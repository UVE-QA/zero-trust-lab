# ---------------------------------------------------------------------------
# IAM Roles Anywhere: the on-prem collector uploads without a stored key.
#
# The device presents an X.509 certificate and receives temporary credentials.
# This is the on-prem answer to a permanent access key sitting on a machine in
# a living room, and it maps directly onto field sites uploading to cloud
# storage.
#
# IT BINDS TO A CERTIFICATE, NOT TO HARDWARE. Nothing here names a machine, so
# replacing the collector means issuing a certificate and revoking the old one
# -- no change in this directory. That move is docs/runbooks/rehome-collector.md.
#
# Created only when a CA is supplied, so the rest of the stack can be applied
# before one exists.
# ---------------------------------------------------------------------------

locals {
  roles_anywhere_enabled = var.collector_ca_certificate_pem != ""
}

resource "aws_rolesanywhere_trust_anchor" "collector" {
  count   = local.roles_anywhere_enabled ? 1 : 0
  name    = "${var.name_prefix}-collector-ca"
  enabled = true

  source {
    source_type = "CERTIFICATE_BUNDLE"
    source_data {
      x509_certificate_data = var.collector_ca_certificate_pem
    }
  }
}

data "aws_iam_policy_document" "collector_assume" {
  statement {
    effect  = "Allow"
    actions = [
      "sts:AssumeRole",
      "sts:TagSession",
      "sts:SetSourceIdentity",
    ]

    principals {
      type        = "Service"
      identifiers = ["rolesanywhere.amazonaws.com"]
    }

    # Without this, any trust anchor in the account could assume the role.
    # Naming the anchor is what makes the certificate the credential.
    dynamic "condition" {
      for_each = local.roles_anywhere_enabled ? [1] : []
      content {
        test     = "ArnEquals"
        variable = "aws:SourceArn"
        values   = [aws_rolesanywhere_trust_anchor.collector[0].arn]
      }
    }
  }
}

resource "aws_iam_role" "collector" {
  name               = "${var.name_prefix}-collector"
  description        = "Assumed by the collector via a certificate. No access key exists for it."
  assume_role_policy = data.aws_iam_policy_document.collector_assume.json
}

# Write-only into the archive. The collector uploads; it does not read back,
# does not delete, and cannot reach the state bucket.
data "aws_iam_policy_document" "collector_permissions" {
  statement {
    sid       = "PutArchiveObjects"
    effect    = "Allow"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.archive.arn}/*"]
  }

  statement {
    sid       = "ListOwnPrefix"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.archive.arn]
  }
}

resource "aws_iam_role_policy" "collector" {
  name   = "${var.name_prefix}-collector"
  role   = aws_iam_role.collector.id
  policy = data.aws_iam_policy_document.collector_permissions.json
}

resource "aws_rolesanywhere_profile" "collector" {
  count     = local.roles_anywhere_enabled ? 1 : 0
  name      = "${var.name_prefix}-collector"
  role_arns = [aws_iam_role.collector.arn]
  enabled   = true

  # An hour, not a day. The point of the pattern is that a credential taken
  # off the device stops being useful quickly.
  duration_seconds = 3600
}

output "collector_role_arn" {
  value       = aws_iam_role.collector.arn
  description = "Role the collector assumes by certificate."
}

output "collector_trust_anchor_arn" {
  value       = local.roles_anywhere_enabled ? aws_rolesanywhere_trust_anchor.collector[0].arn : "not created -- no CA supplied"
  description = "Trust anchor. Empty until a CA is provided."
}

output "roles_anywhere_enabled" {
  value       = local.roles_anywhere_enabled
  description = "False means the certificate half is not yet built; the role exists but nothing can assume it."
}
