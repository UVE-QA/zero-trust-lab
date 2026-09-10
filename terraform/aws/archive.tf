# ---------------------------------------------------------------------------
# Camera archive: S3 with a lifecycle into Glacier.
#
# Independent of which machine uploads, so it is built before the collector
# has dedicated hardware. Nothing here refers to a device.
# ---------------------------------------------------------------------------

resource "aws_s3_bucket" "archive" {
  # The account id makes the name globally unique and is resolved at apply
  # time, so the literal never enters the repository.
  bucket = "${var.name_prefix}-archive-${var.account_id}"
}

resource "aws_s3_bucket_public_access_block" "archive" {
  bucket                  = aws_s3_bucket.archive.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "archive" {
  bucket = aws_s3_bucket.archive.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "archive" {
  bucket = aws_s3_bucket.archive.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "archive" {
  bucket = aws_s3_bucket.archive.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Refuse plaintext transport at the bucket, not merely by convention.
data "aws_iam_policy_document" "archive_tls_only" {
  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.archive.arn,
      "${aws_s3_bucket.archive.arn}/*",
    ]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "archive" {
  bucket = aws_s3_bucket.archive.id
  policy = data.aws_iam_policy_document.archive_tls_only.json
}

resource "aws_s3_bucket_lifecycle_configuration" "archive" {
  bucket = aws_s3_bucket.archive.id

  # Terraform can otherwise race the versioning resource on a fresh apply.
  depends_on = [aws_s3_bucket_versioning.archive]

  rule {
    id     = "archive-to-glacier"
    status = "Enabled"

    filter {}

    transition {
      days          = var.archive_days_to_glacier
      storage_class = "GLACIER_IR"
    }

    transition {
      days          = var.archive_days_to_deep_archive
      storage_class = "DEEP_ARCHIVE"
    }

    # Expiry is off by default. Footage that deletes itself on a schedule
    # nobody chose is a worse failure than paying for storage.
    dynamic "expiration" {
      for_each = var.archive_expire_days > 0 ? [1] : []
      content {
        days = var.archive_expire_days
      }
    }

    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "GLACIER_IR"
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

output "archive_bucket" {
  description = "Archive bucket name. Contains the account id, so treat it as a real value."
  value       = aws_s3_bucket.archive.id
  sensitive   = true
}
