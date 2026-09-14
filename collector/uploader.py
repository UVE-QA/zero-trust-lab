#!/usr/bin/env python3
"""Ship readings to the archive bucket with no AWS key on the machine.

The collector holds an X.509 certificate and its private key. It exchanges
them, over TLS, for credentials that expire in an hour (IAM Roles Anywhere),
and uses those to PUT one object. There is no access key here, in the
environment, or in any file this program reads -- which is the whole point:
a key on a machine in a flat is its own successor, a certificate is not
(D-064).

    CERT=/certs/collector.crt KEY=/certs/collector.key \
    TRUST_ANCHOR_ARN=... PROFILE_ARN=... ROLE_ARN=... BUCKET=... \
    ./uploader.py

Everything it needs comes from the environment, because every one of those
values names something real and this file is public.

Two things are deliberately hand-rolled rather than imported:

  - The CreateSession request is signed with the certificate's own key
    (AWS4-X509-ECDSA-SHA256). AWS ships a helper binary for this; fetching and
    running a binary on the machine that holds the credential is a bigger
    trust decision than writing sixty lines, and the sixty lines can be read.
  - The S3 request is signed with ordinary SigV4 using the temporary
    credentials. hmac and hashlib are in the standard library.

The private key never leaves the process's arguments to openssl, which signs
the string-to-sign and nothing else.
"""
import base64
import datetime as dt
import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import urllib.request

CERT = os.environ.get("CERT", "/certs/collector.crt")
KEY = os.environ.get("KEY", "/certs/collector.key")
REGION = os.environ.get("REGION", "us-west-2")
BUCKET = os.environ.get("BUCKET", "")
PREFIX = os.environ.get("PREFIX", "readings")
DATA = os.environ.get("DATA", "/data/readings.jsonl")
STATE = os.environ.get("STATE", "/state/uploaded.offset")
TRUST_ANCHOR_ARN = os.environ.get("TRUST_ANCHOR_ARN", "")
PROFILE_ARN = os.environ.get("PROFILE_ARN", "")
ROLE_ARN = os.environ.get("ROLE_ARN", "")
MAX_BATCH = 4 * 1024 * 1024


def sh(*args, stdin=None):
    p = subprocess.run(args, input=stdin, capture_output=True)
    if p.returncode:
        sys.exit("%s failed: %s" % (args[0], p.stderr.decode()[:200]))
    return p.stdout


def cert_der_and_serial():
    """The certificate as DER, and its serial as the decimal AWS expects."""
    der = sh("openssl", "x509", "-in", CERT, "-outform", "DER")
    serial_hex = sh("openssl", "x509", "-in", CERT, "-noout", "-serial").decode().split("=")[1].strip()
    return base64.b64encode(der).decode(), str(int(serial_hex, 16))


def sign_with_certificate(string_to_sign):
    """ECDSA-SHA256 over the string to sign, DER, hex -- openssl does the maths."""
    return sh("openssl", "dgst", "-sha256", "-sign", KEY, stdin=string_to_sign.encode()).hex()


def sha256_hex(b):
    return hashlib.sha256(b if isinstance(b, bytes) else b.encode()).hexdigest()


def create_session():
    """Certificate in, one hour of credentials out."""
    host = "rolesanywhere.%s.amazonaws.com" % REGION
    now = dt.datetime.now(dt.timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    scope_date = now.strftime("%Y%m%d")
    b64_cert, serial = cert_der_and_serial()
    body = json.dumps({
        "durationSeconds": 3600,
        "profileArn": PROFILE_ARN,
        "roleArn": ROLE_ARN,
        "trustAnchorArn": TRUST_ANCHOR_ARN,
    }).encode()

    signed_headers = "content-type;host;x-amz-date;x-amz-x509"
    canonical = "\n".join([
        "POST", "/sessions", "",
        "content-type:application/json",
        "host:" + host,
        "x-amz-date:" + amz_date,
        "x-amz-x509:" + b64_cert,
        "", signed_headers, sha256_hex(body),
    ])
    scope = "%s/%s/rolesanywhere/aws4_request" % (scope_date, REGION)
    string_to_sign = "\n".join(["AWS4-X509-ECDSA-SHA256", amz_date, scope, sha256_hex(canonical)])
    auth = "AWS4-X509-ECDSA-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s" % (
        serial, scope, signed_headers, sign_with_certificate(string_to_sign))

    req = urllib.request.Request("https://%s/sessions" % host, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "Host": host,
        "X-Amz-Date": amz_date,
        "X-Amz-X509": b64_cert,
        "Authorization": auth,
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        out = json.loads(r.read())
    c = out["credentialSet"][0]["credentials"]
    return c["accessKeyId"], c["secretAccessKey"], c["sessionToken"], c["expiration"]


def put_object(key_id, secret, token, key, payload):
    """Ordinary SigV4, with credentials that stop working within the hour."""
    host = "%s.s3.%s.amazonaws.com" % (BUCKET, REGION)
    now = dt.datetime.now(dt.timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    scope_date = now.strftime("%Y%m%d")
    payload_hash = sha256_hex(payload)

    signed_headers = "host;x-amz-content-sha256;x-amz-date;x-amz-security-token"
    canonical = "\n".join([
        "PUT", "/" + key, "",
        "host:" + host,
        "x-amz-content-sha256:" + payload_hash,
        "x-amz-date:" + amz_date,
        "x-amz-security-token:" + token,
        "", signed_headers, payload_hash,
    ])
    scope = "%s/%s/s3/aws4_request" % (scope_date, REGION)
    string_to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, sha256_hex(canonical)])

    k = ("AWS4" + secret).encode()
    for part in (scope_date, REGION, "s3", "aws4_request"):
        k = hmac.new(k, part.encode(), hashlib.sha256).digest()
    signature = hmac.new(k, string_to_sign.encode(), hashlib.sha256).hexdigest()

    req = urllib.request.Request("https://%s/%s" % (host, key), data=payload, method="PUT", headers={
        "Host": host,
        "X-Amz-Content-Sha256": payload_hash,
        "X-Amz-Date": amz_date,
        "X-Amz-Security-Token": token,
        "Authorization": "AWS4-HMAC-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s" % (
            key_id, scope, signed_headers, signature),
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def unsent():
    """Lines written since the last successful upload, and the new offset.

    The offset is bytes, kept outside the data volume's rotation: if the
    readings file is shorter than the offset it has been rotated, and the
    honest thing is to start again from the beginning rather than guess.
    """
    try:
        offset = int(open(STATE).read().strip())
    except (OSError, ValueError):
        offset = 0
    size = os.path.getsize(DATA)
    if size < offset:
        offset = 0
    with open(DATA, "rb") as f:
        f.seek(offset)
        chunk = f.read(MAX_BATCH)
    # Never ship half a line: a truncated JSON line is worse than a late one.
    cut = chunk.rfind(b"\n")
    if cut < 0:
        return b"", offset
    return chunk[:cut + 1], offset + cut + 1


def main():
    missing = [n for n in ("BUCKET", "TRUST_ANCHOR_ARN", "PROFILE_ARN", "ROLE_ARN") if not os.environ.get(n)]
    if missing:
        sys.exit("missing: " + ", ".join(missing) + " -- every real value comes from the environment")
    payload, new_offset = unsent()
    if not payload:
        print("nothing new")
        return
    key_id, secret, token, expires = create_session()
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y/%m/%d/%H%M%S")
    key = "%s/%s.jsonl" % (PREFIX, stamp)
    status = put_object(key_id, secret, token, key, payload)
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as f:
        f.write(str(new_offset))
    print("uploaded %d bytes, %d lines -> %s (HTTP %d), credentials expire %s"
          % (len(payload), payload.count(b"\n"), key, status, expires))


if __name__ == "__main__":
    main()
