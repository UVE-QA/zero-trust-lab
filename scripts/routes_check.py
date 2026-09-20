#!/usr/bin/env python3
"""Every address a grant names must have an approved route behind it.

A grant is a promise about a destination. When that destination is an address
on the house's own network rather than a node in the tailnet, the promise is
only kept if two separate things hold: some node advertises a route covering
the address, and an administrator approved that route in the console.

The second one lives outside this repository, changes with a click, and its
disappearance makes no noise. That is how the household lost remote access for
two weeks while every check stayed green (D-073, D-074).

    ./scripts/routes_check.py policy/.rendered/policy.hujson routes/routes.json

Fails when a granted address has no approved route. Warns -- loudly, without
failing -- when a route is approved that no grant needs, because a road nobody
is allowed to walk is still a road, and somebody should know it is there.

Reads real addresses and prints none of them -- only prefix lengths and node
names -- because its output lands in a public log.
"""
import ipaddress
import json
import re
import sys


def mask(addr):
    """The prefix length and nothing else.

    This runs in a public repository's logs. The alias name already says which
    device a line is about, so the address adds nothing a reader needs and
    everything a sweep would object to.
    """
    try:
        return "/" + str(ipaddress.ip_network(addr, strict=False).prefixlen)
    except ValueError:
        return "?"


def slice_section(text, name):
    """The policy is HuJSON with comments; take one top-level block as text."""
    start = text.find(f'"{name}"')
    if start < 0:
        return ""
    depth, i = 0, text.find("{", start)
    for j in range(i, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[i:j + 1]
    return ""


def main():
    policy = open(sys.argv[1], encoding="utf-8").read()
    routes = json.load(open(sys.argv[2], encoding="utf-8"))

    # host aliases: name -> address. These are the only addresses a grant can
    # name; everything else is a tag or an identity, which needs no route.
    hosts = dict(re.findall(r'"([\w-]+)":\s*"([0-9a-fA-F.:]+)"', slice_section(policy, "hosts")))
    granted = set(re.findall(r'"dst":\s*\[([^\]]*)\]', policy))
    named = {h for h in hosts if any(f'"{h}"' in g for g in granted)}

    approved = routes.get("approved", {})
    nets = []
    for r in approved:
        try:
            nets.append((ipaddress.ip_network(r, strict=False), r))
        except ValueError:
            pass

    missing, covered = [], []
    for name in sorted(named):
        addr = ipaddress.ip_address(hosts[name])
        hit = [r for net, r in nets if addr in net]
        (covered if hit else missing).append((name, hit))

    used = {r for _, hits in covered for r in hits}
    spare = [r for r in approved if r not in used]

    for name, hit in covered:
        print(f"  ok      {name:18} <- {mask(hit[0])} approved on {', '.join(approved[hit[0]])}")
    for r in spare:
        print(f"  spare   {'(no grant needs it)':18} <- {mask(r)} approved on {', '.join(approved[r])}")
    for r, who in routes.get("advertised_not_approved", {}).items():
        print(f"  offered {'(not approved)':18} <- {mask(r)} advertised by {', '.join(who)}")

    if missing:
        for name, _ in missing:
            print(f"  MISSING {name:18} <- granted, but no approved route covers it", file=sys.stderr)
        print(f"\nFAIL: {len(missing)} granted address(es) with no approved route. A grant that "
              f"names an address is only kept when a route to it is approved, and approval "
              f"changes outside this repository (D-074).", file=sys.stderr)
        return 1
    print(f"\nOK: {len(covered)} granted address(es), each behind an approved route; "
          f"{len(spare)} approved route(s) no grant needs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
