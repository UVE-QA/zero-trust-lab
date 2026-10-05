#!/usr/bin/env python3
"""Open an issue when a check on main turns red, and close it when it is green.

A red tile on the evidence page notifies nobody. The cloud tile was red for two
weeks and the policy drift check for three days before anyone looked (D-078,
D-080); the page caught both, and that was the whole of it. An issue is the
cheapest alarm there is: the repository's owner is notified when one opens,
and it closes itself, so an open one always means something is red now.

    ./scripts/alarm.py --title "..." --state fail --why "..."
    ./scripts/alarm.py --title "..." --state pass

One issue per title: a second failure updates the open issue rather than
opening another. Says nothing a public log should not: the caller writes the
text, and every caller here writes counts, hashes and links only.
"""
import argparse
import json
import os
import sys
import urllib.request

REPO = os.environ.get("GITHUB_REPOSITORY", "")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
RUN = (f'{os.environ.get("GITHUB_SERVER_URL", "https://github.com")}/{REPO}'
       f'/actions/runs/{os.environ.get("GITHUB_RUN_ID", "")}')


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
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    ap.add_argument("--state", required=True, choices=["pass", "fail"])
    ap.add_argument("--why", default="", help="what is red and what to look at")
    a = ap.parse_args()

    if not TOKEN or not REPO:
        print(f"no GitHub token: reporting only -- {a.state}: {a.title}")
        return 0

    found = [i for i in gh(f"/repos/{REPO}/issues?state=open&per_page=50")
             if i["title"] == a.title and "pull_request" not in i]
    issue = found[0] if found else None

    if a.state == "pass":
        if issue:
            gh(f'/repos/{REPO}/issues/{issue["number"]}/comments', "POST",
               {"body": f"Green again: {RUN}"})
            gh(f'/repos/{REPO}/issues/{issue["number"]}', "PATCH", {"state": "closed"})
            print(f'closed #{issue["number"]}: green again')
        else:
            print(f"green: {a.title}")
        return 0

    body = "\n\n".join(x for x in [
        a.why,
        f"The run: {RUN}",
        "This issue closes itself when the same check is green on main again.",
    ] if x)
    if issue:
        gh(f'/repos/{REPO}/issues/{issue["number"]}', "PATCH", {"body": body})
        gh(f'/repos/{REPO}/issues/{issue["number"]}/comments', "POST",
           {"body": f"Still red: {RUN}"})
        print(f'updated #{issue["number"]}: still red')
    else:
        made = gh(f"/repos/{REPO}/issues", "POST", {"title": a.title, "body": body})
        print(f'opened #{made["number"]}: {a.title}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
