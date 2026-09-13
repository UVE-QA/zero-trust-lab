# Runbook — the collector's certificate

**Purpose.** The collector uploads to the archive bucket with **no AWS key
anywhere on the machine**. It presents an X.509 certificate to IAM Roles
Anywhere and receives credentials that expire in an hour. This is how the
certificate is made, renewed and taken away.

**Status:** CA created 2026-09-13. The trust anchor is created by Terraform as
soon as the CA is supplied (D-064).

---

## Where the private keys are, and why there

| key | lives on | why |
|---|---|---|
| the CA key | the operator's laptop, in `local/ca/`, never committed, never copied to a server | the machine that *uses* a certificate must not be able to *mint* one. That separation is the whole point of the pattern. |
| the collector's key | the collector host only, generated on the laptop and copied once | it is the credential. It is worth exactly one role, write-only into one bucket, for one hour at a time. |

**Stated plainly:** this CA is a file on a laptop with disk encryption, not an
HSM and not an air-gapped machine. A managed private CA is $400 a month, which
buys hardware custody and an audit trail this lab does not need and will not
pay for. What the lab does get is the property that matters most here — the
credential on the exposed machine cannot create more credentials.

## Making the CA and the first certificate

```bash
umask 077
openssl ecparam -name prime256v1 -genkey -noout -out ca.key
openssl req -x509 -new -key ca.key -sha256 -days 1825 -out ca.crt \
  -subj "/CN=zero-trust-lab collector CA/O=zero-trust-lab" \
  -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
  -addext "keyUsage=critical,keyCertSign,cRLSign"
```

`pathlen:0` means this CA can sign leaf certificates and no further CAs. The
leaf, 90 days, client authentication only:

```bash
openssl ecparam -name prime256v1 -genkey -noout -out collector.key
openssl req -new -key collector.key -out collector.csr -subj "/CN=collector/O=zero-trust-lab"
printf "basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=clientAuth\n" > leaf.ext
openssl x509 -req -in collector.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -days 90 -sha256 -extfile leaf.ext -out collector.crt
openssl verify -CAfile ca.crt collector.crt
```

The CA certificate — public, and no household value in it — goes to the
`aws-plan` and `aws-apply` environments as `COLLECTOR_CA_CERTIFICATE_PEM`, and
Terraform turns it into the trust anchor. The CA *key* goes nowhere.

## Renewing, in 90 days

Issue a new leaf with the same CA, copy it to the collector, restart the
uploader. Nothing changes in AWS: the trust anchor trusts the CA, not the
certificate. Renewal is a local command and a file copy, which is the point of
signing rather than registering.

## Taking it away

Three levers, in increasing size:

1. **Disable the profile** in Roles Anywhere — every certificate stops working
   at once, and nothing is destroyed. This is the incident lever.
2. **Publish a CRL** naming the certificate. Roles Anywhere supports one; this
   lab has not set one up, which is a real gap and is written down rather than
   implied: today a leaked leaf is answered by disabling the profile or
   replacing the CA, not by revoking one certificate.
3. **Replace the CA**: new anchor, new leaf, old anchor deleted. About ten
   minutes, and it invalidates every certificate the old CA signed.

The credential the collector holds expires an hour after it is issued, so any
of these takes effect within an hour even for a session already in flight.

## What it can do once it has credentials

`s3:PutObject` into the archive bucket and `s3:ListBucket` on it. Not
`GetObject`, not `DeleteObject`, nothing outside that bucket, and no path to
the state bucket. A machine in a flat that can only add is a machine whose
compromise costs storage, not history.
