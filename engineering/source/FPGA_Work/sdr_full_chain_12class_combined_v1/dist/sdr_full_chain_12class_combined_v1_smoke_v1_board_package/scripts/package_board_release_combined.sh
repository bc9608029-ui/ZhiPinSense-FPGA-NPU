#!/usr/bin/env bash
# package_board_release_combined.sh -- assemble the combined-bitstream smoke_v1
# board release (task 39e5 §十 / first-smoke deliverable).
#
# Builds a self-contained software tarball the board user copies to the FMQL30TAI
# Linux image: sources (board_package/ + sdr_adapter/ + ui_sw/), build scripts, the
# frozen model artifacts (model_12class/), the deployment golden set
# (deployment_golden/), the run scripts (scripts/, incl. the UNLOCKED
# run_gate9_ui.sh), docs + contracts, and the provenance manifest.
#
# The gate binaries are NOT packaged (built ON board: build_on_board.sh,
# build_npu_on_board.sh, build_ui_live.sh, then copied into bin/).  Host test
# binaries (x86 WSL) are also excluded.  The FPGA bitstream is a SEPARATE deliverable
# (outputs/smoke_v1/bitstream/), NOT part of this tarball.
#
# Produces:
#   dist/sdr_full_chain_12class_combined_v1_smoke_v1_board_package.tar.gz
#   dist/.../SHA256SUMS.txt  (relative paths, sha256sum -c verifies)
#
# Usage (inside WSL/Git Bash, from the project root):
#   bash scripts/package_board_release_combined.sh
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

PKG_NAME="sdr_full_chain_12class_combined_v1_smoke_v1_board_package"
DIST="$ROOT/dist"
STAGE="$DIST/$PKG_NAME"
TARBALL="$DIST/$PKG_NAME.tar.gz"

rm -rf "$DIST"
mkdir -p "$STAGE/board_package" "$STAGE/sdr_adapter" "$STAGE/ui_sw" \
         "$STAGE/scripts" "$STAGE/contracts" "$STAGE/model_12class" \
         "$STAGE/deployment_golden" "$STAGE/docs" "$STAGE/host_tests"

# ---- sources + build scripts ------------------------------------------------
cp board_package/*.cpp board_package/*.hpp board_package/*.sh \
   board_package/CMakeLists.txt "$STAGE/board_package/"
cp sdr_adapter/*.hpp sdr_adapter/*.cpp sdr_adapter/*.h "$STAGE/sdr_adapter/"
cp ui_sw/*.cpp ui_sw/*.hpp "$STAGE/ui_sw/"
cp scripts/*.sh "$STAGE/scripts/"
cp contracts/*.md "$STAGE/contracts/"

# ---- host tests (sources only; x86 WSL binaries in host_tests/bin|asan excluded) --
cp host_tests/*.cpp host_tests/*.sh "$STAGE/host_tests/"

# ---- frozen model artifacts (exclude calibration/ intermediates) ------------
cp model_12class/model_12class.json model_12class/model_12class.raw \
   model_12class/model_12class.sha256 \
   model_12class/MODEL_DEPLOYMENT_CONTRACT.md "$STAGE/model_12class/"

# ---- deployment golden set (all inputs + expected sidecars + manifest) -------
cp deployment_golden/* "$STAGE/deployment_golden/"

# ---- docs + provenance --------------------------------------------------------
cp docs/*.md "$STAGE/docs/"
cp README.md SOURCE_PROVENANCE_SHA256.txt "$STAGE/"

# ---- SHA256SUMS.txt (relative to the package root; excludes itself) ----------
( cd "$STAGE" && find . -type f ! -name SHA256SUMS.txt -printf '%P\0' \
    | sort -z | xargs -0 sha256sum > SHA256SUMS.txt )

# ---- tarball (deterministic: fixed mtime + no gzip timestamp/name) ------------
GZIP=-n tar -czf "$TARBALL" -C "$DIST" "$PKG_NAME" \
  --mtime='UTC 2026-10-06' --owner=0 --group=0 --numeric-owner

# ---- self-verify: unpack to a temp dir and sha256sum -c -----------------------
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
tar -xzf "$TARBALL" -C "$TMP"
( cd "$TMP/$PKG_NAME" && sha256sum -c SHA256SUMS.txt )

PKG_SHA="$(sha256sum -b "$TARBALL" | awk '{print $1}')"
FILE_COUNT="$(find "$STAGE" -type f | wc -l)"

echo "Package : $TARBALL"
echo "SHA256  : $PKG_SHA"
echo "Files   : $FILE_COUNT (incl. SHA256SUMS.txt)"
echo "Self-check: sha256sum -c SHA256SUMS.txt -> all OK"
