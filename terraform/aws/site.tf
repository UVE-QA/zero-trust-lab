# ---------------------------------------------------------------------------
# The evidence page, served through a CDN of its own (D-079).
#
# The page is still built and published by GitHub, with no cloud credential at
# all; that does not change. What changes is the path a visitor's request takes:
# lab.uveapp.net now resolves to CloudFront, which fetches the page from GitHub
# Pages and keeps CloudFront's standard access log of the request.
#
# The log is the reason. GitHub Pages keeps none, so nothing recorded that the
# page was opened at all. The log lines go to the bucket the sibling project's
# dashboard already logs into (aws-devops-sdet-demo, ADR-0104): same account,
# private, SSE-S3, every object expired after 90 days, read by one script on
# the operator's host that prints counts and never an address. One bucket
# rather than two means one retention rule and one place that holds viewers'
# addresses, not two. The page itself sends nothing anywhere.
#
# DNS. lab.uveapp.net becomes a zone of its own in this account, delegated by
# one NS record in the parent zone, which lives in another account and is
# edited by hand -- the same arrangement as the sibling project's subdomain.
# Until the switch, the zone answers with GitHub Pages' published addresses, so
# the delegation itself changes nothing a visitor sees.
#
# Applied by a person, not by CI: the apply role is not given CloudFront, ACM
# or Route 53 writes. Both CI roles can read these resources, so the weekly
# plan still covers them.
# ---------------------------------------------------------------------------

# CloudFront accepts certificates from us-east-1 and nowhere else.
provider "aws" {
  alias               = "us_east_1"
  region              = "us-east-1"
  profile             = var.profile != "" ? var.profile : null
  allowed_account_ids = [var.account_id]

  default_tags {
    tags = {
      Project   = "zero-trust-lab"
      ManagedBy = "terraform"
    }
  }
}

locals {
  site_domain      = "lab.uveapp.net"
  site_origin      = "${lower(var.github_owner)}.github.io"
  site_origin_path = "/${var.github_repo}"

  # Owned by the sibling project's public-site level, not by this stack: this
  # stack names it and never manages it.
  site_logs_bucket = "aws-devops-sdet-demo-site-logs-${var.account_id}"

  # GitHub Pages' published apex addresses, served until the CDN takes over.
  github_pages_ipv4 = ["185.199.108.153", "185.199.109.153", "185.199.110.153", "185.199.111.153"]
  github_pages_ipv6 = ["2606:50c0:8000::153", "2606:50c0:8001::153", "2606:50c0:8002::153", "2606:50c0:8003::153"]

  # AWS managed cache policy "CachingOptimized". It honours the origin's own
  # Cache-Control, and GitHub Pages sends max-age=600 -- the same ten minutes
  # GitHub's own CDN keeps the page today. Query strings are not part of the
  # cache key and are not sent to GitHub; they are still in the access log,
  # which records the viewer's request, not the origin's.
  caching_optimized = "658327ea-f89d-4fab-a63d-7e88639e58f6"
}

resource "aws_route53_zone" "site" {
  name    = local.site_domain
  comment = "Evidence page; delegated from the parent zone by one NS record (D-079)"
}

# GitHub Pages' addresses, with a one-minute TTL, while the switch is pending.
# Deliberately independent of the distribution: the zone and these records come
# first, the parent zone delegates to them, and only then can the certificate
# validate and the distribution be built. A record that referred to the
# distribution would wait for all of that before it existed, and the
# delegation would point at an empty zone in the meantime.
#
# The switch replaces these with aliases to the distribution in one change
# (docs/runbooks/evidence-page-cdn.md): the alias records upsert over these
# values, and these are dropped from the state with `removed`, not deleted, so
# the name is never without an answer.
resource "aws_route53_record" "site_pages" {
  for_each = {
    A    = local.github_pages_ipv4
    AAAA = local.github_pages_ipv6
  }

  zone_id = aws_route53_zone.site.zone_id
  name    = local.site_domain
  type    = each.key
  ttl     = 60
  records = each.value
}

resource "aws_acm_certificate" "site" {
  provider          = aws.us_east_1
  domain_name       = local.site_domain
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "site_cert_validation" {
  for_each = {
    for o in aws_acm_certificate.site.domain_validation_options : o.domain_name => o
  }

  zone_id         = aws_route53_zone.site.zone_id
  name            = each.value.resource_record_name
  type            = each.value.resource_record_type
  records         = [each.value.resource_record_value]
  ttl             = 300
  allow_overwrite = true
}

resource "aws_acm_certificate_validation" "site" {
  provider                = aws.us_east_1
  certificate_arn         = aws_acm_certificate.site.arn
  validation_record_fqdns = [for r in aws_route53_record.site_cert_validation : r.fqdn]
}

resource "aws_cloudfront_distribution" "site" {
  enabled         = true
  is_ipv6_enabled = true
  http_version    = "http2and3"
  comment         = "zero-trust-lab evidence page (D-079)"
  aliases         = [local.site_domain]

  # North America and Europe only. A portfolio page, not a product.
  price_class = "PriceClass_100"

  # GitHub Pages serves a project site at <owner>.github.io/<repo>/ once the
  # repository has no custom domain of its own. With one set, that address
  # redirects to the custom domain -- which would now be this distribution, a
  # loop -- so the switch removes the custom domain from the repository in the
  # same minute (docs/runbooks/evidence-page-cdn.md).
  origin {
    domain_name = local.site_origin
    origin_id   = "github-pages"
    origin_path = local.site_origin_path

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    target_origin_id       = "github-pages"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true
    cache_policy_id        = local.caching_optimized
  }

  # One line per request into the shared logs bucket, under a prefix of its
  # own. No cookies: the page sets none, and a log should not start keeping them.
  logging_config {
    bucket          = "${local.site_logs_bucket}.s3.amazonaws.com"
    prefix          = "lab/"
    include_cookies = false
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate_validation.site.certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }
}

# What both CI roles may read of the above, so the weekly plan covers it. Each
# action is scoped to the one resource it reads; nothing here can change it.
locals {
  site_read_actions = [
    "cloudfront:GetDistribution",
    "cloudfront:GetDistributionConfig",
    "cloudfront:ListTagsForResource",
    "acm:DescribeCertificate",
    "acm:ListTagsForCertificate",
    "route53:GetHostedZone",
    "route53:ListResourceRecordSets",
    "route53:ListTagsForResource",
  ]
  site_read_resources = [
    aws_cloudfront_distribution.site.arn,
    aws_acm_certificate.site.arn,
    aws_route53_zone.site.arn,
  ]
}

output "site_name_servers" {
  description = "The four NS values the parent zone's `lab` record must name (D-079)."
  value       = aws_route53_zone.site.name_servers
}

output "site_distribution_domain" {
  description = "The distribution's own hostname, for checking it before the switch."
  value       = aws_cloudfront_distribution.site.domain_name
}
