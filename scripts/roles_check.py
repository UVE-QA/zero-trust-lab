#!/usr/bin/env python3
"""Raise an issue when a role that should have a live node has none.

A role that empties is invisible in every check this lab already runs. The
policy still names it, the tests still pass -- they assert what the role may
reach, not that anyone is there -- and a drill against it returns a
reassuring zero that means "the target is switched off" rather than "access is
refused".

That is not hypothetical: the media appliance went offline after a system
update and stayed offline for six days. It is the test user's only
destination and the intended standby route into the house, and nothing said a
word (D-076).

    ./scripts/roles_check.py tailnet-aggregate/aggregate.json docs/roles-expected.json

Reads counts, never addresses or names, so its output is safe in a public log
and in a public issue.
"""
import json
import os
import sys
import urllib.request

REPO = os.environ.get("GITHUB_REPOSITORY", "")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
TITLE = "A role has no live node"


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
    agg = json.loads(open(sys.argv[1], encoding="utf-8").read())
    spec = json.loads(open(sys.argv[2], encoding="utf-8").read())
    roles = agg.get("tagged_roles", {})

    empty, surprises = [], []
    for role, why in spec["expected_live"].items():
        seen = roles.get(role, {"count": 0, "online": 0})
        if seen["online"] < 1:
            empty.append((role, seen, why))
        print(f"  {'ok ' if seen['online'] else 'EMPTY'} {role:22} {seen['online']} of {seen['count']} online")
    for role, why in spec.get("expected_empty", {}).items():
        seen = roles.get(role, {"count": 0, "online": 0})
        if seen["online"]:
            surprises.append((role, seen, why))
            print(f"  new   {role:22} {seen['online']} of {seen['count']} online -- expected none")

    if not TOKEN or not REPO:
        print("\nno GitHub token: reporting only")
        return 1 if empty else 0

    found = [i for i in gh(f"/repos/{REPO}/issues?state=open&per_page=50") if i["title"] == TITLE]
    issue = found[0] if found else None

    if not empty:
        if issue:
            gh(f'/repos/{REPO}/issues/{issue["number"]}', "PATCH", {"state": "closed"})
            print(f'\nclosed #{issue["number"]}: every role that should be live has a node')
        else:
            print("\nOK: every role that should be live has a live node")
        return 0

    lines = [f"Checked {agg.get('counted_at', 'just now')}. A role below is named by the policy, "
             f"asserted by the tests, and has nobody behind it. Checks do not notice this on their "
             f"own: a test says what a role may reach, not that it is there.", "",
             "| role | live nodes | why it should not be empty |", "|---|---|---|"]
    lines += [f'| `{r}` | {s["online"]} of {s["count"]} | {why} |' for r, s, why in empty]
    if surprises:
        lines += ["", "Also, a role expected to be empty is not — which may be good news, and "
                  "should be moved in `docs/roles-expected.json` if it is:", ""]
        lines += [f'- `{r}`: {s["online"]} of {s["count"]} online' for r, s, _ in surprises]
    lines += ["", "This issue closes itself when the role has a live node again."]
    body = "\n".join(lines)

    if issue:
        gh(f'/repos/{REPO}/issues/{issue["number"]}', "PATCH", {"body": body})
        print(f'\nupdated #{issue["number"]}: {len(empty)} empty role(s)')
    else:
        made = gh(f"/repos/{REPO}/issues", "POST", {"title": TITLE, "body": body})
        print(f'\nopened #{made["number"]}: {len(empty)} empty role(s)')
    return 0


if __name__ == "__main__":
    sys.exit(main())
