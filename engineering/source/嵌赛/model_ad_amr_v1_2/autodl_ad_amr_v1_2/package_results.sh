#!/usr/bin/env bash
set -euo pipefail

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="dist/ad_amr_v1_2_results_${STAMP}.zip"
mkdir -p dist
test -d outputs/ad_amr_v1_2
zip -r "$OUT" outputs/ad_amr_v1_2 -x '*/last.pt' '*/.pytest*' '*/__pycache__/*' >/dev/null
sha256sum "$OUT" | tee "${OUT}.sha256"
echo "AD_AMR_V1_2_RESULTS_PACKAGED=$OUT"
