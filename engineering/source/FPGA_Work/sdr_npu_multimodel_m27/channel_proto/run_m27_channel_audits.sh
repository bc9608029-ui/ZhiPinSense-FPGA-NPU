#!/usr/bin/env bash
# M27 channel-prototype audits: 3-way isolation + generator-shortcut.
# Offline, synthetic only.  Exit non-zero on any protocol violation.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

echo "== M27 channel isolation audit =="
python m27_channel_isolation_audit.py

echo "== M27 channel generator-shortcut audit =="
python m27_channel_shortcut_audit.py

echo "== M27_CHANNEL_AUDITS_OK =="
