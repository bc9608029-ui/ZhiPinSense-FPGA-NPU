#!/usr/bin/env bash
set -euo pipefail
FULL=/mnt/f/FPGA_Work/_scratch_m17_2/build/verify/sdr_full_chain_12class_ui_v3_board_package_m17_2
DIST=/mnt/f/FPGA_Work/sdr_full_chain_12class_ui_v3_m17_2/dist

echo "=== sha256sum -c on M17.2 full package ==="
cd "$FULL"
SUM=$(sha256sum -c SHA256SUMS.txt 2>&1)
echo "$SUM" | grep -E 'FAILED|FAILED open|No such' && echo "!!! FOUND FAILURES" || echo "no FAILED lines"
echo "OK count: $(echo "$SUM" | grep -c ': OK')"
echo "total listed: $(wc -l < SHA256SUMS.txt)"

echo "=== dist/ entries inside full package (expect 0) ==="
tar -tzf "$DIST/sdr_full_chain_12class_ui_v3_board_package_m17_2.tar.gz" | grep -c 'dist/' || echo 0

echo "=== patch tarball file list ==="
tar -tzf "$DIST/m17_2_touch_acceptance_harden_patch.tar.gz"

echo "=== patch SHA256SUMS.txt line count (expect 427 = full manifest) ==="
tar -xOzf "$DIST/m17_2_touch_acceptance_harden_patch.tar.gz" SHA256SUMS.txt | wc -l
