#!/usr/bin/env python3
"""Raise an issue when a node key is about to expire.

A key that expires takes its node off the network until somebody signs in
again ON THAT DEVICE. The two nodes that carry the only way into the house
have expiry switched off for exactly that reason (D-071); everything that
travels keeps it, because there the expiry means what it says. This job is the
warning for the second group: thirty days is enough to act while the device is
still in your hands.

Reads a file written by `tailnet-api.py keys`; writes one issue and nothing
else. Names only -- no addresses -- because the issue is public.
"""
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

REPO = os.environ.get("GITHUB_REPOSITORY", "")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
TITLE = "Node keys expiring soon"
WARN_DAYS = int(os.environ.get("WARN_DAYS", "30"))


def gh(path, method="GET", body=None):
    req = urllib.request.Request(
        "https://api.github.com" + path, method=method,
        data=json.dumps(body).encode() if body else None,
        headers={"Accept": "application/vnd.github+json",
                 "Authorization": f"Bearer {TOKEN}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r) if r.status != 204 else None


def main():
    data = json.loads(pathlib.Path(sys.argv[1]).read_text())
    due = [n for n in data["nodes"] if n["days"] <= WARN_DAYS]

    found = [i for i in gh(f"/repos/{REPO}/issues?state=open&per_page=50") if i["title"] == TITLE]
    issue = found[0] if found else None

    if not due:
        if issue:
            gh(f'/repos/{REPO}/issues/{issue["number"]}', "PATCH", {"state": "closed"})
            print(f'closed #{issue["number"]}: no key expires within {WARN_DAYS} days')
        else:
            print(f"nothing expires within {WARN_DAYS} days")
        return 0

    lines = [f"Checked {data['checked_at']}. A key that expires takes its node off the network "
             f"until someone signs in again **on that device** — so this is the warning while "
             f"the device is still to hand.", "", "| node | days left | expires |", "|---|---|---|"]
    lines += [f'| `{n["name"]}` | **{n["days"]}** | {n["expires"]} |' for n in due]
    lines += ["", "Renew by opening the Tailscale client on the device and signing in again. "
              "Nodes that carry the only way into the house have expiry disabled on purpose "
              "(D-071); if one of those appears here, someone has re-enabled it."]
    body = "\n".join(lines)

    if issue:
        gh(f'/repos/{REPO}/issues/{issue["number"]}', "PATCH", {"body": body})
        print(f'updated #{issue["number"]}: {len(due)} key(s) within {WARN_DAYS} days')
    else:
        made = gh(f"/repos/{REPO}/issues", "POST", {"title": TITLE, "body": body})
        print(f'opened #{made["number"]}: {len(due)} key(s) within {WARN_DAYS} days')
    return 0


if __name__ == "__main__":
    sys.exit(main())
