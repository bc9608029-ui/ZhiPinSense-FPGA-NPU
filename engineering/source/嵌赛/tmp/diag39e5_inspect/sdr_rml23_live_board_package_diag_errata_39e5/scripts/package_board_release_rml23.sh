#!/usr/bin/env bash
# package_board_release_rml23.sh -- assemble the RML23 (M29 Phase F5) 23-class
# live board package.
#
# Builds a self-contained, SOURCE-ONLY tarball the board user copies to the
# FMQL30TAI Linux image: sources (board_package/ + sdr_adapter/ + ui_sw/), the
# host test + tool sources, the run scripts, the frozen model artifacts
# (model_rml23/ 23-class expA + model_12class/ rollback), the deployment golden
# set, the contracts, and the docs.
#
# The gate/UI binaries are NOT packaged (they must be built ON the board via
# ./scripts/build_on_board.sh).  Host test binaries (x86 WSL) and Python bytecode
# caches are excluded, so the package contains no Windows/x86/WSL/ELF/Mach-O binary.
#
# Produces:
#   dist/sdr_rml23_live_board_package.tar.gz
#   dist/sdr_rml23_live_board_package/SHA256SUMS.txt  (relative, sha256sum -c)
#
# Usage (inside WSL/Git Bash, from the package root):
#   bash scripts/package_board_release_rml23.sh
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

PKG_NAME="sdr_rml23_live_board_package"
DIST="$ROOT/dist"
STAGE="$DIST/$PKG_NAME"
TARBALL="$DIST/$PKG_NAME.tar.gz"

rm -rf "$DIST"
mkdir -p "$STAGE/board_package" "$STAGE/sdr_adapter" "$STAGE/ui_sw" \
         "$STAGE/scripts" "$STAGE/contracts" "$STAGE/host_tests" \
         "$STAGE/host_tools" "$STAGE/model_rml23" "$STAGE/model_12class" \
         "$STAGE/deployment_golden"

# ---- sources + build scripts ------------------------------------------------
cp board_package/*.cpp board_package/*.hpp board_package/*.sh \
   board_package/CMakeLists.txt "$STAGE/board_package/"
cp sdr_adapter/*.hpp sdr_adapter/*.cpp sdr_adapter/*.h "$STAGE/sdr_adapter/"
cp ui_sw/*.cpp ui_sw/*.hpp "$STAGE/ui_sw/"
cp scripts/*.sh scripts/*.py "$STAGE/scripts/"
cp contracts/*.md contracts/*.py contracts/*.json "$STAGE/contracts/"

# ---- host test / tool SOURCES only (exclude compiled bin/ + __pycache__) -----
cp host_tests/*.cpp host_tests/*.sh "$STAGE/host_tests/"
cp host_tools/*.py "$STAGE/host_tools/"

# ---- frozen model artifacts --------------------------------------------------
cp model_rml23/model_24class_ZG.json model_rml23/model_24class_ZG.raw \
   model_rml23/model_rml23.sha256 \
   model_rml23/MODEL_DEPLOYMENT_CONTRACT.md "$STAGE/model_rml23/"
cp model_12class/model_12class.json model_12class/model_12class.raw \
   model_12class/model_12class.sha256 \
   model_12class/MODEL_DEPLOYMENT_CONTRACT.md "$STAGE/model_12class/"

# ---- deployment golden set + top-level README --------------------------------
# -r: the golden set now includes the coverage_supplemental/ audit subdir
# (audit-only, the board gate never reads it), so copy recursively.
cp -r deployment_golden/* "$STAGE/deployment_golden/"
cp README.md "$STAGE/"

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
