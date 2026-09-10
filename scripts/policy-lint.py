#!/usr/bin/env python3
"""Structural checks on the policy TEMPLATE. Runs in CI, needs no credential.

This is NOT the tailnet's own `tests` section. Those run on apply, evaluate
real reachability, and need an API credential CI does not yet have (Q-003).
This lint catches the mistakes that are visible without evaluating anything --
which happens to include the one rule the design states absolutely:

    "Grants by port, never *:*"

Checks:
  1. No wildcard in any grant's src, dst or ip.
  2. Every tag referenced anywhere is declared in tagOwners.
  3. Every host alias referenced is declared in hosts.
  4. Every grant names at least one port.
  5. Braces and brackets balance.
  6. No literal address outside the hosts block (the leak sweep guards the
     repo; this guards the template's own shape).
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "policy" / "policy.hujson.tmpl"

def strip_comments(s):
    return re.sub(r"//[^\n]*", "", s)

def section(body, name):
    m = re.search(r'"' + name + r'"\s*:\s*([\[{])', body)
    if not m:
        return ""
    open_ch = m.group(1)
    close_ch = "]" if open_ch == "[" else "}"
    i = m.end() - 1
    depth = 0
    for j in range(i, len(body)):
        if body[j] == open_ch:
            depth += 1
        elif body[j] == close_ch:
            depth -= 1
            if depth == 0:
                return body[i:j + 1]
    return ""

def main():
    raw = TEMPLATE.read_text()
    body = strip_comments(raw)
    errs = []

    if body.count("{") != body.count("}"):
        errs.append("braces do not balance")
    if body.count("[") != body.count("]"):
        errs.append("brackets do not balance")

    declared_tags = set(re.findall(r'"(tag:[a-z0-9-]+)"\s*:', section(body, "tagOwners")))
    declared_hosts = set(re.findall(r'"([a-z0-9-]+)"\s*:', section(body, "hosts")))

    grants = section(body, "grants")
    for field in ("src", "dst", "ip"):
        for m in re.finditer(r'"' + field + r'"\s*:\s*\[([^\]]*)\]', grants):
            if '"*"' in m.group(1):
                errs.append(f'wildcard "*" in a grant\'s {field} -- grants are by port, never *:*')

    for m in re.finditer(r"\{([^{}]*)\}", grants):
        blk = m.group(1)
        if '"src"' not in blk:
            continue
        ips = re.search(r'"ip"\s*:\s*\[([^\]]*)\]', blk)
        if not ips or not re.search(r'"\w+:\d+"', ips.group(1)):
            errs.append("a grant does not name a port")

    used_tags = set(re.findall(r'"(tag:[a-z0-9-]+)', body))
    for t in sorted(used_tags - declared_tags):
        errs.append(f"tag referenced but not declared in tagOwners: {t}")

    scope = grants + section(body, "tests")
    used_hosts = set()
    for m in re.finditer(r'"([a-z][a-z0-9-]*)(?::\d+)?"', scope):
        name = m.group(1)
        if name in declared_hosts:
            used_hosts.add(name)
    for h in sorted(used_hosts - declared_hosts):
        errs.append(f"host alias referenced but not declared: {h}")

    hosts_block = section(body, "hosts")
    outside = body.replace(hosts_block, "")
    for m in re.finditer(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", outside):
        errs.append(f"literal address outside the hosts block: {m.group(0)}")

    if errs:
        print("policy lint FAILED:")
        for e in errs:
            print(f"  - {e}")
        sys.exit(1)

    print(f"policy lint OK: {len(declared_tags)} tags declared, "
          f"{len(declared_hosts)} host aliases, no wildcards, every grant names a port.")

if __name__ == "__main__":
    main()
