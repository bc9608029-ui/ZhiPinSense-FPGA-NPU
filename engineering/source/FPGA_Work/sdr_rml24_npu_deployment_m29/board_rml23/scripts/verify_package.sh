#!/usr/bin/env bash
# M29 Phase F4 — board package verification (fail-closed).
#
#   1. sha256sum -c over the shipped SHA256SUMS.txt (every content file)
#   2. model json/raw SHA256 must equal the frozen deployment values
#   3. the shipped 23-class contract must recompute to its frozen SHAs
#
# Exit 0 only if ALL checks pass.
set -euo pipefail

PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PKG_DIR"

if command -v python3 >/dev/null 2>&1; then PY=python3
elif command -v python >/dev/null 2>&1; then PY=python
else echo "FAIL: no python3 interpreter" >&2; exit 1; fi

FROZEN_MODEL_JSON_SHA="d43a22848fad56195265fc98f9009039e4e9d9e8da7f58fc5042fb2a602edb2d"
FROZEN_MODEL_RAW_SHA="2425d990dbac0761cfcdb578c2225795e3b700c4afc6800a0b544ff4d50e0cba"

echo "== [1/3] SHA256 manifest =="
sha256sum -c SHA256SUMS.txt

echo "== [2/3] model identity =="
json_sha="$(sha256sum model/model_24class_ZG.json | awk '{print $1}')"
raw_sha="$(sha256sum model/model_24class_ZG.raw | awk '{print $1}')"
if [ "$json_sha" != "$FROZEN_MODEL_JSON_SHA" ]; then
  echo "FAIL: model json SHA mismatch: $json_sha" >&2; exit 1
fi
if [ "$raw_sha" != "$FROZEN_MODEL_RAW_SHA" ]; then
  echo "FAIL: model raw SHA mismatch: $raw_sha" >&2; exit 1
fi
echo "  [OK] model_24class_ZG.json = $json_sha"
echo "  [OK] model_24class_ZG.raw  = $raw_sha"

echo "== [3/3] 23-class contract =="
"$PY" scripts/verify_rml23_contract.py

echo "== PACKAGE VERIFY PASSED =="
