#!/usr/bin/env bash
# M29 Phase F4 — assemble the RML23-AMSSB-MERGED board candidate package
# (host-side; NOT shipped inside the tarball).
#
#   ./build_package.sh
#
# Stages the source files, the frozen NPU model json/raw (expA_bf16_head), the
# frozen 23-class contract, and the scripts into a clean directory, verifies the
# staged model identity fail-closed, generates SHA256SUMS.txt, and produces:
#
#   dist/sdr_rml23_amssb_merged_board_package.tar.gz
#
# The tarball contains NO prebuilt binary and NO Windows/x86/WSL binary.
set -euo pipefail

PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$PKG_DIR/.." && pwd)"
DIST="$PROJECT_ROOT/dist"

# frozen source locations (read-only)
MODEL_SRC="${MODEL_SRC:-/f/FPGA_Work/_tmp_24class_expA_bf16_head_384_20261010/jsonraw}"
CONTRACT_SRC="$PROJECT_ROOT/contracts"

FROZEN_JSON_SHA="d43a22848fad56195265fc98f9009039e4e9d9e8da7f58fc5042fb2a602edb2d"
FROZEN_RAW_SHA="2425d990dbac0761cfcdb578c2225795e3b700c4afc6800a0b544ff4d50e0cba"

mkdir -p "$DIST"
echo "[build_package] staging board package ..."
STAGE="$(mktemp -d "$DIST/stage.XXXXXX")"
trap 'rm -rf "$STAGE"' EXIT

mkdir -p "$STAGE/rml23"/{model,contract,scripts,src,test_data,bin}

# --- source / scripts / data (no binaries) ---------------------------------
cp "$PKG_DIR/rml23_merged.hpp"              "$STAGE/rml23/"
cp "$PKG_DIR/rml23_merged_test.cpp"         "$STAGE/rml23/"
cp "$PKG_DIR/src/rml23_merged_main.cpp"     "$STAGE/rml23/src/"
cp "$PKG_DIR/README.md"                     "$STAGE/rml23/"
cp "$PKG_DIR/scripts/build_board.sh"        "$STAGE/rml23/scripts/"
cp "$PKG_DIR/scripts/verify_package.sh"     "$STAGE/rml23/scripts/"
cp "$PKG_DIR/scripts/verify_rml23_contract.py" "$STAGE/rml23/scripts/"
cp "$PKG_DIR/scripts/start_rml23.sh"        "$STAGE/rml23/scripts/"
cp "$PKG_DIR/scripts/stop_rml23.sh"         "$STAGE/rml23/scripts/"
cp "$PKG_DIR/scripts/check_ui_result.sh"    "$STAGE/rml23/scripts/"
cp "$PKG_DIR/scripts/test_1000_frames.sh"   "$STAGE/rml23/scripts/"
cp "$PKG_DIR/scripts/test_10000_frames.sh"  "$STAGE/rml23/scripts/"
cp "$PKG_DIR/scripts/rollback.sh"           "$STAGE/rml23/scripts/"
cp "$PKG_DIR/test_data/"*.bin               "$STAGE/rml23/test_data/"

# --- frozen model + contract (fail-closed identity) -------------------------
for f in model_24class_ZG.json model_24class_ZG.raw; do
  [ -f "$MODEL_SRC/$f" ] || { echo "FAIL: model source missing: $MODEL_SRC/$f" >&2; exit 1; }
  cp "$MODEL_SRC/$f" "$STAGE/rml23/model/$f"
done
cp "$CONTRACT_SRC/rml23_merged_contract.py"   "$STAGE/rml23/contract/"
cp "$CONTRACT_SRC/rml23_merged_contract.json" "$STAGE/rml23/contract/"

json_sha="$(sha256sum "$STAGE/rml23/model/model_24class_ZG.json" | awk '{print $1}')"
raw_sha="$(sha256sum "$STAGE/rml23/model/model_24class_ZG.raw" | awk '{print $1}')"
[ "$json_sha" = "$FROZEN_JSON_SHA" ] || { echo "FAIL: staged json SHA $json_sha != frozen" >&2; exit 1; }
[ "$raw_sha"  = "$FROZEN_RAW_SHA"  ] || { echo "FAIL: staged raw SHA $raw_sha != frozen" >&2; exit 1; }
echo "  [OK] staged model identity verified (json/raw)"

# --- make scripts executable on the board -----------------------------------
chmod +x "$STAGE/rml23/scripts/"*.sh

# --- SHA256 manifest (content files only, no self-reference) ----------------
(
  cd "$STAGE/rml23"
  # list every file except the manifest itself, in sorted order
  find . -type f ! -name 'SHA256SUMS.txt' -printf '%P\n' | sort \
    | while IFS= read -r rel; do
        sha256sum "$rel"
      done > SHA256SUMS.txt
)

# --- deterministic tarball --------------------------------------------------
mkdir -p "$DIST"
OUT="$DIST/sdr_rml23_amssb_merged_board_package.tar.gz"
rm -f "$OUT"
(
  cd "$STAGE"
  GZIP=-n tar --sort=name --mtime='UTC 2026-10-11' --owner=0 --group=0 \
      --numeric-owner -czf "$OUT" rml23
)

echo "[build_package] wrote $OUT"
echo "[build_package] $(du -h "$OUT" | awk '{print $1}')  files=$(tar -tzf "$OUT" | grep -c '/')"
