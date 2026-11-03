#!/usr/bin/env bash
# package_board_release.sh -- assemble the twelve-class Gate 6-9 board release.
#
# Builds a self-contained tarball the board user copies to the FMQL30TAI Linux
# image: sources (board_package/ + sdr_adapter/), build scripts, the frozen model
# artifacts (model_12class/), the deployment golden set (deployment_golden/), the
# run scripts (scripts/), the docs + contracts, and the provenance manifests.
#
# The gate binaries themselves are NOT packaged (they must be built ON the board:
# ./board_package/build_on_board.sh and ./board_package/build_npu_on_board.sh,
# then copied into bin/).  Host test binaries (x86 WSL) are also excluded.
#
# Produces:
#   dist/sdr_full_chain_12class_board_package.tar.gz
#   dist/sdr_full_chain_12class_board_package/SHA256SUMS.txt  (relative, sha256sum -c)
#
# Usage (inside WSL/Git Bash, from the project root):
#   bash scripts/package_board_release.sh
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

PKG_NAME="sdr_full_chain_12class_board_package"
DIST="$ROOT/dist"
STAGE="$DIST/$PKG_NAME"
TARBALL="$DIST/$PKG_NAME.tar.gz"

rm -rf "$DIST"
mkdir -p "$STAGE/board_package" "$STAGE/sdr_adapter" "$STAGE/scripts" \
         "$STAGE/contracts" "$STAGE/tools" "$STAGE/model_12class" \
         "$STAGE/deployment_golden" "$STAGE/docs"

# ---- sources + build scripts ------------------------------------------------
cp board_package/*.cpp board_package/*.hpp board_package/*.sh \
   board_package/CMakeLists.txt "$STAGE/board_package/"
cp sdr_adapter/*.hpp sdr_adapter/*.cpp sdr_adapter/*.h "$STAGE/sdr_adapter/"
cp scripts/*.sh "$STAGE/scripts/"
cp contracts/*.md "$STAGE/contracts/"
cp tools/*.py tools/*.sh "$STAGE/tools/"

# ---- frozen model artifacts (exclude compile/ + calibration/ intermediates) --
cp model_12class/model_12class.json model_12class/model_12class.raw \
   model_12class/model_12class.sha256 \
   model_12class/MODEL_DEPLOYMENT_CONTRACT.md "$STAGE/model_12class/"

# ---- deployment golden set (all inputs + expected sidecars + manifest) -------
cp deployment_golden/* "$STAGE/deployment_golden/"

# ---- docs + provenance --------------------------------------------------------
cp docs/*.md "$STAGE/docs/"
cp SOURCE_PROVENANCE_SHA256.txt "$STAGE/"

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
