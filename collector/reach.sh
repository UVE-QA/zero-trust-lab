#!/bin/sh
# What can this node reach right now? One TCP connection per destination,
# four seconds each, nothing sent. Run inside a node's network namespace.
#
# Destinations are NOT in this repository: this file may not carry a real
# address (that is what the disclosure sweep enforces). Pass them in, one per
# line, as "label host port" -- from a local file the operator keeps:
#
#   docker run --rm --network container:<node> \
#     -v "$PWD/reach.sh:/m.sh:ro" -v "$HOME/targets:/t:ro" alpine:3 sh /m.sh /t
#
# A missing file is not silence: the script says so and exits non-zero.
set -u
F="${1:-${REACH_TARGETS:-}}"
[ -n "$F" ] && [ -r "$F" ] || { echo "reach.sh: give it a targets file: label host port per line" >&2; exit 2; }
while read -r label host port; do
  case "$label" in ""|\#*) continue ;; esac
  if nc -z -w 4 "$host" "$port" 2>/dev/null; then r=open; else r=refused; fi
  printf '%s %-22s %s\n' "$(date -u +%H:%M:%S)" "$label" "$r"
done < "$F"
