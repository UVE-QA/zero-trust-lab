# Runbook — lost comms

**Purpose.** Measure what happens to the telemetry stream when a link is lost,
and what comes back without hands.

**Status:** executed once, collector side, 2026-09-11, and re-run every 30
days on the same cadence as the other drills. The household side (the hub
losing its link) is Phase 6 and has not been run.

---

## What was cut, and why this side first

The stream runs one way: the automation hub pushes one reading to the
collector on every change of an outdoor temperature and on a five-minute tick
(D-049). The drill cut the **collector's** link. That side is a lab machine
outside the house, so the drill could run without asking anything of the
household; the only effect inside the house was a failed call in the hub's log
per attempt.

The cut is a firewall rule on the collector container's own network interface,
inside its own namespace: a link loss, not an administrative shutdown. The
tailnet client stays up and has to find its own way back when the rule goes.
[`collector/drill-lost-comms.sh`](../../collector/drill-lost-comms.sh) cuts,
waits, restores, and records the timeline; a trap removes the rule however it
ends.

## Observed

| | time (UTC) | |
|---|---|---|
| last reading before the cut | 00:00:40.16 | |
| link cut | 00:00:49.8 | |
| link restored | 00:15:59.0 | outage 15 min 9 s |
| tailnet path to the hub back | 00:16:10.4 | **11 s after restore, unattended** |
| first reading after | 00:20:00.8 | the next scheduled tick |

**Readings lost: 7 of 7.** The hub attempted seven pushes during the outage —
three scheduled ticks and four value changes — and logged each as a timeout.
The collector received none of them, and none arrived later. The first reading
after the restore is a fresh one taken at 00:20, not a backlog. The two counts
were taken independently — the hub's from its own log by the session that
manages the house, the collector's from its arrival file — and agree exactly.

**Nothing buffered, nothing replayed.** The hub does not queue a failed push.
This is the design as built, not a fault: the stream is "the latest reading",
and a missed one is gone.

**Hands needed: none.** The tailnet path re-established itself, the receiver
kept running throughout, and the hub resumed on its next trigger.

## What the numbers mean, and do not

- **11 s is the network's recovery**; the four minutes to the first reading
  after it are the sender's schedule. With nothing to send until 00:20, the
  stream could not show its recovery sooner. A shorter tick would show a
  shorter gap and cost more calls; the trade is recorded, not changed.
- **Data gap at the collector: 19 min 20 s** for a 15-minute outage — the
  outage plus the time to the next reading on each side of it.
- The house did not notice. Each failed attempt held the lab's automation for
  about 5.9 s (the 5 s timeout plus overhead); attempts never overlapped, and
  nothing else in the house waits on it. The hub logs each failure at **ERROR**
  level, not warning: `continue_on_error` keeps the run alive but does not lower
  the log level.
- The hub keeps only its last five run traces per automation, so for any
  longer drill its **log**, not its traces, is the count.

## Not tested here

- **The node restarting instead of the link dropping.** The receiver shares the
  node container's network namespace; if that container restarts, the receiver
  must be restarted after it ([collector/README.md](../../collector/README.md)).
  That would need hands, and this drill did not exercise it.
- **The hub losing its link, or the control plane being unreachable.** That is
  the household-side drill of Phase 6: what keeps working in the house, and
  whether remote access comes back on its own.
- **Buffering.** Making the stream survive an outage — a queue on the hub, or
  retained messages on a local broker — would turn "7 lost" into "7 late". Not
  built: the house's broker is shared, and its access control is not enforced
  (D-048).

## Re-run

```bash
CUT=900 nohup ~/zt-collector/drill-lost-comms.sh > ~/zt-collector/drill.out 2>&1 &
```

Then ask the session that manages the house for the hub's failed-push count
and times over the same window, and set them against the collector's arrivals.
