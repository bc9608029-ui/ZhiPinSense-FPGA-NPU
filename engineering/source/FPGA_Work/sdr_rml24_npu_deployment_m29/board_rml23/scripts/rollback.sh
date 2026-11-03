#!/usr/bin/env bash
# M29 Phase F4 — roll back the board deployment to the previous model files.
#
#   ./scripts/rollback.sh
#
# The deploy flow keeps a backup of the currently-running model/ before writing
# the new one (see README "upload/run").  This script restores that backup and
# re-verifies package identity.  It NEVER touches the NPU flash or bitstream —
# it only swaps the model json/raw files in this deployment directory.
#
# Fail-closed: refuses to roll back if no backup exists or the restored files
# fail the frozen identity check.
set -euo pipefail

PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PKG_DIR"

BACKUP="model.prev"
MODEL="model"

if [ ! -d "$BACKUP" ]; then
  echo "FAIL: no backup at $BACKUP; nothing to roll back to." >&2
  exit 1
fi

for f in model_24class_ZG.json model_24class_ZG.raw; do
  if [ ! -f "$BACKUP/$f" ]; then
    echo "FAIL: backup missing $f" >&2
    exit 1
  fi
done

# stop any running chain before swapping model files
"$PKG_DIR/scripts/stop_rml23.sh" || true

echo "[rollback] restoring previous model files from $BACKUP"
for f in model_24class_ZG.json model_24class_ZG.raw; do
  cp -f "$BACKUP/$f" "$MODEL/$f"
done

echo "[rollback] re-verifying restored package identity"
"$PKG_DIR/scripts/verify_package.sh"

echo "== ROLLBACK COMPLETE =="
