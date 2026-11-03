#!/usr/bin/env bash
set -euo pipefail
ROOT=/root/rml24_mainchain_diagnostic_20261028
for i in $(seq 1 100); do
  test -f "$ROOT/diag_fixed01/capture/final.json" && break
  sleep 1
done
test -f "$ROOT/diag_fixed01/capture/final.json"
python3 "$ROOT/package_board.py" > "$ROOT/archive_info.log" 2>&1
python3 "$ROOT/serve_diagnostic_once.py" > "$ROOT/export_server.log" 2>&1
