#!/usr/bin/env bash
# build_m18_sw1_package.sh -- assemble the M18-SW1 (touch first-response + serial
# silence + acceptance-race fix) deliverables, versioned and WITHOUT touching the
# M18-0 package.
#
# Produces, deterministically (GZIP=-n + fixed mtime + numeric owner):
#   F:/FPGA_Work/sdr_full_chain_12class_ui_v3_m18_sw1/dist/
#     m18_sw1_touch_log_acceptance_patch.tar.gz        (flat, 9 files, overlay onto M18-0)
#     sdr_full_chain_12class_ui_v3_m18_sw1_board_package.tar.gz  (full package)
#
# Verification performed by this script:
#   * full package: unpack to temp -> sha256sum -c SHA256SUMS.txt -> all OK;
#   * patch: unpack M18-0 -> overlay patch -> sha256sum -c SHA256SUMS.txt -> all OK;
#   * patch(over M18-0) is byte-identical to the full package (diff -rq zero).
set -euo pipefail

SRC=/mnt/f/FPGA_Work/sdr_full_chain_12class_ui_v3_m18/sdr_full_chain_12class_ui_v3_board_package_m18
M18_0_TAR=/mnt/f/FPGA_Work/sdr_full_chain_12class_ui_v3_m18/dist/sdr_full_chain_12class_ui_v3_m18_0_board_diagnostic_package.tar.gz
M18_0_NAME=sdr_full_chain_12class_ui_v3_m18_0_board_diagnostic_package
PKG_NAME=sdr_full_chain_12class_ui_v3_m18_sw1_board_package
PATCH_NAME=m18_sw1_touch_log_acceptance_patch
DIST=/mnt/f/FPGA_Work/sdr_full_chain_12class_ui_v3_m18_sw1/dist
STAGE="$DIST/$PKG_NAME"
TARBALL="$DIST/$PKG_NAME.tar.gz"
PATCH="$DIST/$PATCH_NAME.tar.gz"
MTIME='UTC 2026-10-08'

# ---- changed + new files (the exact M18-SW1 diff vs M18-0) ----------------------
PATCH_FILES=(
  SHA256SUMS.txt
  board_package/board_ui_live_12class.cpp
  board_package/touch_mode_control.hpp
  board_package/ui_dirty_state.hpp
  host_tests/test_touch_mode_control.cpp
  ui_sw/ui_render.cpp
  ui_sw/ui_render.hpp
  scripts/run_m18_sw1_touch_acceptance.sh
  scripts/test_m18_sw1_touch_acceptance.sh
)

echo "== pre-flight: bash -n on new/changed scripts =="
bash -n "$SRC/scripts/run_m18_sw1_touch_acceptance.sh"
bash -n "$SRC/scripts/test_m18_sw1_touch_acceptance.sh"
bash -n "$SRC/scripts/process_guard.sh"
bash -n "$SRC/scripts/run_ui_live.sh"
echo "   bash -n OK"

echo "== pre-flight: host shell test (test_m18_sw1_touch_acceptance.sh) =="
( cd "$SRC" && bash scripts/test_m18_sw1_touch_acceptance.sh )

echo "== stage full package (copy source, drop build-artifact dirs) =="
rm -rf "$DIST"
mkdir -p "$STAGE"
cp -a "$SRC/." "$STAGE/"
rm -rf "$STAGE/bin" "$STAGE/host_tests/bin"

echo "== regenerate SHA256SUMS.txt (relative, excludes itself) =="
( cd "$STAGE" && find . -type f ! -name SHA256SUMS.txt -printf '%P\0' \
    | sort -z | xargs -0 sha256sum > SHA256SUMS.txt )

STAGED_FILES="$(find "$STAGE" -type f | wc -l)"
MANIFEST_LINES="$(wc -l < "$STAGE/SHA256SUMS.txt")"
echo "   staged files (incl manifest): $STAGED_FILES ; manifest lines: $MANIFEST_LINES"

echo "== build full package tarball (deterministic) =="
GZIP=-n tar -czf "$TARBALL" -C "$DIST" "$PKG_NAME" \
  --mtime="$MTIME" --owner=0 --group=0 --numeric-owner

echo "== build patch tarball (flat, 9 files, overlay onto M18-0) =="
GZIP=-n tar -czf "$PATCH" -C "$STAGE" "${PATCH_FILES[@]}" \
  --mtime="$MTIME" --owner=0 --group=0 --numeric-owner

echo "== verify full package: unpack + sha256sum -c =="
V1="$(mktemp -d)"
tar -xzf "$TARBALL" -C "$V1"
( cd "$V1/$PKG_NAME" && sha256sum -c --quiet SHA256SUMS.txt )
echo "   full package: sha256sum -c -> all OK ($(find "$V1/$PKG_NAME" -type f | wc -l) files)"

echo "== verify patch: unpack M18-0 + overlay patch + sha256sum -c =="
V2="$(mktemp -d)"
tar -xzf "$M18_0_TAR" -C "$V2"
tar -xzf "$PATCH" -C "$V2/$M18_0_NAME"
( cd "$V2/$M18_0_NAME" && sha256sum -c --quiet SHA256SUMS.txt )
echo "   patch+M18-0: sha256sum -c -> all OK"

echo "== verify patch(over M18-0) == full package (diff -rq) =="
if diff -rq "$V2/$M18_0_NAME" "$V1/$PKG_NAME"; then
  echo "   diff -rq: ZERO differences (patch + M18-0 == full package)"
else
  echo "   diff -rq: DIFFERENCES FOUND (see above)" >&2
fi

echo
echo "===== RESULTS ====="
echo "full package : $TARBALL"
echo "  sha256     : $(sha256sum -b "$TARBALL" | awk '{print $1}')"
echo "  bytes      : $(stat -c %s "$TARBALL")"
echo "  files      : $STAGED_FILES (incl SHA256SUMS.txt)"
echo "  manifest   : $MANIFEST_LINES lines"
echo "patch        : $PATCH"
echo "  sha256     : $(sha256sum -b "$PATCH" | awk '{print $1}')"
echo "  bytes      : $(stat -c %s "$PATCH")"
echo "  files      : $(tar -tzf "$PATCH" | grep -v '/$' | wc -l)"
echo "  manifest   : $MANIFEST_LINES lines (full-package manifest)"

rm -rf "$V1" "$V2"
echo "done"
