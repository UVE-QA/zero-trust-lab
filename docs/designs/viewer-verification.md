# Design — what a stranger can check, and what they must take on trust

**Question.** The evidence page states numbers about a network nobody else can
see. What can a visitor verify without an account, what could they be allowed
to *run*, and what would that cost the household?

**Status:** the read-only half is built (D-062). Of the two ways of letting a
visitor trigger something, the owner chose **B**, which is built (D-063); **C**
remains specified and unbuilt, because it would put the first create-capable
credential into CI.

---

## Three kinds of claim, kept apart

The page used to blend them, which is the usual way a portfolio quietly
overstates itself.

**1. What the visitor can compute.** The policy template is public. Its
SHA-256, fetched from GitHub and hashed in the visitor's own browser, either
matches the hash built into the page or it does not. Same for the page's own
provenance: the build workflow's run says which commit it came from, and that
commit is the one whose file was just hashed. No trust in me is required for
either, only in GitHub serving the same bytes to everyone.

**2. What GitHub attests.** That a job ran, when, with what conclusion, and
what its log says. The tailnet comparison lives here: a job renders the
template with values held as secrets, asks the tailnet for the policy actually
in force, and compares byte for byte. A visitor reads the workflow file to see
what it does and the run to see that it passed. They are trusting GitHub's
record of a job they can read — not my summary of it — while still not seeing
the network.

**3. What only the owner can attest.** The drill numbers: seconds from a click
to a refused connection, destinations reachable and not, a device cut off from
the control plane. These were measured on a private network. Repeating them
needs access to the tailnet, which is the thing being protected. The page says
so plainly, and offers the only honest substitute: every drill links a runbook
with the exact commands, the controls used, and a section naming what it did
not test. A reader can judge the method even when they cannot repeat the run.

## Why the rendered policy's hash is not published

It would prove more than the template's hash, and it cannot be shown. The
render contains the household's real addresses; a hash does not leak them, but
it does let anyone with a guess confirm it. The comparison therefore happens
inside the job where the rendered file exists, and the visitor gets the job's
verdict rather than the digest.

## Letting a visitor run something — options, and their cost

The rule these are judged against: **nothing a stranger can trigger may touch
the home network, and nothing they can trigger may take an input.** A trigger
that accepts a parameter is a trigger that eventually accepts the wrong one.

### A. `workflow_dispatch` — rejected

Needs write access to the repository. Handing that out to see a check run is
absurd; a fork's run would not carry the trust credentials anyway.

### B. A phrase on one pinned issue re-runs the read-only checks — built (D-063)

Anyone with a GitHub account comments a fixed phrase on one pinned issue; a
workflow reacts, re-runs the checks that already run on a schedule, and replies
in the thread with the result and a link to the run.

- **It cannot reach the house.** The job talks to the tailnet control plane and
  nothing else, with a credential minted per run that can only read the policy.
- **It takes no input.** The comment is a trigger, not an argument: the phrase
  matches or the workflow does nothing.
- **Abuse is spam, not exposure.** Mitigated by a concurrency group, a cooldown
  the workflow enforces itself, and the fact that Actions minutes are free on
  public repositories. The worst outcome is a noisy issue thread, which the
  owner can lock.
- **What it buys:** a visitor stops reading a record of runs and watches one
  happen. That is a different quality of evidence for the same underlying job.
- **As built:** [`viewer-check.yml`](../../.github/workflows/viewer-check.yml).
  Gated on the `public-check` label rather than an issue number, so the
  invitation is withdrawn by removing the label. The comment body is passed
  through the environment and compared in the shell, never interpolated into
  one: it is untrusted text from a stranger, and this is the only workflow they
  can reach. Bot comments are ignored, one run at a time, five-minute cooldown
  with an explaining reply.

### C. A nightly probe node that measures the refusals in public

CI joins an **ephemeral, tagged node with no grants at all**, attempts a fixed
list of connections, and publishes the result as a run log and artifact: a
machine-produced "0 of N reachable" instead of my sentence saying so.

- **What it buys:** the deny-by-default claim stops being self-reported. It is
  the single strongest thing this lab could publish.
- **What it costs:** CI would hold a credential that can *add a node*. Today no
  workflow can change anything anywhere, and that property is worth a lot. An
  ephemeral pre-authorised key for a tag with zero grants is a small version of
  that credential, but it is not nothing, and it would have to be scoped,
  rotated and written down as a decision.
- **What it needs before it could run:** target addresses as secrets, output
  reduced to labels, and the disclosure sweep extended over the artifact — the
  same treatment the tailnet aggregate already gets.

### D. A public endpoint on the collector — rejected

Serving live telemetry staleness to visitors would expose when the house is
active. Household privacy outranks a nicer demonstration, and this lab does not
publish camera counts for the same reason.

## Recommendation

Build **B** — it adds no capability that does not already exist on a schedule,
and it converts "here is a record" into "watch it happen". Treat **C** as a
deliberate trade to be decided on its own: a real gain in provable
deny-by-default, paid for with the first write-capable credential in CI.

**Decided 2026-09-13:** B built, C left on the roadmap.
