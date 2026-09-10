# Runbook — the CI identity for the tailnet

**Purpose.** Let `tailnet-check.yml` validate proposed policies and detect drift,
with no stored Tailscale secret and no ability to change the tailnet.

**Status:** executed 2026-09-10. Proven from both sides: the introducing pull
request passed, and a deliberately broken test failed and named itself.
See D-041 for why it is shaped this way.

---

## What gets created

| where | what | secret? |
|---|---|---|
| Tailscale console | one OpenID Connect trust credential, scope `policy_file:read` (+ two device reads the console forces with it) | no — produces a client ID and an audience, both non-secret |
| GitHub | environment `tailnet-read` | — |
| GitHub, on that environment | secrets `TS_OIDC_CLIENT_ID`, `TS_OIDC_AUDIENCE` | not by Tailscale's definition — held as secrets only so logs mask them |
| GitHub, on that environment | secrets `POLICY_VALUE_CAMERA_STREAM`, `POLICY_VALUE_ACTUATOR_GRANTED`, `POLICY_VALUE_ACTUATOR_CONTROL`, `POLICY_VALUE_OPERATOR_IDENTITY` | yes — the template's real values |

Nothing on this list can write to the tailnet.

---

## Procedure

**1. Create the trust credential**

Console → Settings → Trust credentials → **Credential** → *OpenID Connect*.

- Issuer: **GitHub**
- Subject — exact, no `*`:

  ```
  repo:<owner>@<owner-id>/<repo>@<repo-id>:environment:tailnet-read
  ```

  The numeric ids are the repository's and its owner's. This is the form GitHub
  actually puts in tokens for this repository (measured in Phase 5), so a subject
  written in the shorter name-only form would never match. It also survives a
  rename. `gh api repos/<owner>/<repo> --jq '.owner.id, .id'` prints both.

- Audience: leave empty. The console generates one.
- Custom claims: none needed — the subject already pins owner, repository and
  environment by id.
- Scopes: tick **Policy File → Read** and nothing else. Not `all:read`.

  The console then also ticks, and locks, **Devices → Core → Read** and
  **Devices → Posture Attributes → Read**. They cannot be cleared while the
  policy read is selected, and they clear with it — the validator needs them to
  evaluate tests that name devices or posture. They sit in a collapsed section,
  so expand every section before generating and check the full list: the form
  does not show you what it has added.

Record the client ID and the audience it shows.

A wildcard in the subject is the one mistake here that changes the security
property rather than just breaking the job. A subject ending `/*` would admit any
environment, branch or pull request in the repository — the Tailscale form of
the `StringLike` mistake that `tf-lint.py` refuses on the AWS side.

**2. Create the environment and its values**

```
gh api -X PUT repos/<owner>/<repo>/environments/tailnet-read
gh secret set TS_OIDC_CLIENT_ID --env tailnet-read --body '<client id>'
gh secret set TS_OIDC_AUDIENCE  --env tailnet-read --body '<audience>'
```

The four secrets come from `local/inventory.yaml`'s `policy_values:` block. Set
them from the file, not by pasting — nothing should put these values on a
command line or in shell history.

**3. Prove it, from both sides**

- Run the workflow manually (`workflow_dispatch`). `drift` should pass if the
  tailnet enforces the render of main.
- Open a throwaway pull request that breaks one `accept` test in the template.
  `validate` must fail, with the failure naming the test. A check that has only
  ever been seen passing has not been shown to check anything.

**4. Record it**

The client ID and creation date go in `local/inventory.yaml`. There is no secret
to rotate; revoking the trust credential in the console ends access immediately.

---

## If the exchange is refused

The script prints the `sub` and `aud` the token carried. Compare them with the
credential. Almost every failure is one of:

- the subject in the console is the name-only form, and GitHub sent the id form;
- the job does not declare `environment: tailnet-read`, so the subject ends
  `:pull_request` or `:ref:…` instead;
- `TS_OIDC_AUDIENCE` does not match what the console generated.

Do not fix a mismatch by widening the subject.
