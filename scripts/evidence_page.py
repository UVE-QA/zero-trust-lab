#!/usr/bin/env python3
"""Build the live evidence page: every status on it is read, not written.

    GITHUB_TOKEN=... GITHUB_REPOSITORY=owner/repo ./scripts/evidence_page.py --out site

The page makes claims about this lab and backs each one with the GitHub
Actions run that checked it. At build time this script asks GitHub for the
latest result of each check and renders what it gets back -- pass, fail, or
"no data" -- with the time it ran and a link to the run. Nothing on the page
is a status typed by a person.

It holds no tailnet or cloud credential. What it reads is GitHub's public
record of this repository's CI, plus the repository's own files for the
figures that come from the code, which the page labels as such.

Standard library only, and every value is HTML-escaped: run names and times
come from an API, and an API is input.
"""
import argparse
import datetime as dt
import html
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
API = "https://api.github.com"
REPO = os.environ.get("GITHUB_REPOSITORY", "UVE-QA/zero-trust-lab")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
SERVER = "https://github.com"

# Runs that count as "the state of main", as opposed to a pull request's
# proposal. A check that has only ever passed on a branch proves nothing
# about what is in force.
MAIN_EVENTS = {"schedule", "push", "workflow_dispatch"}


def gh(path):
    req = urllib.request.Request(f"{API}{path}", headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        print(f"warning: GET {path} -> HTTP {e.code}", file=sys.stderr)
        return None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def gh_text(path):
    """Fetch a job log. GitHub answers with a redirect to a short-lived signed
    URL on its storage host, which rejects the API token -- so the redirect is
    followed by hand, without the token. Following it automatically carried
    the header along and turned a passing check into a false failure."""
    req = urllib.request.Request(f"{API}{path}", headers={
        "Accept": "application/vnd.github+json",
        **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
    })
    try:
        urllib.request.build_opener(_NoRedirect).open(req, timeout=60)
        print(f"warning: GET {path} did not redirect", file=sys.stderr)
        return ""
    except urllib.error.HTTPError as e:
        if e.code not in (301, 302, 303, 307, 308):
            print(f"warning: GET {path} -> HTTP {e.code}", file=sys.stderr)
            return ""
        location = e.headers.get("Location", "")
    try:
        with urllib.request.urlopen(location, timeout=60) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        print(f"warning: log download -> HTTP {e.code}", file=sys.stderr)
        return ""


def latest_job(workflow, job_name, events=MAIN_EVENTS, need=None):
    """Newest completed run of `job_name` on main that actually ran.

    Skipped and cancelled jobs are passed over: a skipped check is not a
    passing one. `need`, if given, must return True for the job's log --
    used where "the job succeeded" is weaker than the claim being made.
    """
    runs = gh(f"/repos/{REPO}/actions/workflows/{workflow}/runs"
              f"?branch=main&status=completed&per_page=30") or {}
    for run in runs.get("workflow_runs", []):
        if run.get("event") not in events:
            continue
        jobs = gh(f"/repos/{REPO}/actions/runs/{run['id']}/jobs") or {}
        for job in jobs.get("jobs", []):
            if job.get("name") != job_name:
                continue
            if job.get("conclusion") not in ("success", "failure"):
                break
            ok = job["conclusion"] == "success"
            detail = None
            if ok and need is not None:
                ok, detail = need(gh_text(f"/repos/{REPO}/actions/jobs/{job['id']}/logs"))
            return {
                "ok": ok,
                "at": job.get("completed_at"),
                "url": job.get("html_url"),
                "sha": (run.get("head_sha") or "")[:7],
                "event": run.get("event"),
                "detail": detail,
            }
    return None


ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def plan_says_no_changes(log):
    # Terraform colours its output; the escape codes sit between the words of
    # the very sentence being looked for.
    if "No changes. Your infrastructure matches the configuration." in ANSI.sub("", log):
        return True, "terraform plan: no changes"
    return False, "terraform plan reported changes, or its output was not found"


def negative_control(pr_number, check_name):
    """A pull request that was broken on purpose. The expected result is FAILURE."""
    pr = gh(f"/repos/{REPO}/pulls/{pr_number}")
    if not pr:
        return None
    runs = gh(f"/repos/{REPO}/commits/{pr['head']['sha']}/check-runs"
              f"?check_name={urllib.request.quote(check_name)}") or {}
    for cr in runs.get("check_runs", []):
        return {
            "ok": cr.get("conclusion") == "failure" and not pr.get("merged_at"),
            "at": cr.get("completed_at"),
            "url": cr.get("html_url"),
            "sha": pr["head"]["sha"][:7],
            "event": "pull_request",
            "detail": f"PR #{pr_number}: {cr.get('conclusion')}, "
                      f"{'merged' if pr.get('merged_at') else 'closed without merging'}",
        }
    return None


def branch_protected():
    """Only what the public branch record states: the required checks, and who
    they apply to. Whether a pull request is required is not in that record,
    so the page does not claim it."""
    b = gh(f"/repos/{REPO}/branches/main")
    if b is None:
        return None
    rsc = (b.get("protection") or {}).get("required_status_checks") or {}
    checks = rsc.get("contexts") or []
    level = rsc.get("enforcement_level", "off")
    return {
        "ok": bool(b.get("protected")) and bool(checks) and level == "everyone",
        "at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "url": f"{SERVER}/{REPO}/branches",
        "link": "see the branch →",
        "sha": (b.get("commit", {}).get("sha") or "")[:7],
        "event": "read from GitHub at build",
        "detail": f"required: {', '.join(checks) or 'none'} · applies to: {level}",
    }


# --- figures from the code ---------------------------------------------------
def policy_figures():
    s = (ROOT / "policy" / "policy.hujson.tmpl").read_text()
    grants = s[s.index('"grants"'):s.index('"ssh"')]
    tests = s[s.index('"tests"'):]
    count = lambda key: sum(len(re.findall(r'"[^"]+"', m))
                            for m in re.findall(rf'"{key}":\s*\[([^\]]*)\]', tests))
    return {
        "grants": len(re.findall(r"^\t\t\{", grants, re.M)),
        "accept": count("accept"),
        "deny": count("deny"),
        "addresses": len(re.findall(r'"\{\{\w+\}\}"', s[s.index('"hosts"'):s.index('"grants"')])),
        "wildcard": '"*"' in grants,
    }


def decision_figures():
    heads = re.findall(r"^## (D-\d+) — (.*)$",
                       (ROOT / "docs" / "02-decisions.md").read_text(), re.M)
    return {
        "decisions": len(heads),
        "corrections": sum(1 for _, t in heads if t.lower().startswith("correction")),
    }


# --- rendering ---------------------------------------------------------------
E = html.escape


def card(claim, why, result, stale_hours, expect_failure=False):
    if result is None:
        state, label = "none", "no data"
    elif result["ok"]:
        state, label = "pass", ("refused, as it should be" if expect_failure else "pass")
    else:
        state, label = "fail", ("not refused" if expect_failure else "fail")
    ev = ""
    if result:
        bits = []
        if result.get("detail"):
            bits.append(E(result["detail"]))
        if result.get("sha"):
            bits.append(f"commit <code>{E(result['sha'])}</code>")
        if result.get("event"):
            bits.append(E(result["event"]))
        ev = (f'<p class="ev">{" · ".join(bits)}</p>'
              f'<p class="ev"><time data-stale-hours="{stale_hours}" '
              f'datetime="{E(result["at"] or "")}">{E(result["at"] or "")}</time>'
              f' · <a href="{E(result["url"] or "#")}">{E(result.get("link", "open the run →"))}</a></p>')
    return (f'<article class="card {state}"><div class="row"><h3>{E(claim)}</h3>'
            f'<span class="pill">{E(label)}</span></div><p class="why">{E(why)}</p>{ev}</article>')


def render(measured, pol, dec, built):
    blob = f"{SERVER}/{REPO}/blob/main"
    live = "".join(card(*m) for m in measured["live"])
    every = "".join(card(*m) for m in measured["every"])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>zero-trust-lab · live evidence</title>
<meta name="description" content="A home Zero Trust lab. Every status on this page is read from the CI run that checked it.">
<style>
:root{{--bg:#fbfaf8;--fg:#1d1d1b;--mut:#6b6a66;--line:#e4e1dc;--card:#fff;--pass:#1f7a4d;--passbg:#e6f4ec;--fail:#b3261e;--failbg:#fbe9e7;--none:#6b6a66;--nonebg:#efedea;--stale:#8a5a00;--stalebg:#fff4d6;--link:#1a56b8}}
@media (prefers-color-scheme:dark){{:root{{--bg:#131312;--fg:#ecebe8;--mut:#a3a19b;--line:#2e2d2a;--card:#1b1b19;--pass:#6fd19c;--passbg:#15301f;--fail:#ff8a80;--failbg:#3a1714;--none:#a3a19b;--nonebg:#262522;--stale:#ffcf66;--stalebg:#3a2e10;--link:#8ab4ff}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:880px;margin:0 auto;padding:48px 20px 64px}}
h1{{font-size:28px;line-height:1.2;margin:0 0 8px}}h2{{font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:var(--mut);margin:40px 0 12px}}
h3{{font-size:16px;margin:0}}p{{margin:6px 0}}a{{color:var(--link)}}code{{font:13px ui-monospace,SFMono-Regular,Menlo,monospace}}
.lede{{color:var(--mut);max-width:640px}}.built{{font-size:14px;color:var(--mut);margin-top:14px}}
.card{{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--none);border-radius:8px;padding:14px 16px;margin:10px 0}}
.card.pass{{border-left-color:var(--pass)}}.card.fail{{border-left-color:var(--fail)}}.card.stale{{border-left-color:var(--stale)}}
.row{{display:flex;justify-content:space-between;gap:12px;align-items:baseline}}
.pill{{font-size:13px;font-weight:600;padding:2px 10px;border-radius:999px;white-space:nowrap;background:var(--nonebg);color:var(--none)}}
.pass .pill{{background:var(--passbg);color:var(--pass)}}.fail .pill{{background:var(--failbg);color:var(--fail)}}.stale .pill{{background:var(--stalebg);color:var(--stale)}}
.why{{color:var(--mut);font-size:15px}}.ev{{font-size:14px;color:var(--mut)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}}
.fig{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 16px}}.fig b{{display:block;font-size:26px}}.fig span{{color:var(--mut);font-size:14px}}
footer{{margin-top:48px;padding-top:16px;border-top:1px solid var(--line);color:var(--mut);font-size:14px}}
</style></head><body><main>
<h1>zero-trust-lab · live evidence</h1>
<p class="lede">A Zero Trust access model on a real home network, built in the open.
Every status below was read from GitHub Actions when this page was built, and links to
the run that produced it. None of them is typed by hand. A check older than its schedule
turns amber on its own.</p>
<p class="built">Built <time data-stale-hours="30" datetime="{E(built)}">{E(built)}</time> ·
<a href="{SERVER}/{REPO}">repository</a> · <a href="{blob}/STATUS.md">status and plan</a> ·
<a href="{blob}/docs/02-decisions.md">decision log</a></p>

<h2>Checked against the live network</h2>
{live}

<h2>Checked on every change</h2>
{every}

<h2>From the code, not measured</h2>
<p class="why">Counted from the repository's files when the page was built. The live checks
above are what show these are the rules actually in force.</p>
<div class="grid">
<div class="fig"><b>{pol['grants']}</b><span>access grants, each naming one port</span></div>
<div class="fig"><b>{pol['accept'] + pol['deny']}</b><span>policy assertions — {pol['deny']} of them must be refused</span></div>
<div class="fig"><b>{pol['addresses']}</b><span>real addresses in the whole policy</span></div>
<div class="fig"><b>{'yes' if pol['wildcard'] else 'none'}</b><span>wildcard grants</span></div>
<div class="fig"><b>{dec['decisions']}</b><span>recorded decisions</span></div>
<div class="fig"><b>{dec['corrections']}</b><span>of them correct an earlier one</span></div>
</div>
<p class="ev"><a href="{blob}/policy/policy.hujson.tmpl">policy template</a> ·
<a href="{blob}/docs/02-decisions.md">decision log</a></p>

<h2>Not shown here</h2>
<p class="why">What is unfinished is stated in <a href="{blob}/STATUS.md">STATUS.md</a>,
under “Open, stated plainly” — including the gaps this page cannot measure.</p>

<footer>Built by <a href="{blob}/.github/workflows/evidence-page.yml">evidence-page.yml</a>
from <a href="{blob}/scripts/evidence_page.py">evidence_page.py</a>. The job that builds
this page holds no network or cloud credential; it can write to this page and nothing else.</footer>
</main>
<script>
(function(){{var now=Date.now();document.querySelectorAll('time[datetime]').forEach(function(t){{
var d=Date.parse(t.getAttribute('datetime'));if(isNaN(d))return;var h=(now-d)/36e5;
var s=h<1?Math.round(h*60)+' min ago':h<48?Math.round(h)+' h ago':Math.round(h/24)+' days ago';
t.textContent=s+' ('+new Date(d).toISOString().slice(0,16).replace('T',' ')+' UTC)';
var lim=parseFloat(t.getAttribute('data-stale-hours'));var c=t.closest('.card');
if(c&&lim&&h>lim&&c.classList.contains('pass')){{c.classList.remove('pass');c.classList.add('stale');c.querySelector('.pill').textContent='stale';}}
}});}})();
</script>
</body></html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="site")
    args = ap.parse_args()

    tn = "tailnet-check.yml"
    live = [
        ("The policy in force is the one on main",
         "The live tailnet policy is read back and compared byte for byte with the "
         "render of main. The console stores the file verbatim, so any difference is real.",
         latest_job(tn, "policy in force matches main"), 30),
        ("Every policy test passes on the live network",
         "The tailnet itself parses the policy and runs its tests — including every "
         "“this must be refused” assertion — against the real devices. Read-only; "
         "no credential is stored anywhere.",
         latest_job(tn, "tailnet tests (validate, read-only)"), 30),
        ("The tests can fail",
         "A pull request that deliberately asserted a forbidden path. The pipeline "
         "refused it. A check that has only ever been seen passing proves nothing.",
         negative_control(8, "tailnet tests (validate, read-only)"), 10**9, True),
        ("Cloud infrastructure matches its code",
         "A read-only plan against the cloud account, authenticated by federation — "
         "no access keys exist. CI can plan; only a person can apply.",
         latest_job("terraform-plan.yml", "plan", need=plan_says_no_changes), 24 * 8),
    ]
    every = [
        ("No real address, hostname or account id can merge",
         "Every file and every commit message is swept for real-world values before "
         "merge, including a private list of this network's own names.",
         latest_job("leak-scan.yml", "disclosure sweep", events={"push"}), 24 * 30),
        ("No secrets in history",
         "The whole git history is scanned for credentials on every change.",
         latest_job("leak-scan.yml", "secret scanner", events={"push"}), 24 * 30),
        ("main accepts only changes that passed its checks",
         "GitHub enforces the checks above on main for everyone, the owner included.",
         branch_protected(), 30),
    ]
    built = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    page = render({"live": [(c, w, r, s, *x) for c, w, r, s, *x in live],
                   "every": [(c, w, r, s) for c, w, r, s in every]},
                  policy_figures(), decision_figures(), built)

    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(page)
    (out / ".nojekyll").write_text("")
    summary = {c: (None if r is None else r["ok"]) for c, _, r, *_ in live + every}
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
