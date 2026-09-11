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
import io
import urllib.error
import urllib.request
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import evidence_diagram  # noqa: E402

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
                # for the page's live layer: which run this card shows
                "wf": workflow, "job": job_name, "run": run["id"], "need": need is not None,
            }
    return None


ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def gh_bytes(url):
    """Download an artifact archive: same signed-URL redirect as job logs."""
    req = urllib.request.Request(url, headers={
        **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {})})
    try:
        urllib.request.build_opener(_NoRedirect).open(req, timeout=60)
        return b""
    except urllib.error.HTTPError as e:
        if e.code not in (301, 302, 303, 307, 308):
            print(f"warning: artifact -> HTTP {e.code}", file=sys.stderr)
            return b""
        location = e.headers.get("Location", "")
    with urllib.request.urlopen(location, timeout=60) as r:
        return r.read()


def tailnet_aggregate():
    """Counts written by tailnet-check's drift job on main -- the page's only
    view into the network, and it contains numbers and nothing else."""
    runs = gh(f"/repos/{REPO}/actions/workflows/tailnet-check.yml/runs"
              f"?branch=main&status=completed&per_page=20") or {}
    for run in runs.get("workflow_runs", []):
        if run.get("event") not in MAIN_EVENTS:
            continue
        arts = gh(f"/repos/{REPO}/actions/runs/{run['id']}/artifacts") or {}
        for a in arts.get("artifacts", []):
            if a.get("name") == "tailnet-aggregate" and not a.get("expired"):
                blob = gh_bytes(a["archive_download_url"])
                if not blob:
                    return None
                with zipfile.ZipFile(io.BytesIO(blob)) as z:
                    agg = json.loads(z.read("aggregate.json"))
                agg["_run"] = run.get("html_url")
                return agg
    return None


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
    live = ""
    if result and result.get("wf"):
        live = (f' data-wf="{E(result["wf"])}" data-job="{E(result["job"])}" data-run="{result["run"]}"'
                + (' data-need="log"' if result.get("need") else ""))
    return (f'<article class="card {state}"{live}><div class="row"><h3>{E(claim)}</h3>'
            f'<span class="pill">{E(label)}</span></div><p class="why">{E(why)}</p>{ev}</article>')


def render(measured, pol, dec, built, diagram, agg, home):
    blob = f"{SERVER}/{REPO}/blob/main"
    rt = (agg or {}).get("routes_into_other_networks") or {}
    routes_n = rt.get("effective", rt.get("enabled", home.get("exposed_to_tailnet")))
    stale = rt.get("approved_not_advertised")
    routes_note = (f'measured live: {routes_n} routes in effect, the widest {rt.get("widest")}'
                   + (f"; {stale} approval{'s' if stale != 1 else ''} left behind with no route" if stale else "")
                   if rt else "from the policy")
    agg_note = (f'<a href="{E(agg.get("_run") or "#")}">live, counted on {E(agg.get("read_at", ""))}</a>'
                if agg else "shown once the network job has published its first count")
    live = "".join(card(*m) for m in measured["live"])
    every = "".join(card(*m) for m in measured["every"])
    drills = ""
    for d in json.loads((ROOT / "docs" / "drills.json").read_text()).get("drills", []):
        drills += (f'<h3>{E(d["name"])} · {E(d["date"])}</h3><div class="grid">'
                   f'<div class="fig"><b>{E(d["path_back"])}</b><span>for the network path to come back '
                   f'after a {E(d["outage"])} outage, with no hands</span></div>'
                   f'<div class="fig"><b>{E(d["readings_lost"])}</b><span>readings sent during the outage '
                   f'were lost; {E(str(d["replayed"]))} replayed — nothing is buffered, by design</span></div>'
                   f'<div class="fig"><b>{E(d["hands"])}</b><span>manual steps to recover</span></div></div>'
                   f'<p class="ev">Not tested: {E(d["not_tested"])} · '
                   f'<a href="{blob}/{E(d["runbook"])}">runbook, with the timeline</a></p>')
    roadmap = "".join(
        f'<tr><td><b>{E(i["what"])}</b></td><td><span class="st">{E(i["state"])}</span></td>'
        f'<td>{E(i["why"])}</td><td>{E(i["takes"])}</td><td>{E(i["ref"])}</td></tr>'
        for i in json.loads((ROOT / "docs" / "roadmap.json").read_text()).get("items", []))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>zero-trust-lab · live evidence</title>
<meta name="description" content="A home Zero Trust lab. Every status on this page is read from the CI run that checked it.">
<style>
:root{{--bg:#fbfaf8;--fg:#1d1d1b;--mut:#6b6a66;--line:#e4e1dc;--card:#fff;--pass:#1f7a4d;--passbg:#e6f4ec;--fail:#b3261e;--failbg:#fbe9e7;--none:#6b6a66;--nonebg:#efedea;--stale:#8a5a00;--stalebg:#fff4d6;--link:#1a56b8;--cp:#1f6feb;--cl:#c2410c}}
@media (prefers-color-scheme:dark){{:root{{--bg:#131312;--fg:#ecebe8;--mut:#a3a19b;--line:#2e2d2a;--card:#1b1b19;--pass:#6fd19c;--passbg:#15301f;--fail:#ff8a80;--failbg:#3a1714;--none:#a3a19b;--nonebg:#262522;--stale:#ffcf66;--stalebg:#3a2e10;--link:#8ab4ff;--cp:#6ea8ff;--cl:#f0883e}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:1220px;margin:0 auto;padding:48px 20px 64px}}.col{{max-width:880px}}
.diagram{{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px}}
.diagram svg{{min-width:960px;width:100%;height:auto;display:block;font-family:system-ui,-apple-system,"Segoe UI",sans-serif}}
.ct{{fill:none;stroke-width:1.5}}.ct.ci{{stroke:var(--mut)}}.ct.cp{{stroke:var(--cp)}}.ct.cloud{{stroke:var(--cl);fill:rgba(194,65,12,.035)}}
.ct.tailnet{{stroke:#5b4fd6;stroke-dasharray:9 6;fill:rgba(91,79,214,.03)}}.ct.future{{stroke:var(--mut);stroke-opacity:.6;stroke-dasharray:3 6;fill:rgba(128,128,128,.035)}}.ct.home{{stroke:#3f8624;fill:rgba(63,134,36,.04)}}
.grp{{fill:none;stroke:var(--mut);stroke-opacity:.45;stroke-dasharray:3 4}}.ctl{{font-size:13px;font-weight:650;fill:var(--fg)}}.ctn{{font-size:11.5px;fill:var(--mut)}}
.tile .t{{font-size:13px;font-weight:650;fill:var(--fg)}}.tile .s{{font-size:11px;fill:var(--mut)}}.tile .b{{font-size:10.5px;fill:var(--mut);font-family:ui-monospace,Menlo,monospace}}
.chip{{font-size:12px;fill:var(--fg)}}.chip .n{{font-weight:700;fill:#3f8624}}
.brief{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:10px;margin:22px 0 6px}}
.brief div{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}}
.brief h3{{font-size:12px;text-transform:uppercase;letter-spacing:.07em;color:var(--mut);margin:0 0 6px}}
.brief p{{margin:4px 0;font-size:15px}}.brief .big{{font-size:30px;font-weight:750;line-height:1.1}}
.lbl text{{font-size:11px;font-weight:650}}.lbl.f text{{font-weight:500}}
.legend{{font-size:13.5px;color:var(--mut);margin:10px 0}}.legend.warn{{color:var(--fail)}}
.k{{display:inline-block;width:22px;border-top:2px solid var(--pass);vertical-align:middle}}.k.no{{border-top:2px dashed var(--fail)}}.k.cf{{border-top:2px dashed var(--cp)}}
.layers{{display:flex;flex-wrap:wrap;gap:6px 18px;align-items:center;font-size:13.5px;color:var(--mut);padding:4px 8px 6px}}
.layers label{{display:flex;align-items:center;gap:7px;cursor:pointer;color:var(--fg)}}
#labmap.hide-grant .layer-grant,#labmap.hide-refusal .layer-refusal,#labmap.hide-control .layer-control{{display:none}}
details.parts{{margin:6px 0 0}}details.parts summary{{cursor:pointer;font-weight:600;font-size:14.5px}}
table.why{{width:100%;border-collapse:collapse;font-size:14px;margin-top:8px}}table.why th,table.why td{{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}}
table.why th{{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut)}}.sw{{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:8px}}
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
.now{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 16px;margin:18px 0 8px}}
.nowhead{{display:flex;align-items:center;gap:12px}}.nowhead h2{{margin:0;font-size:18px}}
.nowhead button{{margin-left:auto;font:inherit;font-size:13px;padding:4px 12px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg);cursor:pointer}}
.meta{{font-size:12.5px;color:var(--mut)}}.now .run{{border-top:1px solid var(--line);padding:8px 0}}.now .run:first-child{{border-top:0}}
.now ul{{list-style:none;padding:0;margin:6px 0 0}}.now li{{font-size:14px;margin:3px 0}}.now .ic{{display:inline-block;width:1.2em;text-align:center;font-weight:700}}
.now .success,.now .job.success .ic{{color:var(--pass)}}.now .failure,.now .job.failure .ic{{color:var(--fail)}}.now .job.in_progress .ic{{color:var(--cp)}}
.card.updated .pill::after{{content:" · live";font-weight:500}}
#labmap path.running{{stroke:var(--cp);stroke-width:2.6;stroke-dasharray:7 5;animation:flow .9s linear infinite}}
#n-gha.busy rect:first-of-type{{stroke:var(--cp);stroke-width:2.2}}
@keyframes flow{{to{{stroke-dashoffset:-12}}}}@media (prefers-reduced-motion:reduce){{#labmap path.running{{animation:none}}}}
.tw{{overflow-x:auto}}table.road td:first-child{{min-width:170px}}.st{{display:inline-block;font-size:12px;padding:1px 8px;border-radius:9px;background:var(--nonebg);color:var(--none);white-space:nowrap}}
</style></head><body data-repo="{E(REPO)}"><main>
<h1>zero-trust-lab · live evidence</h1>
<p class="lede">A Zero Trust access model on a real home network, built in the open.
Every status below was read from GitHub Actions when this page was built, and links to
the run that produced it. None of them is typed by hand. A check older than its schedule
turns amber on its own.</p>
<p class="built">Built <time data-stale-hours="30" datetime="{E(built)}">{E(built)}</time> ·
<a href="{SERVER}/{REPO}">repository</a> · <a href="{blob}/STATUS.md">status and plan</a> ·
<a href="{blob}/docs/02-decisions.md">decision log</a></p>

<div class="brief">
<div><h3>The one number</h3><p class="big">{routes_n} of ~{home.get("total_about")}</p>
<p>devices in the house are reachable from the network overlay — each by one grant, on one port
({routes_note}). Everything else is refused by default.</p></div>
<div><h3>Live, checked daily</h3><p>The policy in force equals <code>main</code>. {pol['accept'] + pol['deny']} policy
assertions — {pol['deny']} of them refusals — run against the live network. CI holds no stored key for
the network or the cloud.</p><p>Measured once, not counted: after a 15-minute link loss the telemetry path came
back in 11 s with no hands; the readings sent meanwhile were lost, not queued.</p></div>
<div><h3>Not built, and why</h3><p>Field units: deferred — the house's sensors cannot run a
client, and the cloud host that would run simulated ones serves two projects. Device-management posture
and multi-user sign-in: a paid tier ($8/user/mo) and one user. Just-in-time access and log streaming:
$18/user/mo. The before-and-after exposure reading: missed, and <a href="{blob}/STATUS.md">stated</a>, not reconstructed.</p></div>
<div><h3>Read with care</h3><p>Posture on this plan is <strong>reported by the client itself</strong>: it shows how a
device is configured, not that it is intact. The break-glass path into production — the cloud
provider's console — exists but has not yet been exercised (D-042).</p></div>
</div>

<section class="now" aria-live="polite"><div class="nowhead"><h2>Now</h2>
<button id="now-refresh" type="button">Refresh</button></div>
<p id="now-meta" class="meta">Reading GitHub…</p>
<div id="now-body"><p class="why">This panel reads GitHub's public Actions API from your browser: what is
running this minute, step by step, and the last runs. Everything else on the page moves forward with it.</p></div>
<noscript><p class="why">Without JavaScript the page shows what was true when it was built.</p></noscript>
</section>

<h2>The lab on one picture</h2>
<p class="why col">Where each part lives, which tool manages it, and who may reach what. Contours
and words are drawn by hand; <strong>every access arrow is parsed from the policy file</strong>,
so the picture cannot show a path the policy does not grant. Counts on the tiles are {agg_note}.</p>
<div class="diagram">{diagram[0]}</div>
{diagram[1]}
<details class="parts col"><summary>What each part is for, and why it is managed the way it is</summary>{diagram[2]}</details>

<div class="col">
<h2>Checked against the live network</h2>
{live}

<h2>Checked on every change</h2>
{every}

<h2>Measured by watching the system</h2>
<p class="why">Not a check that passes or fails: numbers observed while something was
deliberately broken, counted from both ends, and written down once. They change only when
the drill is run again.</p>
{drills}

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

<h2>In the project, not built yet</h2>
<p class="why">What this lab intends and does not have, why, and what each would take.
An item leaves this list when it is built; nothing here is drawn on the diagram as if it existed.
The full plan is in <a href="{blob}/STATUS.md">STATUS.md</a>.</p>
<div class="tw"><table class="why road"><thead><tr><th>What</th><th>State</th><th>Why not yet</th>
<th>What it takes</th><th>Ref</th></tr></thead><tbody>{roadmap}</tbody></table></div>

</div>
<footer class="col">Built by <a href="{blob}/.github/workflows/evidence-page.yml">evidence-page.yml</a>
from <a href="{blob}/scripts/evidence_page.py">evidence_page.py</a>. The job that builds
this page holds no network or cloud credential; it can write to this page and nothing else.</footer>
</main>
<script>
// Fit every tile label inside its tile, whatever font the visitor has.
document.querySelectorAll('#labmap g.tile').forEach(function(g){{var r=g.querySelector('rect');
var edge=+r.getAttribute('x')+(+r.getAttribute('width'))-5;g.querySelectorAll('text').forEach(function(t){{
var fs=parseFloat(getComputedStyle(t).fontSize),b=t.getBBox();while(b.x+b.width>edge&&fs>7.5){{fs-=0.5;
t.style.fontSize=fs+'px';b=t.getBBox();}}}});}});
document.querySelectorAll('.layers input').forEach(function(i){{i.addEventListener('change',function(){{
document.getElementById('labmap').classList.toggle('hide-'+i.dataset.layer,!i.checked);}});}});
(function(){{var now=Date.now();document.querySelectorAll('time[datetime]').forEach(function(t){{
var d=Date.parse(t.getAttribute('datetime'));if(isNaN(d))return;var h=(now-d)/36e5;
var s=h<1?Math.round(h*60)+' min ago':h<48?Math.round(h)+' h ago':Math.round(h/24)+' days ago';
t.textContent=s+' ('+new Date(d).toISOString().slice(0,16).replace('T',' ')+' UTC)';
var lim=parseFloat(t.getAttribute('data-stale-hours'));var c=t.closest('.card');
if(c&&lim&&h>lim&&c.classList.contains('pass')){{c.classList.remove('pass');c.classList.add('stale');c.querySelector('.pill').textContent='stale';}}
}});}})();
</script>
<script src="live.js" defer></script>
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
    agg = tailnet_aggregate()
    home = json.loads((ROOT / "docs" / "home-snapshot.json").read_text())
    diagram = evidence_diagram.render((ROOT / "policy" / "policy.hujson.tmpl").read_text(), agg, home)
    page = render({"live": [(c, w, r, s, *x) for c, w, r, s, *x in live],
                   "every": [(c, w, r, s) for c, w, r, s in every]},
                  policy_figures(), decision_figures(), built, diagram, agg, home)

    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(page)
    (out / ".nojekyll").write_text("")
    (out / "live.js").write_text((ROOT / "scripts" / "evidence_live.js").read_text())
    summary = {c: (None if r is None else r["ok"]) for c, _, r, *_ in live + every}
    summary["_aggregate"] = bool(agg)
    summary["_unplaced_on_diagram"] = diagram[3]
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
