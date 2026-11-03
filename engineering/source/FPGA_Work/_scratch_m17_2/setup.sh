#!/usr/bin/env bash
set -euo pipefail
D=/mnt/f/FPGA_Work/sdr_full_chain_12class_ui_v3_m17_2
mkdir -p "$D"
tar -xzf /mnt/f/FPGA_Work/sdr_full_chain_12class_ui_v3_m17_1/dist/sdr_full_chain_12class_ui_v3_board_package_m17_1.tar.gz -C "$D"
echo "=== top level ==="
ls -la "$D"
echo "=== file count ==="
find "$D" -type f | wc -l
echo "=== sha256sum -c (verify M17.1 baseline intact) ==="
( cd "$D/sdr_full_chain_12class_ui_v3_board_package_m17_1" && sha256sum -c SHA256SUMS.txt | tail -n 1 )
