#!/usr/bin/env bash
set -euo pipefail

DIST=/mnt/f/FPGA_Work/sdr_full_chain_12class_ui_v3_m17_3/dist
WORK=/mnt/f/FPGA_Work/_scratch_m17_3/build
FULL="$WORK/verify/sdr_full_chain_12class_ui_v3_board_package_m17_3"
M17_2_TAR=/mnt/f/FPGA_Work/sdr_full_chain_12class_ui_v3_m17_2/dist/sdr_full_chain_12class_ui_v3_board_package_m17_2.tar.gz

echo "=== baseline M17.2 full SHA (compare vs 66817b65...) ==="
sha256sum "$M17_2_TAR"

echo "=== sha256sum -c on M17.3 full package ==="
cd "$FULL"
SUM=$(sha256sum -c SHA256SUMS.txt 2>&1)
echo "$SUM" | grep -E 'FAILED|FAILED open|No such' && echo "!!! FOUND FAILURES" || echo "no FAILED lines"
echo "OK count: $(echo "$SUM" | grep -c ': OK')"
echo "total listed: $(wc -l < SHA256SUMS.txt)"

echo "=== dist/ entries inside full package (expect 0) ==="
tar -tzf "$DIST/sdr_full_chain_12class_ui_v3_board_package_m17_3.tar.gz" | grep -c 'dist/' || echo 0

echo "=== patch tarball file list (expect 8 files) ==="
tar -tzf "$DIST/m17_3_minimal_script_patch.tar.gz"

echo "=== patch SHA256SUMS.txt line count (expect 427 = full manifest) ==="
tar -xOzf "$DIST/m17_3_minimal_script_patch.tar.gz" SHA256SUMS.txt | wc -l

echo "=== only 7 content files changed vs M17.2 (diff the manifests) ==="
tar -xOzf "$M17_2_TAR" sdr_full_chain_12class_ui_v3_board_package_m17_2/SHA256SUMS.txt > /tmp/m17_2_manifest.txt 2>/dev/null || \
  tar -xOzf "$M17_2_TAR" SHA256SUMS.txt > /tmp/m17_2_manifest.txt
tar -xOzf "$DIST/m17_3_minimal_script_patch.tar.gz" SHA256SUMS.txt > /tmp/m17_3_manifest.txt
diff /tmp/m17_2_manifest.txt /tmp/m17_3_manifest.txt || true

echo "=== confirm the 7 changed content files (names) ==="
diff /tmp/m17_2_manifest.txt /tmp/m17_3_manifest.txt | grep '^[<>]' | awk '{print $3}' | sort -u
