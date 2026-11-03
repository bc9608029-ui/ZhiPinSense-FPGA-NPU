#!/usr/bin/env bash
# build_m18_sw1_1_package.sh -- assemble the M18-SW1.1 deliverables (serial-silence
# real-fd test + run_ui_live.sh UI_RUN_DIR test hook), versioned and WITHOUT
# touching the M18-SW1 package.
#
# Produces (deterministically: GZIP=-n + fixed mtime + numeric owner):
#   F:/FPGA_Work/sdr_full_chain_12class_ui_v3_m18_sw1_1/dist/
#     m18_sw1_1_serial_silence_patch.tar.gz              (flat, overlay onto M18-SW1)
#     sdr_full_chain_12class_ui_v3_m18_sw1_1_board_package.tar.gz  (full package)
#
# Verification:
#   * pre-flight: bash -n on the two scripts + run scripts/test_serial_silence.sh
#     against a fresh M18-SW1 + overlay tree (REAL /proc/PID/fd verification);
#   * full package: unpack -> sha256sum -c SHA256SUMS.txt -> all OK;
#   * patch(over M18-SW1) is byte-identical to the full package (diff -rq zero).
set -euo pipefail

SW1_TAR=/mnt/f/FPGA_Work/sdr_full_chain_12class_ui_v3_m18_sw1/dist/sdr_full_chain_12class_ui_v3_m18_sw1_board_package.tar.gz
SW1_NAME=sdr_full_chain_12class_ui_v3_m18_sw1_board_package
OVERLAY=/mnt/f/FPGA_Work/sdr_full_chain_12class_ui_v3_m18_sw1_1/overlay
PKG_NAME=sdr_full_chain_12class_ui_v3_m18_sw1_1_board_package
PATCH_NAME=m18_sw1_1_serial_silence_patch
DIST=/mnt/f/FPGA_Work/sdr_full_chain_12class_ui_v3_m18_sw1_1/dist
MTIME='UTC 2026-10-08'

PATCH_FILES=(
  SHA256SUMS.txt
  scripts/run_ui_live.sh
  scripts/test_serial_silence.sh
  docs/M18_SW1_SERIAL_SILENCE_ERRATA.md
)

echo "== pre-flight: bash -n on new/changed scripts =="
bash -n "$OVERLAY/scripts/run_ui_live.sh"
bash -n "$OVERLAY/scripts/test_serial_silence.sh"
echo "   bash -n OK"

echo "== pre-flight: host test (REAL fd verification) =="
PRE="$(mktemp -d)"
tar -xzf "$SW1_TAR" -C "$PRE"
cp -a "$OVERLAY/." "$PRE/$SW1_NAME/"
( cd "$PRE/$SW1_NAME" && bash scripts/test_serial_silence.sh )
rm -rf "$PRE"

echo "== stage full package (unpack M18-SW1 + overlay) =="
rm -rf "$DIST"
mkdir -p "$DIST"
tar -xzf "$SW1_TAR" -C "$DIST"
mv "$DIST/$SW1_NAME" "$DIST/$PKG_NAME"
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

echo "== build patch tarball (flat, overlay onto M18-SW1) =="
GZIP=-n tar -czf "$DIST/$PATCH_NAME.tar.gz" -C "$DIST/$PKG_NAME" "${PATCH_FILES[@]}" \
  --mtime="$MTIME" --owner=0 --group=0 --numeric-owner

echo "== verify full package: unpack + sha256sum -c =="
V1="$(mktemp -d)"
tar -xzf "$DIST/$PKG_NAME.tar.gz" -C "$V1"
( cd "$V1/$PKG_NAME" && sha256sum -c --quiet SHA256SUMS.txt )
echo "   full package: sha256sum -c -> all OK ($(find "$V1/$PKG_NAME" -type f | wc -l) files)"

echo "== verify patch(over M18-SW1) == full package (diff -rq) =="
V2="$(mktemp -d)"
tar -xzf "$SW1_TAR" -C "$V2"
tar -xzf "$DIST/$PATCH_NAME.tar.gz" -C "$V2/$SW1_NAME"
( cd "$V2/$SW1_NAME" && sha256sum -c --quiet SHA256SUMS.txt )
if diff -rq "$V2/$SW1_NAME" "$V1/$PKG_NAME"; then
  echo "   diff -rq: ZERO differences (patch + M18-SW1 == full package)"
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
