// The page's live layer. The page itself is built by CI and states what was
// true when it was built; this script keeps it current in the visitor's
// browser. It can only read: nothing here starts, stops or changes anything.
//
// It reads two things, in this order:
//
//   1. runs.json, published beside the page by the same job that built it.
//      Same origin, no quota, no credential, and already true for everything
//      that finished before the build.
//   2. GitHub's public Actions API -- but only when the snapshot has gone
//      stale and the tab is open. The anonymous limit is sixty requests an
//      hour PER ADDRESS, shared with every other tab and site that reads
//      GitHub from there, so a page that polls on every load spends a quota
//      that is not its own (D-070).
//
// Budget: GitHub allows 60 unauthenticated requests an hour per visitor
// address. Idle, this reads once every 3 minutes; while a run is in flight,
// every 30 seconds; never while the tab is hidden; and it backs off to the
// reset time when fewer than 8 requests are left.
(function () {
  "use strict";
  var REPO = document.body.getAttribute("data-repo");
  var API = "https://api.github.com/repos/" + REPO;
  var IDLE = 180, ACTIVE = 30, FLOOR = 8;
  var MAIN_EVENTS = { push: 1, schedule: 1, workflow_dispatch: 1, workflow_run: 1 };
  var jobsCache = {};
  var budget = null, resetAt = null, timer = null, lastRead = null;
  var snapAt = null, fromSnapshot = false;
  var meta = document.getElementById("now-meta");
  var body = document.getElementById("now-body");
  if (!REPO || !body) return;

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function age(iso) {
    var d = Date.parse(iso);
    if (isNaN(d)) return "";
    var s = (Date.now() - d) / 1000;
    if (s < 90) return Math.round(s) + " s ago";
    var h = s / 3600;
    return h < 1 ? Math.round(s / 60) + " min ago" : h < 48 ? Math.round(h) + " h ago" : Math.round(h / 24) + " days ago";
  }
  function dur(a, b) {
    var s = Math.max(0, ((b ? Date.parse(b) : Date.now()) - Date.parse(a)) / 1000);
    return s < 60 ? Math.round(s) + "s" : Math.floor(s / 60) + "m " + Math.round(s % 60) + "s";
  }
  function wfFile(run) { return (run.path || "").split("/").pop(); }

  function get(path) {
    return fetch(API + path, { headers: { Accept: "application/vnd.github+json" } }).then(function (r) {
      var rem = r.headers.get("x-ratelimit-remaining"), rst = r.headers.get("x-ratelimit-reset");
      if (rem !== null) budget = +rem;
      if (rst !== null) resetAt = +rst * 1000;
      if (!r.ok) throw new Error("GitHub answered " + r.status);
      return r.json();
    });
  }
  function jobs(run) {
    var fresh = run.status === "completed" && jobsCache[run.id];
    if (fresh) return Promise.resolve(fresh);
    return get("/actions/runs/" + run.id + "/jobs?per_page=50").then(function (j) {
      if (run.status === "completed") jobsCache[run.id] = j.jobs || [];
      return j.jobs || [];
    });
  }

  // --- "verify this yourself" ---------------------------------------------
  // Four checks, run once, in the visitor's browser. Each says what it proves
  // and, where it matters, what it does not: the point of the section is that
  // a stranger should not have to take this page's word, and should be told
  // plainly where taking someone's word is unavoidable (D-062).
  var vBox = document.querySelector(".verify");
  var vList = document.getElementById("verify-body");

  function vRow(state, claim, sub) {
    var mark = state === "ok" ? "\u2713" : state === "no" ? "\u2717" : "\u2026";
    return '<li><span class="vs ' + state + '">' + mark + "</span> " + claim +
           (sub ? '<span class="sub">' + sub + "</span>" : "") + "</li>";
  }
  function sha256(buf) {
    return crypto.subtle.digest("SHA-256", buf).then(function (h) {
      return Array.prototype.map.call(new Uint8Array(h), function (b) {
        return ("0" + b.toString(16)).slice(-2);
      }).join("");
    });
  }
  var verified = false;
  function verify(runs) {
    // runs === null means the panel could not read GitHub at all -- usually a
    // visitor's own hourly quota. The hash check below does not touch the API
    // and still runs; the two rows that need the list say why they cannot, and
    // point at the public history. Leaving them on "Reading GitHub..." for ever
    // was the bug this fixes (D-065).
    if (verified || !vBox || !vList || !window.crypto || !crypto.subtle) return;
    verified = true;
    runs = runs || [];
    var want = vBox.getAttribute("data-tmpl-sha");
    var path = vBox.getAttribute("data-tmpl-path");
    var at = vBox.getAttribute("data-build-sha") || "main";
    var rows = [];
    function draw() { vList.innerHTML = rows.join(""); }

    fetch("https://raw.githubusercontent.com/" + REPO + "/" + at + "/" + path)
      .then(function (r) { if (!r.ok) throw new Error("GitHub answered " + r.status); return r.arrayBuffer(); })
      .then(sha256)
      .then(function (got) {
        rows[0] = got === want
          ? vRow("ok", "The policy this page describes is the file in the repository.",
                 "SHA-256 of <code>" + esc(path) + "</code>, fetched from GitHub and hashed here, matches the hash built into this page: <code>" + esc(got.slice(0, 16)) + "\u2026</code>")
          : vRow("no", "The policy file does not match the hash this page was built with.",
                 "Fetched <code>" + esc(got.slice(0, 16)) + "\u2026</code>, expected <code>" + esc(String(want).slice(0, 16)) + "\u2026</code>. Treat every claim below it as unverified.");
        draw();
      })
      .catch(function (e) { rows[0] = vRow("wait", "Could not fetch the policy file to hash it.", esc(e.message)); draw(); });

    // Both rows below are read out of the list the Now panel already fetched.
    // Asking GitHub separately cost two requests of a visitor's sixty an hour,
    // for answers that were already on this page (D-065).
    Promise.resolve().then(function () {
      var run = runs.filter(function (r) { return wfFile(r) === "evidence-page.yml" && r.conclusion === "success"; })[0];
      if (!run) throw new Error(runs.length ? "no successful build in the last runs read" : "the runs list could not be read from here");
      var same = run.head_sha && run.head_sha.slice(0, 7) === at.slice(0, 7);
      rows[1] = vRow(same ? "ok" : "wait",
        same ? "This page was built by GitHub Actions from that commit."
             : "This page is not the newest build.",
        (same ? "Run " : "The newest successful build is ") + '<a href="' + esc(run.html_url) + '">#' + run.run_number +
        "</a>, " + esc(age(run.created_at)) + ", from <code>" + esc((run.head_sha || "").slice(0, 7)) +
        "</code>. Nobody uploads this page by hand: the workflow that publishes it holds no network or cloud credential." +
        (fromSnapshot ? ' Read from the snapshot this page ships with \u2014 for a read that owes this page nothing, <a href="https://github.com/' + REPO + '/actions">GitHub\u2019s own history</a> is one click away.' : ""));
      draw();
    }).catch(function (e) {
      rows[1] = vRow("wait", runs.length ? "The last build is not among the runs just read."
                                          : "GitHub's run list could not be read from your address just now.",
        esc(e.message) + '. <a href="https://github.com/' + REPO + '/actions/workflows/evidence-page.yml">The build history</a> is public.');
      draw();
    });

    Promise.resolve().then(function () {
      var run = runs.filter(function (r) {
        return wfFile(r) === "tailnet-check.yml" && r.status === "completed" && r.head_branch === "main";
      })[0];
      if (!run) throw new Error(runs.length ? "no completed run among the runs just read" : "the runs list could not be read from here");
      var ok = run.conclusion === "success";
      rows[2] = vRow(ok ? "ok" : "no",
        ok ? "The live network agreed with that policy, and GitHub says so."
           : "The last comparison against the live network did not pass.",
        'Run <a href="' + esc(run.html_url) + '">#' + run.run_number + "</a>, " + esc(age(run.created_at)) +
        ". The job renders the template with values held as secrets, asks the tailnet for the policy actually in force, and compares byte for byte. " +
        "You are trusting GitHub's record of a job you can read, not my summary of it \u2014 but you are not seeing the network itself.");
      draw();
    }).catch(function (e) {
      rows[2] = vRow("wait", runs.length ? "The network check is not among the runs just read."
                                          : "Neither could the network check's last run — same reason, same quota.",
        esc(e.message) + '. <a href="https://github.com/' + REPO + '/actions/workflows/tailnet-check.yml">Its history</a> is public, and it runs daily.');
      draw();
    });

    rows[3] = vRow("ok", "You can make the network check run, now, yourself.",
      'Comment <code class="phrase" title="click to copy">run the checks</code> \u2014 those three words, nothing else \u2014 in ' +
      '<a href="https://github.com/' + REPO + '/issues?q=is%3Aissue+is%3Aopen+label%3Apublic-check">this issue</a>' +
      ", and GitHub re-runs the two checks above and answers in the thread. It takes no argument \u2014 the phrase matches or nothing happens \u2014 " +
      "the credential is minted for that run and can only read the policy, and there is no path from it to the home network. " +
      "Everything else on this page only reads.");
    draw();
  }

  // --- the Now panel -------------------------------------------------------
  function icon(st, c) {
    if (st !== "completed") return st === "in_progress" ? "◐" : "○";
    return c === "success" ? "✓" : c === "skipped" ? "–" : c === "cancelled" ? "⊘" : "✗";
  }
  function renderRunning(list) {
    return list.map(function (x) {
      var r = x.run;
      var js = x.jobs.map(function (j) {
        var steps = j.steps || [];
        var done = steps.filter(function (s) { return s.status === "completed"; }).length;
        var cur = steps.filter(function (s) { return s.status === "in_progress"; })[0];
        return '<li class="job ' + esc(j.status) + " " + esc(j.conclusion || "") + '"><span class="ic">' +
          icon(j.status, j.conclusion) + "</span> " + esc(j.name) +
          ' <span class="meta">' + (j.started_at ? dur(j.started_at, j.completed_at) : "queued") +
          (steps.length ? " · " + done + " of " + steps.length + " steps" : "") +
          (cur ? " · now: " + esc(cur.name) : "") + "</span></li>";
      }).join("");
      return '<div class="run live"><div class="rh"><b>' + esc(r.name) + "</b> " +
        '<span class="meta">' + esc(r.event) + " · " + esc(r.head_branch) + " · <code>" + esc((r.head_sha || "").slice(0, 7)) +
        "</code> · started " + age(r.run_started_at || r.created_at) + '</span> <a href="' + esc(r.html_url) +
        '">open the run →</a></div><ul class="jobs">' + js + "</ul></div>";
    }).join("");
  }
  function renderRecent(runs) {
    return '<p class="why">Nothing is running. Checks run on a daily schedule and on every change. ' +
      (fromSnapshot
        ? "This list came with the page, written by the job that built it \u2014 no request of yours was spent on it. "
        : "This list was just read from GitHub in your browser. ") +
      'While the tab is open the panel refreshes at most every ' + IDLE / 60 + ' minutes.</p><ul class="recent">' +
      runs.slice(0, 6).map(function (r) {
        return '<li><span class="ic ' + esc(r.conclusion) + '">' + icon(r.status, r.conclusion) + "</span> " +
          esc(r.name) + ' <span class="meta">' + esc(r.event) + " · " + esc(r.head_branch) + " · " +
          age(r.updated_at) + '</span> <a href="' + esc(r.html_url) + '">run →</a></li>';
      }).join("") + "</ul>";
  }

  // --- the diagram: light what is running ---------------------------------
  function light(running) {
    var map = document.getElementById("labmap");
    if (!map) return;
    var on = {};
    running.forEach(function (x) { on[wfFile(x.run)] = 1; });
    map.querySelectorAll("[data-wf]").forEach(function (el) {
      // One arrow may be walked by more than one workflow -- the read-only path
      // to the control plane is used by the scheduled check and by the run a
      // visitor starts -- so the attribute is a space-separated list.
      var any = el.getAttribute("data-wf").split(/\s+/).some(function (w) { return on[w]; });
      el.classList.toggle("running", any);
    });
    var gha = document.getElementById("n-gha");
    if (gha) gha.classList.toggle("busy", running.length > 0);
  }

  // --- the cards: move them forward when a newer run has finished ----------
  function updateCards(runs) {
    var cards = document.querySelectorAll(".card[data-wf]");
    var work = [];
    cards.forEach(function (card) {
      var wf = card.getAttribute("data-wf"), have = +card.getAttribute("data-run") || 0;
      var newer = runs.filter(function (r) {
        return wfFile(r) === wf && r.head_branch === "main" && MAIN_EVENTS[r.event] &&
          r.status === "completed" && r.id > have;
      })[0];
      if (!newer) return;
      work.push(jobs(newer).then(function (js) {
        var j = js.filter(function (x) { return x.name === card.getAttribute("data-job"); })[0];
        if (!j || (j.conclusion !== "success" && j.conclusion !== "failure")) return;
        var ok = j.conclusion === "success", t = card.querySelector("time"), a = card.querySelector(".ev a");
        card.setAttribute("data-run", newer.id);
        if (card.hasAttribute("data-need") ) {
          // This claim is stronger than "the job passed": the build reads the
          // log. The browser cannot, so it reports the run and does not flip.
          var n = card.querySelector(".livenote") || card.appendChild(document.createElement("p"));
          n.className = "ev livenote";
          n.innerHTML = "A newer run finished " + age(j.completed_at) + " (" + esc(j.conclusion) +
            '); its log is read when the page is rebuilt. <a href="' + esc(j.html_url) + '">open it →</a>';
          return;
        }
        card.classList.remove("pass", "fail", "stale", "none");
        card.classList.add(ok ? "pass" : "fail");
        card.querySelector(".pill").textContent = ok ? "pass" : "fail";
        if (t) { t.setAttribute("datetime", j.completed_at); }
        if (a) { a.href = j.html_url; }
        var sha = card.querySelector(".ev code");
        if (sha) sha.textContent = (newer.head_sha || "").slice(0, 7);
        card.classList.add("updated");
      }));
    });
    return Promise.all(work);
  }
  function ages() {
    document.querySelectorAll("time[datetime]").forEach(function (t) {
      var d = Date.parse(t.getAttribute("datetime"));
      if (isNaN(d)) return;
      var h = (Date.now() - d) / 36e5;
      t.textContent = age(t.getAttribute("datetime")) + " (" + new Date(d).toISOString().slice(0, 16).replace("T", " ") + " UTC)";
      var lim = parseFloat(t.getAttribute("data-stale-hours")), c = t.closest(".card");
      if (c && lim && h > lim && c.classList.contains("pass")) {
        c.classList.remove("pass"); c.classList.add("stale"); c.querySelector(".pill").textContent = "stale";
      }
    });
  }

  function showMeta(next, err) {
    if (!meta) return;
    // GitHub allows 60 unauthenticated requests an hour PER ADDRESS, shared with
    // everything else the visitor does. Running out is their quota, not this
    // lab failing, and saying "GitHub not reachable" invited exactly the wrong
    // conclusion (D-065).
    var spent = budget === 0 && err && /\b(403|429)\b/.test(err);
    meta.textContent = (spent
        ? "GitHub's anonymous limit for your address is used up — 60 requests an hour, shared with anything else you do from here, not with this page. What you see below is what was true when the page was built · "
        : err ? "GitHub not reachable: " + err + " · " : "") +
      (lastRead ? "read from GitHub " + lastRead.toLocaleTimeString()
        : snapAt ? "showing the snapshot this page was built with, " + age(new Date(snapAt).toISOString())
        : spent ? "waiting for the limit to reset" : "not read yet") +
      (budget !== null ? " · budget: " + budget + " of 60 requests left this hour" : "") +
      (next ? " · next read in " + Math.round(next) + " s" : "");
  }
  function schedule(sec, err) {
    clearTimeout(timer);
    if (budget !== null && budget < FLOOR && resetAt) sec = Math.max(sec, (resetAt - Date.now()) / 1000 + 5);
    showMeta(sec, err);
    timer = setTimeout(poll, sec * 1000);
  }
  function draw(runs, running) {
    body.innerHTML = running.length ? renderRunning(running) : renderRecent(runs);
    light(running);
    verify(runs);
    return updateCards(runs).then(ages);
  }

  // The snapshot published with the page. Free, same origin, and enough for
  // every visitor who arrives between runs -- which is nearly all of them.
  function readSnapshot() {
    return fetch("runs.json").then(function (r) {
      if (!r.ok) throw new Error("no snapshot (" + r.status + ")");
      return r.json();
    }).then(function (snap) {
      var runs = snap.runs || [];
      if (!runs.length) throw new Error("snapshot is empty");
      snapAt = Date.parse(snap.generated_at);
      fromSnapshot = true;
      var running = runs.filter(function (r) { return r.status !== "completed"; }).slice(0, 2)
        .map(function (r) { return { run: r, jobs: (snap.jobs || {})[String(r.id)] || [] }; });
      return draw(runs, running).then(function () {
        // Ask GitHub only for what the snapshot cannot know: what has happened
        // since it was written.
        var age = (Date.now() - snapAt) / 1000;
        schedule(Math.max(5, IDLE - age));
      });
    }).catch(function () { poll(); });
  }

  function poll() {
    if (document.hidden) { schedule(IDLE); return; }
    get("/actions/runs?per_page=30").then(function (d) {
      lastRead = new Date();
      fromSnapshot = false;
      var runs = d.workflow_runs || [];
      var active = runs.filter(function (r) { return r.status !== "completed"; }).slice(0, 2);
      return Promise.all(active.map(function (r) {
        return jobs(r).then(function (js) { return { run: r, jobs: js }; });
      })).then(function (running) {
        return draw(runs, running).then(function () {
          schedule(running.length ? ACTIVE : IDLE);
        });
      });
    }).catch(function (e) { verify(null); schedule(IDLE, e.message); });
  }

  // The phrase is the whole interface a stranger has, so it should be as easy
  // to take as it is to read: one click copies it. Falls back to selecting the
  // text, which the CSS already makes a single click's work.
  document.addEventListener("click", function (e) {
    var el = e.target && e.target.closest && e.target.closest(".phrase");
    if (!el) return;
    var text = el.textContent.trim();
    var flash = function (what) {
      el.classList.add("copied");
      var was = el.getAttribute("title");
      el.setAttribute("title", what);
      el.setAttribute("data-said", what);
      setTimeout(function () {
        el.classList.remove("copied");
        el.removeAttribute("data-said");
        el.setAttribute("title", was && was !== what ? was : "click to copy");
      }, 1600);
    };
    var select = function () {
      // Clipboard access is refused in plenty of ordinary situations -- an
      // unfocused tab, a browser that asks first. Say what happened rather
      // than flashing "copied" over a clipboard that never changed.
      try {
        var r = document.createRange(); r.selectNodeContents(el);
        var sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(r);
      } catch (err) { /* the CSS selects it on click anyway */ }
      flash("selected \u2014 press \u2318C");
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { flash("copied"); }, select);
    } else {
      select();
    }
  });

  var btn = document.getElementById("now-refresh");
  if (btn) btn.addEventListener("click", function () { clearTimeout(timer); poll(); });
  document.addEventListener("visibilitychange", function () { if (!document.hidden) { clearTimeout(timer); poll(); } });
  readSnapshot();
})();
