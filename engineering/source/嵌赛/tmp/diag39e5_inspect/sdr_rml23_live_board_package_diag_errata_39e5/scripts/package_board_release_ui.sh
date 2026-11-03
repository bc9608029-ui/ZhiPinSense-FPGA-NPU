#!/usr/bin/env bash
# package_board_release_ui.sh -- assemble the twelve-class Gate 6-9 + LIVE-UI
# board release (task 39e5 §九).
#
# Builds a self-contained tarball the board user copies to the FMQL30TAI Linux
# image: sources (board_package/ + sdr_adapter/ + ui_sw/), build scripts, the
# frozen model artifacts (model_12class/), the deployment golden set
# (deployment_golden/), the run scripts (scripts/), the docs + contracts, and the
# provenance manifests (PROVENANCE.md + SOURCE_PROVENANCE_SHA256.txt).
#
# Unlike package_board_release.sh (the pure Gate 6-9 package), this one ALSO ships
# ui_sw/ (the DirectFramebufferBackend + Style A render stack + embedded font
# atlas) so the board can build the LIVE UI server (board_ui_live_12class).
#
# The gate binaries themselves are NOT packaged (they must be built ON the board:
# ./board_package/build_on_board.sh, ./board_package/build_npu_on_board.sh, and
# ./board_package/build_ui_live.sh, then copied into bin/).  Host test binaries
# (x86 WSL) are also excluded.
#
# Produces:
#   dist/sdr_full_chain_12class_ui_v1_board_package.tar.gz
#   dist/sdr_full_chain_12class_ui_v1_board_package/SHA256SUMS.txt  (relative, sha256sum -c)
#
# Usage (inside WSL/Git Bash, from the project root):
#   bash scripts/package_board_release_ui.sh
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

PKG_NAME="sdr_full_chain_12class_ui_v1_board_package"
DIST="$ROOT/dist"
STAGE="$DIST/$PKG_NAME"
TARBALL="$DIST/$PKG_NAME.tar.gz"

rm -rf "$DIST"
mkdir -p "$STAGE/board_package" "$STAGE/sdr_adapter" "$STAGE/ui_sw" \
         "$STAGE/scripts" "$STAGE/contracts" "$STAGE/tools" "$STAGE/model_12class" \
         "$STAGE/deployment_golden" "$STAGE/docs" "$STAGE/host_tests"

# ---- sources + build scripts ------------------------------------------------
cp board_package/*.cpp board_package/*.hpp board_package/*.sh \
   board_package/CMakeLists.txt "$STAGE/board_package/"
cp sdr_adapter/*.hpp sdr_adapter/*.cpp sdr_adapter/*.h "$STAGE/sdr_adapter/"
cp ui_sw/*.cpp ui_sw/*.hpp "$STAGE/ui_sw/"
cp scripts/*.sh "$STAGE/scripts/"
cp contracts/*.md "$STAGE/contracts/"
cp tools/*.py tools/*.sh "$STAGE/tools/"

# ---- host tests (sources only; x86 WSL binaries in host_tests/bin/ excluded) --
cp host_tests/*.cpp host_tests/*.sh "$STAGE/host_tests/"

# ---- frozen model artifacts (exclude compile/ + calibration/ intermediates) --
cp model_12class/model_12class.json model_12class/model_12class.raw \
   model_12class/model_12class.sha256 \
   model_12class/MODEL_DEPLOYMENT_CONTRACT.md "$STAGE/model_12class/"

# ---- deployment golden set (all inputs + expected sidecars + manifest) -------
cp deployment_golden/* "$STAGE/deployment_golden/"

# ---- docs + provenance --------------------------------------------------------
cp docs/*.md "$STAGE/docs/"
cp PROVENANCE.md SOURCE_PROVENANCE_SHA256.txt README.md "$STAGE/"

# ---- SHA256SUMS.txt (relative to the package root; excludes itself) ----------
( cd "$STAGE" && find . -type f ! -name SHA256SUMS.txt -printf '%P\0' \
    | sort -z | xargs -0 sha256sum > SHA256SUMS.txt )

# ---- tarball ------------------------------------------------------------------
tar -czf "$TARBALL" -C "$DIST" "$PKG_NAME"

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
