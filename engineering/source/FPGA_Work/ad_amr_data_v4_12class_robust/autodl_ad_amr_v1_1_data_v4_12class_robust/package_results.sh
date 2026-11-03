#!/usr/bin/env bash
set -euo pipefail

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="dist/ad_amr_v1_1_data_v4_12class_robust_results_${STAMP}.zip"
mkdir -p dist
test -d outputs/ad_amr_v1_1_data_v4_12class_robust
zip -r "$OUT" outputs/ad_amr_v1_1_data_v4_12class_robust \
  -x '*/last.pt' '*/.pytest*' '*/__pycache__/*' >/dev/null
sha256sum "$OUT" | tee "${OUT}.sha256"
echo "AD_AMR_V1_1_DATA_V4_12CLASS_ROBUST_RESULTS_PACKAGED=$OUT"
