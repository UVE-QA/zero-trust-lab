# Runbook — putting the evidence page behind its own CDN

**Purpose.** GitHub Pages keeps no record of a request, so nothing showed that
the evidence page had been opened at all. This moves the page's address onto a
CloudFront distribution that fetches the page from GitHub Pages and keeps
CloudFront's standard access log. Publishing does not change: GitHub still
builds and deploys the page, with no cloud credential (D-079).

**Status:** steps 1–3 applied 2026-10-04; step 4 is its own change.

Every step that writes is a person's. CI can read what this creates and
cannot change it. Machine: the operator's laptop. Directory: `terraform/aws`.
Profile: the workload account's SSO profile, named in `terraform.tfvars`.

> **Never apply this stack without the CA variable.** Without it the Roles
> Anywhere trust anchor and profile count to zero and the apply destroys them.
> Since D-078 either spelling below is the same value to Terraform.
>
> `-var="collector_ca_certificate_pem=$(cat ../../local/ca/ca.crt)"`

---

## 1. The zone, answering exactly as today

```bash
terraform apply -target=aws_route53_zone.site -target=aws_route53_record.site_pages -var="collector_ca_certificate_pem=$(cat ../../local/ca/ca.crt)"
```

Three resources: the zone and its A and AAAA records, which hold GitHub
Pages' published addresses with a one-minute TTL. Read the name servers:

```bash
terraform output site_name_servers
```

**Check before the delegation**, asking the new zone directly — it must
already answer with GitHub's addresses:

```bash
dig +short lab.uveapp.net A @"$(terraform output -json site_name_servers | python3 -c 'import json,sys; print(json.load(sys.stdin)[0])')"
```

## 2. The delegation — in the parent zone, by hand

The parent zone is in another account and is edited by its owner. In one
change batch: delete the `lab` CNAME to GitHub Pages, create `lab` NS with the
four values from step 1. A CNAME cannot sit beside an NS record of the same
name, so it is one batch, not two.

**Check:** the name is now answered by the new zone, and the answer is
unchanged.

```bash
dig +short NS lab.uveapp.net
```

```bash
dig +short A lab.uveapp.net
```

The page must still open at its address, served by GitHub as before.

## 3. The certificate and the distribution

```bash
terraform apply -var="collector_ca_certificate_pem=$(cat ../../local/ca/ca.crt)"
```

The plan should be seven to add and two to change. The two changes are the CI
roles' policies gaining the read statement for these resources; anything else
changing is a reason to stop. The certificate validates through the zone, so
this step waits until the delegation in step 2 is visible to ACM — minutes,
usually. The distribution then takes a few minutes more.

**Check:** the distribution reaches GitHub. While the repository still has its
custom domain, GitHub answers the distribution with a redirect to that domain,
and that redirect is the proof the origin is wired:

```bash
curl -sI "https://$(terraform output -raw site_distribution_domain)/" | grep -iE '^HTTP|^location'
```

Expected: `301` and `location: https://lab.uveapp.net/`.

## 4. The switch

A code change of its own, reviewed like any other: the GitHub Pages records
are replaced by aliases to the distribution.

- `aws_route53_record.site_pages` gives way to a `removed` block with
  `destroy = false`, so Terraform forgets those records without deleting them;
- a new `aws_route53_record.site`, A and AAAA, aliases the distribution with
  `allow_overwrite = true`, so it upserts over the values in place.

The name is never without an answer. Three commands, back to back, in this
order:

```bash
terraform apply -var="collector_ca_certificate_pem=$(cat ../../local/ca/ca.crt)"
```

```bash
gh api -X PUT repos/UVE-QA/zero-trust-lab/pages --input - <<< '{"cname":null}'
```

```bash
aws cloudfront create-invalidation --distribution-id "$(terraform output -raw site_distribution_id)" --paths '/*'
```

**Why this order.** The DNS change goes first because it is the one that can
fail: if the upsert is refused, nothing has changed and GitHub still serves
the page. Once it succeeds, the repository's custom domain must go at once —
with it set, GitHub answers the distribution with a redirect back to the
custom domain, which is now the distribution: a loop.

**Why the invalidation.** Step 3's check put that redirect in the
distribution's cache, and so does any request before the custom domain is
removed. GitHub sends the redirect without a `Cache-Control`, and the managed
caching policy then keeps it for up to a day. Measured on 2026-10-04: a second
request for `/` was a cache hit, age 44 seconds. Without the invalidation the
switch would serve a redirect loop from cache long after it was fixed.

For about a minute — the old records' TTL — some resolvers still send visitors
to GitHub directly, where the custom domain is already gone; they get GitHub's
404 until their resolver catches up.

**Check:**

```bash
curl -sI https://lab.uveapp.net/ | grep -iE '^HTTP|^via|^x-cache'
```

Expected: `200`, and `via` naming CloudFront. Then open the page with a query
string and confirm the address bar is plain after load and the live layer
still runs. The first log object appears under `lab/` in the logs bucket
within about an hour; CloudFront's standard logs are not immediate.

## Undo

Before step 2: `terraform destroy` with the same targets as step 1.

After step 4: put the custom domain back on the repository and the parent
zone's `lab` record back to a CNAME for GitHub Pages:

```bash
gh api -X PUT repos/UVE-QA/zero-trust-lab/pages -f cname=lab.uveapp.net
```

GitHub may take a while to re-issue its certificate for the name; until then
it serves the page over a certificate for its own domain.

## What stays true and what does not

- The page is still published by GitHub with no cloud credential, and still
  holds nothing.
- The page's GitHub address — the owner's `github.io` host with the repository
  as its path — keeps serving the page, and a request there is not logged.
  That is accepted, not overlooked: the logged address is the one that is
  linked.
- The logs bucket belongs to the sibling project (ADR-0104 there). If it is
  removed, CloudFront stops writing logs and keeps serving the page.
