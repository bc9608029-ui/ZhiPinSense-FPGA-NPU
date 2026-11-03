#!/usr/bin/env bash
set -euo pipefail

PKG_DIR=/mnt/f/FPGA_Work/sdr_full_chain_12class_ui_v3_m17_3/sdr_full_chain_12class_ui_v3_board_package_m17_2
DIST=/mnt/f/FPGA_Work/sdr_full_chain_12class_ui_v3_m17_3/dist
M17_2_TAR=/mnt/f/FPGA_Work/sdr_full_chain_12class_ui_v3_m17_2/dist/sdr_full_chain_12class_ui_v3_board_package_m17_2.tar.gz
WORK=/mnt/f/FPGA_Work/_scratch_m17_3/build

MTIME='UTC 2026-10-07'
TOPDIR=sdr_full_chain_12class_ui_v3_board_package_m17_3

echo "=== 0. confirm baseline exists ==="
ls -la "$M17_2_TAR"

echo "=== 1. regenerate full SHA256SUMS.txt (M17.3 content) ==="
( cd "$PKG_DIR" && find . -type f ! -name SHA256SUMS.txt -printf '%P\0' | sort -z | xargs -0 sha256sum > SHA256SUMS.txt )
echo "    manifest lines: $(wc -l < "$PKG_DIR/SHA256SUMS.txt")"

echo "=== 2. build M17.3 patch tarball (8 files) ==="
rm -rf "$WORK"
mkdir -p "$WORK"
( cd "$PKG_DIR" && \
  GZIP=-n tar -czf "$WORK/m17_3_minimal_script_patch.tar.gz" \
    --mtime="$MTIME" --owner=0 --group=0 --numeric-owner \
    README.md PROVENANCE.md SHA256SUMS.txt \
    docs/M17_BOARD_ACCEPTANCE.md docs/TOUCH_MODE_CONTROL_CONTRACT.md \
    scripts/process_guard.sh scripts/run_m17_touch_acceptance.sh \
    scripts/test_m17_touch_acceptance.sh )

echo "=== 3. build M17.3 full package (top dir $TOPDIR) ==="
rm -rf "$WORK/full"
mkdir -p "$WORK/full"
cp -a "$PKG_DIR" "$WORK/full/$TOPDIR"
( cd "$WORK/full" && \
  GZIP=-n tar -czf "$WORK/$TOPDIR.tar.gz" \
    --mtime="$MTIME" --owner=0 --group=0 --numeric-owner "$TOPDIR" )

echo "=== 4. verify: M17.2 full + patch  ==  M17.3 full ==="
rm -rf "$WORK/verify"
mkdir -p "$WORK/verify"
tar -xzf "$M17_2_TAR" -C "$WORK/verify"
BASE="$WORK/verify/sdr_full_chain_12class_ui_v3_board_package_m17_2"
tar -xzf "$WORK/m17_3_minimal_script_patch.tar.gz" -C "$BASE"
tar -xzf "$WORK/$TOPDIR.tar.gz" -C "$WORK/verify"
FULL="$WORK/verify/$TOPDIR"
echo "    diff -rq (expect zero output):"
diff -rq "$BASE" "$FULL" && echo "    DIFF: IDENTICAL"
echo "    sha256sum -c (M17.3 full):"
( cd "$FULL" && sha256sum -c SHA256SUMS.txt | tail -n 1 )
echo "    patch SHA256SUMS.txt == full SHA256SUMS.txt ?"
cmp "$BASE/SHA256SUMS.txt" "$FULL/SHA256SUMS.txt" && echo "    MANIFEST: IDENTICAL"

echo "=== 5. copy artifacts to dist/ ==="
mkdir -p "$DIST"
cp -f "$WORK/m17_3_minimal_script_patch.tar.gz" "$DIST/"
cp -f "$WORK/$TOPDIR.tar.gz" "$DIST/"

echo "=== 6. final SHAs + sizes ==="
sha256sum "$DIST/m17_3_minimal_script_patch.tar.gz" "$DIST/$TOPDIR.tar.gz"
ls -la "$DIST"
echo "=== file counts ==="
echo "patch files: $(tar -tzf "$DIST/m17_3_minimal_script_patch.tar.gz" | wc -l)"
echo "full files:  $(tar -tzf "$DIST/$TOPDIR.tar.gz" | wc -l)"
