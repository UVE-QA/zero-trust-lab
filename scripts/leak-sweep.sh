#!/usr/bin/env bash
# Disclosure sweep: refuse any tracked file that carries a real-world value.
#
# Runs in CI on every PR and is meant to be run locally BEFORE committing --
# git history is permanent, so a hit caught by CI on a pushed commit is
# already too late. Scans only git-tracked files, so `local/` (gitignored)
# is never read.
#
#   ./scripts/leak-sweep.sh
#
# Device names and any other site-specific strings are supplied out-of-band
# via $LEAK_DENYLIST (newline-separated); they are never written into this
# repo. In CI that comes from the LEAK_DENYLIST repository secret.

set -uo pipefail

# Files allowed to contain the patterns, because they *are* the patterns.
SELF_EXCLUDE='^(scripts/leak-sweep\.sh|\.github/workflows/leak-scan\.yml)$'

report() {
  local label="$1" file="$2" line="$3" text="$4"
  printf '::error file=%s,line=%s::%s: %s\n' "$file" "$line" "$label" "$text"
  printf '  %-28s %s:%s: %s\n' "$label" "$file" "$line" "$text" >&2
}

scan() {
  local label="$1" pattern="$2"
  while IFS= read -r file; do
    [[ "$file" =~ $SELF_EXCLUDE ]] && continue
    [ -f "$file" ] || continue
    grep -InE "$pattern" -- "$file" 2>/dev/null | while IFS=: read -r line text; do
      printf '%s\t%s\t%s\n' "$file" "$line" "${text:0:200}"
    done
  done < <(git ls-files) | while IFS=$'\t' read -r file line text; do
    report "$label" "$file" "$line" "$text"
    echo x >> "$TALLY"
  done
}

TALLY="$(mktemp)"
trap 'rm -f "$TALLY"' EXIT

echo "== disclosure sweep =="

# 1. Tailnet addresses -- CGNAT 100.64.0.0/10.
scan "tailnet-address" \
  '\b100\.(6[4-9]|[7-9][0-9]|1[0-1][0-9]|12[0-7])\.[0-9]{1,3}\.[0-9]{1,3}\b'

# 2. Private LAN addresses -- RFC 1918.
scan "lan-address-192.168" '\b192\.168\.[0-9]{1,3}\.[0-9]{1,3}\b'
scan "lan-address-10.x"    '\b10\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\b'
scan "lan-address-172.16"  '\b172\.(1[6-9]|2[0-9]|3[01])\.[0-9]{1,3}\.[0-9]{1,3}\b'

# 3. The tailnet's own MagicDNS domain.
scan "tailnet-domain" '[A-Za-z0-9-]+\.ts\.net'

# 4. AWS account id, bare or inside an ARN.
scan "aws-account-id" '(^|[^0-9A-Za-z_-])[0-9]{12}([^0-9A-Za-z_-]|$)'
scan "aws-arn"        'arn:aws[a-z-]*:[^:]*:[^:]*:[0-9]{12}:'

# 5. Credentials that must never be committed.
scan "tailscale-key"  'tskey-[a-z]+-[A-Za-z0-9]+'
scan "aws-access-key" '\b(AKIA|ASIA)[0-9A-Z]{16}\b'
scan "private-key"    '-----BEGIN [A-Z ]*PRIVATE KEY-----'

# 6. Hardware identifiers -- a MAC pins a specific physical device.
scan "mac-address" '\b([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}\b'

# 7. Site-specific strings supplied out-of-band: device names, ssids, the
#    tailnet name, the household surname. Never stored in the repo.
if [ -n "${LEAK_DENYLIST:-}" ]; then
  while IFS= read -r term; do
    term="$(printf '%s' "$term" | tr -d '\r' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    [ -z "$term" ] && continue
    case "$term" in \#*) continue ;; esac
    # The term itself is secret -- report the match location, not the term.
    while IFS= read -r file; do
      [[ "$file" =~ $SELF_EXCLUDE ]] && continue
      [ -f "$file" ] || continue
      if grep -Iiqs -- "$term" "$file"; then
        n="$(grep -Iin -- "$term" "$file" | head -1 | cut -d: -f1)"
        printf '::error file=%s,line=%s::denylisted-term: a term from LEAK_DENYLIST appears here\n' "$file" "$n"
        printf '  %-28s %s:%s: (term redacted)\n' "denylisted-term" "$file" "$n" >&2
        echo x >> "$TALLY"
      fi
    done < <(git ls-files)
  done <<< "$LEAK_DENYLIST"
else
  echo "  note: LEAK_DENYLIST is empty -- device-name sweep skipped" >&2
fi

total="$(wc -l < "$TALLY" | tr -d ' ')"
if [ "$total" -gt 0 ]; then
  echo >&2
  echo "FAIL: $total disclosure hit(s). Nothing containing a real hostname," >&2
  echo "address, account id or device model may be committed." >&2
  exit 1
fi

echo "OK: no real-world values in tracked files."
