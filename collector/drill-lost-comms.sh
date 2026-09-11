#!/usr/bin/env bash
# Lost-comms drill, collector side (docs/runbooks/lost-comms.md).
#
# Cuts the collector container's underlay (eth0) for CUT seconds, restores
# it, and records when the path and the readings come back. The rules live
# only in the container's namespace, so the host and its SSH are untouched,
# and the trap removes them however this script ends.
set -u
CUT=${CUT:-900}
C=zt-collector-ts
OUT=$HOME/zt-collector/drill-$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$OUT"
now() { date -u +%Y-%m-%dT%H:%M:%S.%3NZ; }
log() { echo "$(now) $*" | tee -a "$OUT/timeline.log"; }
rules() { docker exec $C sh -c "iptables $1 INPUT -i eth0 -j DROP; iptables $1 OUTPUT -o eth0 -j DROP"; }
restore() { rules -D 2>/dev/null; while docker exec $C iptables -C INPUT -i eth0 -j DROP 2>/dev/null; do rules -D; done; }
trap 'restore; log "trap: rules removed"' EXIT
hub_hs() { docker exec $C tailscale status --json 2>/dev/null | python3 -c '
import json,sys
d=json.load(sys.stdin)
for p in d.get("Peer",{}).values():
    if "tag:gateway-home" in (p.get("Tags") or []):
        print(p.get("LastHandshake",""), "active" if p.get("Active") else "idle", p.get("CurAddr") or p.get("Relay") or "-")'; }
readings() { docker run --rm -v zt-collector-data:/data:ro alpine:3 cat /data/readings.jsonl; }

readings > "$OUT/readings-before.jsonl"
log "baseline: $(wc -l < "$OUT/readings-before.jsonl") readings; hub peer: $(hub_hs)"
rules -I
log "CUT: underlay dropped (INPUT/OUTPUT on eth0)"
end=$(( $(date +%s) + CUT ))
while [ "$(date +%s)" -lt "$end" ]; do
  echo "$(now) $(hub_hs)" >> "$OUT/peer.log"; sleep 10
done
restore
T_RESTORE=$(date +%s)
log "RESTORE: rules removed"
# Path back: a handshake with the hub newer than the restore.
for i in $(seq 1 180); do
  hs=$(hub_hs); echo "$(now) $hs" >> "$OUT/peer.log"
  hs_s=$(date -d "$(echo "$hs" | cut -d' ' -f1)" +%s 2>/dev/null || echo 0)
  if [ "$hs_s" -ge "$T_RESTORE" ]; then log "PATH: handshake with hub after restore: $hs"; break; fi
  sleep 2
done
# First reading after the restore.
n0=$(wc -l < "$OUT/readings-before.jsonl")
for i in $(seq 1 90); do
  readings > "$OUT/readings-after.jsonl"
  if [ "$(wc -l < "$OUT/readings-after.jsonl")" -gt "$n0" ]; then
    log "FIRST: $(tail -n +$((n0+1)) "$OUT/readings-after.jsonl" | head -1 | cut -c1-140)"; break
  fi
  sleep 10
done
log "done; files in $OUT"
