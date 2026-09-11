// The page's live layer. The page itself is built by CI and states what was
// true when it was built; this script keeps it current in the visitor's
// browser by reading GitHub's public Actions API -- the same record the
// build reads, with no token. It can only read: nothing here starts, stops
// or changes anything.
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
    return '<p class="why">Nothing is running. Checks run on a daily schedule and on every change; ' +
      'this panel reads GitHub every ' + IDLE / 60 + ' minutes while the page is open.</p><ul class="recent">' +
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
      el.classList.toggle("running", !!on[el.getAttribute("data-wf")]);
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
    meta.textContent = (err ? "GitHub not reachable: " + err + " · " : "") +
      (lastRead ? "read from GitHub " + lastRead.toLocaleTimeString() : "not read yet") +
      (budget !== null ? " · budget: " + budget + " of 60 requests left this hour" : "") +
      (next ? " · next read in " + Math.round(next) + " s" : "");
  }
  function schedule(sec, err) {
    clearTimeout(timer);
    if (budget !== null && budget < FLOOR && resetAt) sec = Math.max(sec, (resetAt - Date.now()) / 1000 + 5);
    showMeta(sec, err);
    timer = setTimeout(poll, sec * 1000);
  }
  function poll() {
    if (document.hidden) { schedule(IDLE); return; }
    get("/actions/runs?per_page=30").then(function (d) {
      lastRead = new Date();
      var runs = d.workflow_runs || [];
      var active = runs.filter(function (r) { return r.status !== "completed"; }).slice(0, 2);
      return Promise.all(active.map(function (r) {
        return jobs(r).then(function (js) { return { run: r, jobs: js }; });
      })).then(function (running) {
        body.innerHTML = running.length ? renderRunning(running) : renderRecent(runs);
        light(running);
        return updateCards(runs).then(function () {
          ages();
          schedule(running.length ? ACTIVE : IDLE);
        });
      });
    }).catch(function (e) { schedule(IDLE, e.message); });
  }

  var btn = document.getElementById("now-refresh");
  if (btn) btn.addEventListener("click", function () { clearTimeout(timer); poll(); });
  document.addEventListener("visibilitychange", function () { if (!document.hidden) { clearTimeout(timer); poll(); } });
  poll();
})();
