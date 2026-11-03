#!/usr/bin/env bash
# M27 channel-impairment synthetic prototype: tiny end-to-end training run.
# Offline CPU only; results are a SYNTHETIC prototype, never a real-environment
# recognition claim.  Writes JSON report under dist/m27_channel_proto_results/.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

OUT="$(cd "$HERE/.." && pwd)/dist/m27_channel_proto_results"
mkdir -p "$OUT"

python m27_channel_train.py \
  --seed "${SEED:-2026}" \
  --samples-per-label "${SAMPLES_PER_LABEL:-32}" \
  --epochs "${EPOCHS:-2}" \
  --out "$OUT"

echo "== M27_CHANNEL_TRAIN_OK (synthetic prototype) =="
