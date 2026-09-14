# Runbook — changing the policy in force

**Purpose.** The tailnet policy is edited in a repository and applied by a
person in a console. Six changes went through this in one evening; this is the
order, and the two places where it can go quietly wrong.

---

## The order

1. **Branch, edit the template, render locally.** `scripts/render-policy.py`
   prints the SHA-256 of the rendered file. Note it: it is the check for step 4.
2. **Open a PR.** CI renders from environment secrets and asks the live tailnet
   to evaluate the policy's own tests, including every `must be refused`
   assertion. It cannot apply anything; there is no write credential in CI.
3. **Merge.** From this moment until step 4 the drift check is *correctly* red:
   `main` is not what is in force. That window is the honest cost of a person
   applying, and it is measured in minutes.
4. **Apply in the console, hash-checked.** Paste the staged edit, confirm the
   editor's content hashes to the render from step 1, then save. Refuse to save
   on any mismatch: the console stores the file verbatim, so a difference is
   real. It does reformat two things (long one-line arrays, and aligned padding
   inside an object containing a nested map — D-051, D-060); when that happens,
   match the console's spelling in the template rather than arguing with it.
5. **Re-run the drift check** rather than waiting for the daily schedule:
   comment `run the checks` on the pinned issue, or re-run the workflow. The
   evidence page reads the *last* run of that workflow, so until it re-runs the
   page shows the failure from the window in step 3 — true when it was recorded,
   misleading an hour later.
6. **Verify the page.** The tile counts and the arrows are parsed from the
   policy; if the picture did not change, the change did not reach it.

## Why the apply is not automated

The apply role for the cloud is gated behind a reviewed environment; the tailnet
has no write credential in CI at all. A person is the gate (D-041). The cost is
step 3's window and a few minutes of attention; the benefit is that nothing can
change the network without someone deciding to.

## Rolling back

The console keeps previous versions of the policy file. A rollback is the same
procedure with the previous render as the target hash — and then a revert PR, so
that `main` and the network agree again. Do not leave the two disagreeing: the
drift check will keep saying so, and a check people learn to ignore is worse
than no check.
