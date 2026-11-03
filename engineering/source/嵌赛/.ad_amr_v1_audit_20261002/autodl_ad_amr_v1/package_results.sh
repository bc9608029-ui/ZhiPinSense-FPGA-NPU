#!/usr/bin/env bash
# AD-AMR V1 — package run artifacts (checkpoints, reports, tables, figures).
set -euo pipefail

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="dist/ad_amr_v1_results_${STAMP}.zip"

mkdir -p dist
if [ -d outputs ]; then
  # Exclude the bulky per-epoch last.pt if desired; keep best.pt + reports.
  zip -r "$OUT" outputs/ad_amr_v1 -x '*/last.pt' >/dev/null
  echo "[package_results] wrote $OUT"
else
  echo "[package_results] no outputs/ directory; nothing to package" >&2
  exit 1
fi
