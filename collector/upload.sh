#!/bin/sh
# Ship whatever has arrived since the last run. Installed on the collector host
# as a cron entry; the container is created and destroyed for each run, so
# nothing long-lived holds the certificate open.
#
#   */15 * * * * /home/<user>/zt-collector/upload.sh >> /home/<user>/zt-collector/upload.log 2>&1
#
# The image is python:3.13-slim rather than alpine for one reason: it ships the
# openssl binary, and the signing needs it. Installing a package at runtime, as
# root, on the machine that holds the credential, to save 40 MB, is the wrong
# trade.
set -eu
HOME_DIR="$(cd "$(dirname "$0")" && pwd)"
exec docker run --rm \
  --env-file "$HOME_DIR/uploader.env" \
  -v "$HOME_DIR/certs:/certs:ro" \
  -v "$HOME_DIR/uploader.py:/app/uploader.py:ro" \
  -v zt-collector-data:/data:ro \
  -v "$HOME_DIR/state:/state" \
  --user "$(id -u):$(id -g)" \
  --read-only --cap-drop ALL --security-opt no-new-privileges \
  --memory 96m --pids-limit 32 \
  python:3.13-slim python3 /app/uploader.py
