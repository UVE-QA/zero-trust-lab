#!/usr/bin/env python3
"""Read-only access to the tailnet's policy API, for CI.

    tailnet-api.py validate policy/.rendered/policy.hujson
    tailnet-api.py drift    policy/.rendered/policy.hujson

validate  Submit a proposed policy to the tailnet without applying it. The
          control plane parses it and runs its `tests` section against the
          real tailnet -- the same evaluation that refuses a bad save in the
          console, available before merge instead of at apply time.

drift     Read the policy in force and compare it, byte for byte, with the
          render of main. The console stores the file verbatim (D-040), so any
          difference is real: an apply is pending, or someone edited the
          console directly.

No Tailscale secret exists anywhere. GitHub issues this job a signed OIDC
token; Tailscale exchanges it for a short-lived API token through a trust
credential that matches this repository's exact subject. The credential
carries `policy_file:read`, which the console will not grant without also
granting `devices:core:read` and `devices:posture_attributes:read` -- the
validator needs them to evaluate tests that involve devices and posture. All
three are read-only: enough to validate and to read, not enough to change
anything. Applying is a person's job (D-041).

Standard library only: a script that holds a credential, however narrow,
should not pull a dependency tree in with it.
"""
import base64
import hashlib
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.tailscale.com/api/v2"
TIMEOUT = 20


def die(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(2)


def in_actions():
    return os.environ.get("GITHUB_ACTIONS") == "true"


def mask(value):
    """Tell the Actions log to redact a value from here on."""
    if in_actions() and value:
        print(f"::add-mask::{value}")


# --- redaction -------------------------------------------------------------
# The policy values are secrets in CI and Actions masks them already. This is
# the second layer: anything this script prints passes through here first, so
# a failed test reads `<operator_identity>` rather than relying on the log
# masker alone to catch it.
REDACTIONS = {
    v: "<" + k[len("POLICY_VALUE_"):].lower() + ">"
    for k, v in os.environ.items()
    if k.startswith("POLICY_VALUE_") and v.strip()
}


def redact(text):
    for value, label in REDACTIONS.items():
        text = text.replace(value, label)
    return text


# --- authentication --------------------------------------------------------
def github_oidc_token(audience):
    url = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL")
    bearer = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN")
    if not url or not bearer:
        die("no GitHub OIDC endpoint in the environment. The job needs "
            "`permissions: id-token: write`, and this only works inside Actions.")
    req = urllib.request.Request(
        url + "&audience=" + urllib.parse.quote(audience, safe=""),
        headers={"Authorization": f"bearer {bearer}"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        token = json.load(r)["value"]
    mask(token)
    return token


def claims(jwt):
    """Decode the payload WITHOUT verifying it -- for diagnostics only."""
    try:
        payload = jwt.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return {}


def tailscale_token():
    client_id = os.environ.get("TS_OIDC_CLIENT_ID", "").strip()
    audience = os.environ.get("TS_OIDC_AUDIENCE", "").strip()
    if not client_id or not audience:
        die("TS_OIDC_CLIENT_ID and TS_OIDC_AUDIENCE must both be set.")

    jwt = github_oidc_token(audience)
    # Mirrors the request Tailscale's own client makes (tailscale/tailscale,
    # feature/identityfederation): a form POST carrying client_id and jwt.
    form = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": "",
        "client_id": client_id,
        "jwt": jwt,
    }).encode()
    req = urllib.request.Request(
        f"{API}/oauth/token-exchange", data=form, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = json.load(r)
    except urllib.error.HTTPError as e:
        # The one diagnostic that settles almost every federation failure is
        # the subject GitHub actually presented, compared with the one the
        # trust credential expects. Print those claims -- never the token.
        c = claims(jwt)
        print(f"token exchange refused: HTTP {e.code}", file=sys.stderr)
        print(f"  body: {e.read().decode(errors='replace')[:500]}", file=sys.stderr)
        print(f"  presented sub: {c.get('sub')}", file=sys.stderr)
        print(f"  presented aud: {c.get('aud')}", file=sys.stderr)
        sys.exit(2)

    token = body.get("access_token")
    if not token:
        die("token exchange returned no access_token")
    mask(token)
    return token


# --- API -------------------------------------------------------------------
def call(method, path, token, data=None, headers=None):
    h = {"Authorization": f"Bearer {token}"}
    h.update(headers or {})
    req = urllib.request.Request(f"{API}{path}", data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def cmd_validate(policy):
    token = tailscale_token()
    status, body = call(
        "POST", "/tailnet/-/acl/validate", token, data=policy,
        headers={"Content-Type": "application/hujson"},
    )
    if status != 200:
        die(f"validate returned HTTP {status}: "
            f"{redact(body.decode(errors='replace'))[:800]}")

    # A FAILED validation is also HTTP 200. The only difference is the body:
    # empty means every test passed. Checking the status code alone would
    # pass a policy the tailnet itself would refuse.
    text = body.decode(errors="replace").strip()
    result = json.loads(text) if text else {}
    if not result or (not result.get("message") and not result.get("data")):
        print(f"OK: the tailnet parsed the policy and every test passed "
              f"({len(policy)} bytes, sha256 {hashlib.sha256(policy).hexdigest()}).")
        return 0

    print(f"FAIL: {redact(result.get('message') or 'validation failed')}")
    for entry in result.get("data") or []:
        who = redact(str(entry.get("user") or entry.get("src") or "?"))
        for err in entry.get("errors") or []:
            print(f"  {who}: {redact(err)}")
    return 1


def cmd_drift(policy):
    token = tailscale_token()
    status, live = call("GET", "/tailnet/-/acl", token,
                        headers={"Accept": "application/hujson"})
    if status != 200:
        die(f"reading the live policy returned HTTP {status}")

    want = hashlib.sha256(policy).hexdigest()
    got = hashlib.sha256(live).hexdigest()
    print(f"render of this commit : {len(policy):6d} bytes  sha256 {want}")
    print(f"policy in force       : {len(live):6d} bytes  sha256 {got}")
    if want == got:
        print("OK: the tailnet enforces exactly the policy on this commit.")
        return 0
    # Content is deliberately not printed or diffed: the live file carries the
    # real values, and a diff is one careless log away from publishing them.
    print("DRIFT: the policy in force is not the render of this commit.\n"
          "Either an apply is pending, or the policy was edited in the console.\n"
          "Nothing edits the file on save, so there is no benign explanation to\n"
          "rule out first. Compare locally: render, fetch, diff.")
    return 1


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("validate", "drift"):
        die(__doc__.split("\n\n")[1])
    path = pathlib.Path(sys.argv[2])
    if not path.is_file():
        die(f"{path} not found -- render it first: scripts/render-policy.py --from-env")
    for v in REDACTIONS:
        mask(v)
    policy = path.read_bytes()
    sys.exit(cmd_validate(policy) if sys.argv[1] == "validate" else cmd_drift(policy))


if __name__ == "__main__":
    main()
