#!/usr/bin/env bash
# package_v2.sh — deterministic tar.gz of the AutoDL package.
set -euo pipefail

cd "$(dirname "$0")/.."

STAGE="$(cd .. && pwd)/dist/v2_stage"
OUT="$(cd .. && pwd)/dist/ad_amr_12class_robust_v2_autodl_package.tar.gz"

python3 scripts/package_v2.py 2>&1

mkdir -p "$(dirname "$OUT")"
GZIP=-n tar -czf "$OUT" --mtime='UTC 2026-10-07' --owner=0 --group=0 --numeric-owner -C "$STAGE" .

echo "package: $OUT"
echo "sha256:"
sha256sum "$OUT"
echo "files inside:"
tar -tzf "$OUT" | wc -l
