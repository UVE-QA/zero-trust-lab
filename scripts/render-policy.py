#!/usr/bin/env python3
"""Render policy/policy.hujson.tmpl into an applyable policy file.

The template is the source of truth and is committed. The rendered output
contains real addresses and is gitignored -- it exists only to be applied.

    ./scripts/render-policy.py                 # -> policy/.rendered/policy.hujson
    ./scripts/render-policy.py --check         # verify placeholders resolve, write nothing
    ./scripts/render-policy.py --stdout        # print, do not write

Values come from local/inventory.yaml, which never leaves the machine. The
mapping is deliberately explicit rather than clever: a policy is not the place
for a lookup you cannot read.
"""
import argparse
import hashlib
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "policy" / "policy.hujson.tmpl"
OUT_DIR = ROOT / "policy" / ".rendered"
OUT = OUT_DIR / "policy.hujson"
INVENTORY = ROOT / "local" / "inventory.yaml"

# placeholder -> the inventory key whose lan_address supplies it.
# Explicit so that adding an exposed device is a visible, reviewable edit
# rather than a silent consequence of the inventory changing.
MAPPING = {
    "camera_stream":    ("lan_observed", "camera exposed for the stream tier"),
    "actuator_granted": ("socket_qualification", "granted actuator"),
    "actuator_control": ("socket_qualification", "denied control"),
}

IPV4 = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")


def load_values():
    """Pull the exposed-host addresses out of the private inventory.

    Deliberately reads a small, named block rather than parsing the whole
    inventory: the renderer should fail loudly if that block is missing, not
    quietly pick up something that happens to look like an address.
    """
    if not INVENTORY.exists():
        sys.exit(f"error: {INVENTORY} not found. It is gitignored by design -- "
                 "this script cannot run from a fresh clone without it.")
    text = INVENTORY.read_text()
    block = re.search(r"^exposed_hosts:\s*$(.*?)(?=^\S|\Z)", text, re.M | re.S)
    if not block:
        sys.exit("error: local/inventory.yaml has no `exposed_hosts:` block.\n"
                 "Add one mapping each placeholder to an address, e.g.\n"
                 "  exposed_hosts:\n"
                 "    camera_stream: <address>\n")
    values = {}
    for line in block.group(1).splitlines():
        m = re.match(r"\s+([a-z_]+):\s*([0-9.]+)\s*(?:#.*)?$", line)
        if m:
            values[m.group(1)] = m.group(2)
    return values


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify only, write nothing")
    ap.add_argument("--stdout", action="store_true", help="print instead of writing")
    args = ap.parse_args()

    tmpl = TEMPLATE.read_text()
    needed = set(re.findall(r"\{\{\s*([a-z_]+)\s*\}\}", tmpl))
    values = load_values()

    missing = sorted(needed - values.keys())
    if missing:
        sys.exit("error: no value for placeholder(s): " + ", ".join(missing))

    bad = sorted(k for k in needed if not IPV4.match(values[k]))
    if bad:
        sys.exit("error: value is not an IPv4 address for: " + ", ".join(bad))

    unused = sorted(values.keys() - needed)
    if unused:
        print(f"note: inventory defines unused exposed_hosts: {', '.join(unused)}",
              file=sys.stderr)

    out = tmpl
    for k in needed:
        out = re.sub(r"\{\{\s*" + k + r"\s*\}\}", values[k], out)

    # The rendered file must not be mistaken for the source. Replace the whole
    # template header in one go: matching it line by line is brittle, and a
    # partial match leaves an incoherent header on the file being applied.
    header_start = "// Tailnet policy \u2014 SOURCE OF TRUTH."
    header_end = "// system, and roles are what the model is about."
    i, j = out.find(header_start), out.find(header_end)
    if i == -1 or j == -1:
        sys.exit("error: template header not found -- refusing to emit a file "
                 "that does not say it is generated")
    out = out[:i] + (
        "// Tailnet policy -- RENDERED OUTPUT, not the source.\n"
        "//\n"
        "// GENERATED FILE -- DO NOT EDIT.\n"
        "//\n"
        "// Rendered by scripts/render-policy.py from policy/policy.hujson.tmpl.\n"
        "// Contains real addresses and is gitignored. Edits belong in the\n"
        "// template; anything changed here is lost on the next render.\n"
        "//\n"
        "// Everything except the `hosts` block is expressed in roles, which is\n"
        "// the point: a tag is a role in the system, and roles are what the\n"
        "// model is about."
    ) + out[j + len(header_end):]

    if "{{" in out:
        sys.exit("error: unresolved placeholder remains after rendering")

    digest = hashlib.sha256(out.encode()).hexdigest()

    if args.stdout:
        print(out)
        return
    if args.check:
        print(f"OK: {len(needed)} placeholder(s) resolve. "
              f"Rendered size {len(out)} bytes, sha256 {digest}")
        return

    OUT_DIR.mkdir(exist_ok=True)
    OUT.write_text(out)
    print(f"wrote {OUT.relative_to(ROOT)}  ({len(out)} bytes)")
    print(f"sha256 {digest}")
    print("This file is gitignored. Apply it; do not commit it.")


if __name__ == "__main__":
    main()
