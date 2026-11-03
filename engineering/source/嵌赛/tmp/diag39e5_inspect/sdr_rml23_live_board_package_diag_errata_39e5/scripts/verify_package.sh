#!/usr/bin/env bash
# verify_package.sh -- RML23 (M29 F5) package verification (fail-closed).
#
#   1. model json/raw SHA256 must equal the frozen expA_bf16_head deployment values
#   2. the shipped 23-class label contract must recompute to its frozen SHAs
#   3. if a SHA256SUMS.txt manifest is present (packaged release), sha256sum -c it
#
# Any mismatch (a wrong model, a wrong label order, or a corrupted file) exits
# non-zero BEFORE the board is ever driven.
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

echo "== [1/3] model identity =="
json_sha="$(sha256sum model_rml23/model_24class_ZG.json | awk '{print $1}')"
raw_sha="$(sha256sum model_rml23/model_24class_ZG.raw | awk '{print $1}')"
if [ "$json_sha" != "$FROZEN_MODEL_JSON_SHA" ]; then
  echo "FAIL: model json SHA mismatch: $json_sha" >&2; exit 1
fi
if [ "$raw_sha" != "$FROZEN_MODEL_RAW_SHA" ]; then
  echo "FAIL: model raw SHA mismatch: $raw_sha" >&2; exit 1
fi
echo "  [OK] model_24class_ZG.json = $json_sha"
echo "  [OK] model_24class_ZG.raw  = $raw_sha"

echo "== [2/3] 23-class label contract =="
"$PY" -I scripts/verify_rml23_contract.py

echo "== [3/3] SHA256 manifest (if packaged) =="
if [ -f SHA256SUMS.txt ]; then
    sha256sum -c SHA256SUMS.txt
else
    echo "  [skip] no SHA256SUMS.txt (source tree, not a packaged release)"
fi

echo "== PACKAGE VERIFY PASSED =="
