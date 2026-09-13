#!/bin/sh
# Queue one command for the house to ask about (docs/designs/mobile-unit.md).
#
# This does not command anything. It leaves a name where the hub will find it
# the next time the hub asks; the hub decides whether that name means anything
# and whether its own guards allow it. Run on the collector's host.
#
#   ./ask.sh pet_area_light      # queue
#   ./ask.sh --clear             # withdraw whatever is queued
#
# One command at a time: queueing replaces whatever was waiting.
set -eu
VOL=${VOL:-zt-collector-data}
if [ "${1:-}" = "--clear" ]; then
  docker run --rm -v "$VOL":/data alpine:3 rm -f /data/command.json
  echo "queue cleared"
  exit 0
fi
[ $# -eq 1 ] || { echo "usage: ask.sh <command-name> | --clear" >&2; exit 2; }
ID=$(date -u +%Y%m%dT%H%M%SZ)
printf '{"command":"%s","id":"%s","queued_at":"%s"}' "$1" "$ID" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  | docker run --rm -i -v "$VOL":/data alpine:3 sh -c 'cat > /data/command.json && chown 65534:65534 /data/command.json'
echo "queued $1 (id $ID) — the hub takes it on its next ask, or nobody does"
