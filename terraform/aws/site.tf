# ---------------------------------------------------------------------------
# The evidence page, served through a CDN of its own (D-079).
#
# The page is still built and published by GitHub, with no cloud credential at
# all; that does not change. What changed is the path a visitor's request takes:
# lab.uveapp.net resolves to CloudFront, which fetches the page from GitHub
# Pages.
#
# DNS. lab.uveapp.net is a zone of its own in this account, delegated by one
# NS record in the parent zone, which lives in another account and is edited by
# hand -- the same arrangement as the sibling project's subdomain. The zone
# first answered with GitHub Pages' published addresses, so the delegation
# itself changed nothing a visitor saw; it now aliases the distribution.
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

  # AWS managed cache policy "CachingOptimized". It honours the origin's own
  # Cache-Control, and GitHub Pages sends max-age=600 -- the same ten minutes
  # GitHub's own CDN kept the page.
  caching_optimized = "658327ea-f89d-4fab-a63d-7e88639e58f6"
}

resource "aws_route53_zone" "site" {
  name    = local.site_domain
  comment = "Evidence page; delegated from the parent zone by one NS record (D-079)"
}

# The name now answers with the distribution (the switch, D-079).
#
# Until the switch the zone held GitHub Pages' own addresses, so the
# delegation from the parent zone changed nothing a visitor saw. Those records
# are dropped from the state here without being deleted; the aliases below
# upsert over them in place, so the name is never without an answer.
removed {
  from = aws_route53_record.site_pages

  lifecycle {
    destroy = false
  }
}

resource "aws_route53_record" "site" {
  for_each = toset(["A", "AAAA"])

  zone_id         = aws_route53_zone.site.zone_id
  name            = local.site_domain
  type            = each.key
  allow_overwrite = true

  alias {
    name                   = aws_cloudfront_distribution.site.domain_name
    zone_id                = aws_cloudfront_distribution.site.hosted_zone_id
    evaluate_target_health = false
  }
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

output "site_distribution_id" {
  description = "For the cache invalidation that ends the switch (docs/runbooks/evidence-page-cdn.md)."
  value       = aws_cloudfront_distribution.site.id
}

output "site_distribution_domain" {
  description = "The distribution's own hostname, for checking it before the switch."
  value       = aws_cloudfront_distribution.site.domain_name
}
