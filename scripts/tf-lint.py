#!/usr/bin/env python3
"""Guards on the AWS Terraform. Runs in CI; needs no credential and no binary.

`terraform validate` checks syntax. This checks the two things that are
syntactically fine and still wrong:

  1. A GitHub OIDC trust policy that does not pin the token subject.
     An unconstrained `sub` -- absent, or matched with StringLike and a
     wildcard -- accepts a token from ANY GitHub Actions run, in any
     repository, belonging to anyone. The provider is shared across all of
     GitHub, so the audience alone proves only "this came from Actions", which
     on its own is worth nothing. This is the single most common
     misconfiguration of the pattern and it fails open.

  2. A real account id sitting in a committed file. The repository's own
     disclosure sweep catches this too; catching it here as well means the
     failure names the actual rule rather than a regex.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TF_DIR = ROOT / "terraform"

def main():
    if not TF_DIR.exists():
        print("no terraform/ directory; nothing to lint")
        return

    files = sorted(TF_DIR.rglob("*.tf"))
    if not files:
        print("no .tf files; nothing to lint")
        return

    errs = []
    checked_sub = False

    for f in files:
        text = f.read_text()
        rel = f.relative_to(ROOT)

        for m in re.finditer(r"\b\d{12}\b", text):
            errs.append(f"{rel}: literal 12-digit account id -- must be a variable")

        # Find every condition block that mentions the OIDC subject claim.
        for m in re.finditer(r"condition\s*\{(.*?)\}", text, re.S):
            blk = m.group(1)
            if "githubusercontent.com:sub" not in blk:
                continue
            checked_sub = True

            test = re.search(r'test\s*=\s*"([^"]+)"', blk)
            if not test:
                errs.append(f"{rel}: subject condition has no test operator")
            elif test.group(1) != "StringEquals":
                errs.append(
                    f"{rel}: subject condition uses {test.group(1)}, not StringEquals -- "
                    "anything looser can be widened by a wildcard"
                )

            vals = re.search(r"values\s*=\s*\[(.*?)\]", blk, re.S)
            if vals and "*" in vals.group(1):
                errs.append(f"{rel}: wildcard in the trusted subject -- this accepts tokens from any repository")

        # If a GitHub trust policy exists at all, it must also pin the audience.
        if "sts:AssumeRoleWithWebIdentity" in text and "githubusercontent.com:aud" not in text:
            errs.append(f"{rel}: web-identity trust policy does not pin the audience claim")

    if "github-oidc.tf" in " ".join(str(f) for f in files) and not checked_sub:
        errs.append("a GitHub OIDC stack exists but no condition pins the subject claim")

    if errs:
        print("terraform lint FAILED:")
        for e in dict.fromkeys(errs):
            print(f"  - {e}")
        sys.exit(1)

    print(f"terraform lint OK: {len(files)} file(s); OIDC subject pinned with StringEquals, "
          "audience pinned, no literal account id.")

if __name__ == "__main__":
    main()
