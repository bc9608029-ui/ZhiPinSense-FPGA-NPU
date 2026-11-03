#!/usr/bin/env bash
# build_m19_package.sh -- assemble the M19 UI-visual-polish deliverables, versioned
# and WITHOUT touching the M18-SW1.1 package (or any earlier M14..M18-SW1.1 package).
#
# Produces (deterministically: GZIP=-n + fixed mtime + numeric owner):
#   F:/FPGA_Work/sdr_full_chain_12class_ui_v3_m19/dist/
#     m19_ui_polish_patch.tar.gz                                     (flat, overlay onto M18-SW1.1)
#     sdr_full_chain_12class_ui_v3_m19_ui_polish_board_package.tar.gz (full package)
#
# Verification:
#   * pre-flight: bash -n on the two changed shell scripts + assert every overlay file
#     is byte-identical to its work/pkg counterpart (source of truth);
#   * full package: unpack -> sha256sum -c SHA256SUMS.txt -> all OK;
#   * patch(over M18-SW1.1) is byte-identical to the full package (diff -rq zero).
#
# NOTE: the C++ host-test regression (g++ -Wall -Wextra -Werror, all 29 tests green)
# is run separately in WSL (host_tests/build_host_tests.sh + host_tests/run_tests.sh);
# this script only assembles/verifies the byte-identical deliverables.
set -euo pipefail

BASE_TAR=/mnt/f/FPGA_Work/sdr_full_chain_12class_ui_v3_m18_sw1_1/dist/sdr_full_chain_12class_ui_v3_m18_sw1_1_board_package.tar.gz
BASE_NAME=sdr_full_chain_12class_ui_v3_m18_sw1_1_board_package
OVERLAY=/mnt/f/FPGA_Work/sdr_full_chain_12class_ui_v3_m19/overlay
WORK=/mnt/f/FPGA_Work/sdr_full_chain_12class_ui_v3_m19/work/pkg
PKG_NAME=sdr_full_chain_12class_ui_v3_m19_ui_polish_board_package
PATCH_NAME=m19_ui_polish_patch
DIST=/mnt/f/FPGA_Work/sdr_full_chain_12class_ui_v3_m19/dist
MTIME='UTC 2026-10-08'

PATCH_FILES=(
  SHA256SUMS.txt
  PROVENANCE.md
  board_package/board_ui_live_12class.cpp
  ui_sw/ui_theme.hpp
  ui_sw/ui_layout.hpp
  ui_sw/ui_render.hpp
  ui_sw/ui_render.cpp
  host_tests/test_ui_live.cpp
  host_tests/test_ui_v3_pages.cpp
  host_tests/test_ui_layout_m19.cpp
  host_tests/make_ui_m19_snapshots.cpp
  host_tests/build_host_tests.sh
  host_tests/run_tests.sh
  docs/M19_UI_VISUAL_AUDIT.md
  docs/M19_UI_BEFORE_AFTER.md
  docs/BOARD_M19_UI_POLISH_TEST.md
  artifacts/ui_m19/main_live.ppm
  artifacts/ui_m19/main_stale.ppm
  artifacts/ui_m19/main_error.ppm
  artifacts/ui_m19/main_mock.ppm
  artifacts/ui_m19/parameters.ppm
  artifacts/ui_m19/mode_stopped.ppm
  artifacts/ui_m19/legend.ppm
)

echo "== pre-flight: bash -n on changed shell scripts =="
bash -n "$OVERLAY/host_tests/build_host_tests.sh"
bash -n "$OVERLAY/host_tests/run_tests.sh"
echo "   bash -n OK"

echo "== pre-flight: overlay files byte-identical to work/pkg (source of truth) =="
for f in "${PATCH_FILES[@]}"; do
  [ "$f" = "SHA256SUMS.txt" ] && continue
  if ! cmp -s "$OVERLAY/$f" "$WORK/$f"; then
    echo "   MISMATCH: overlay/$f != work/pkg/$f" >&2
    exit 1
  fi
done
echo "   overlay == work/pkg (${#PATCH_FILES[@]} patch entries, SHA256SUMS.txt regenerated below)"

echo "== stage full package (unpack M18-SW1.1 + overlay) =="
rm -rf "$DIST"
mkdir -p "$DIST"
tar -xzf "$BASE_TAR" -C "$DIST"
mv "$DIST/$BASE_NAME" "$DIST/$PKG_NAME"
cp -a "$OVERLAY/." "$DIST/$PKG_NAME/"
rm -rf "$DIST/$PKG_NAME/bin" "$DIST/$PKG_NAME/host_tests/bin"

echo "== regenerate SHA256SUMS.txt (relative, excludes itself) =="
( cd "$DIST/$PKG_NAME" && find . -type f ! -name SHA256SUMS.txt -printf '%P\0' \
    | sort -z | xargs -0 sha256sum > SHA256SUMS.txt )

STAGED_FILES="$(find "$DIST/$PKG_NAME" -type f | wc -l)"
MANIFEST_LINES="$(wc -l < "$DIST/$PKG_NAME/SHA256SUMS.txt")"
echo "   staged files (incl manifest): $STAGED_FILES ; manifest lines: $MANIFEST_LINES"

echo "== build full package tarball (deterministic) =="
GZIP=-n tar -czf "$DIST/$PKG_NAME.tar.gz" -C "$DIST" "$PKG_NAME" \
  --mtime="$MTIME" --owner=0 --group=0 --numeric-owner

echo "== build patch tarball (flat, overlay onto M18-SW1.1) =="
GZIP=-n tar -czf "$DIST/$PATCH_NAME.tar.gz" -C "$DIST/$PKG_NAME" "${PATCH_FILES[@]}" \
  --mtime="$MTIME" --owner=0 --group=0 --numeric-owner

echo "== verify full package: unpack + sha256sum -c =="
V1="$(mktemp -d)"
tar -xzf "$DIST/$PKG_NAME.tar.gz" -C "$V1"
( cd "$V1/$PKG_NAME" && sha256sum -c --quiet SHA256SUMS.txt )
echo "   full package: sha256sum -c -> all OK ($(find "$V1/$PKG_NAME" -type f | wc -l) files)"

echo "== verify patch(over M18-SW1.1) == full package (diff -rq) =="
V2="$(mktemp -d)"
tar -xzf "$BASE_TAR" -C "$V2"
tar -xzf "$DIST/$PATCH_NAME.tar.gz" -C "$V2/$BASE_NAME"
( cd "$V2/$BASE_NAME" && sha256sum -c --quiet SHA256SUMS.txt )
if diff -rq "$V2/$BASE_NAME" "$V1/$PKG_NAME"; then
  echo "   diff -rq: ZERO differences (patch + M18-SW1.1 == full package)"
else
  echo "   diff -rq: DIFFERENCES FOUND (see above)" >&2
  exit 1
fi

echo
echo "===== RESULTS ====="
echo "full package : $DIST/$PKG_NAME.tar.gz"
echo "  sha256     : $(sha256sum -b "$DIST/$PKG_NAME.tar.gz" | awk '{print $1}')"
echo "  bytes      : $(stat -c %s "$DIST/$PKG_NAME.tar.gz")"
echo "  files      : $STAGED_FILES (incl SHA256SUMS.txt)"
echo "  manifest   : $MANIFEST_LINES lines"
echo "patch        : $DIST/$PATCH_NAME.tar.gz"
echo "  sha256     : $(sha256sum -b "$DIST/$PATCH_NAME.tar.gz" | awk '{print $1}')"
echo "  bytes      : $(stat -c %s "$DIST/$PATCH_NAME.tar.gz")"
echo "  files      : $(tar -tzf "$DIST/$PATCH_NAME.tar.gz" | grep -v '/$' | wc -l)"

rm -rf "$V1" "$V2"
echo "done"
