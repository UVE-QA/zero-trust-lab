#!/usr/bin/env python3
"""Raise an issue when a drill is older than its own cadence.

A drill is a number that only stays true if it is taken again. This reads
docs/drills.json, and when one is overdue it opens -- or updates -- a single
issue naming which, so the slip shows up without anyone remembering to look.
Read-only against everything except that one issue.

    GITHUB_TOKEN=... GITHUB_REPOSITORY=owner/repo ./scripts/drills_due.py [--dry-run]
"""
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.environ.get("GITHUB_REPOSITORY", "UVE-QA/zero-trust-lab")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
TITLE = "Drills due"
API = "https://api.github.com"


def gh(path, method="GET", body=None):
    req = urllib.request.Request(
        API + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Accept": "application/vnd.github+json",
                 "Authorization": f"Bearer {TOKEN}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main():
    dry = "--dry-run" in sys.argv
    today = dt.date.today()
    drills = json.load(open(os.path.join(ROOT, "docs", "drills.json")))["drills"]
    overdue = []
    for d in drills:
        due = dt.date.fromisoformat(d["date"]) + dt.timedelta(days=int(d.get("cadence_days", 30)))
        state = "overdue" if today > due else "due " + due.isoformat()
        print(f'{d["name"]}: last {d["date"]}, {state}')
        if today > due:
            overdue.append((d, (today - due).days))
    open_issue = None
    if TOKEN and not dry:
        found = [i for i in gh(f"/repos/{REPO}/issues?state=open&per_page=50") if i["title"] == TITLE]
        open_issue = found[0] if found else None
    if not overdue:
        if open_issue:
            gh(f'/repos/{REPO}/issues/{open_issue["number"]}', "PATCH", {"state": "closed"})
            print(f'closed issue #{open_issue["number"]}: every drill is within its cadence')
        return 0
    lines = ["A drill's numbers are only true for as long as the drill is recent. These have slipped:", ""]
    lines += [f'- **{d["name"]}** — last run {d["date"]}, {n} day{"s" if n != 1 else ""} past its '
              f'{d.get("cadence_days", 30)}-day cadence. Runbook: `{d["runbook"]}`' for d, n in overdue]
    lines += ["", "Re-run it and update `docs/drills.json` with the new figures. This check closes the issue "
              "once every drill is back within its cadence."]
    body = "\n".join(lines)
    if dry or not TOKEN:
        print("\n--- issue body ---\n" + body)
        return 0
    if open_issue:
        gh(f'/repos/{REPO}/issues/{open_issue["number"]}', "PATCH", {"body": body})
        print(f'updated issue #{open_issue["number"]}')
    else:
        n = gh(f"/repos/{REPO}/issues", "POST", {"title": TITLE, "body": body})["number"]
        print(f"opened issue #{n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
