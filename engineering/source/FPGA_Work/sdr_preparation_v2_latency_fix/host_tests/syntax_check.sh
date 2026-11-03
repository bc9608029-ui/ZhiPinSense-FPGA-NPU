#!/usr/bin/env bash
# -fsyntax-only checks for the two board sources against the iCraft 3.39 headers.
# This verifies host-side syntax only (no link, no board toolchain).  A board
# link/run is still required on hardware: "host syntax verified" is NOT a board
# build pass.
#
# The iCraft headers are passed via -isystem so their own warnings are suppressed
# and any -Wall -Wextra -Werror diagnostic can only come from OUR sources.
set -euo pipefail

INC="/mnt/f/嵌赛/audit/icraft_3_39/usr/include"
PKG="/mnt/f/FPGA_Work/sdr_preparation_v2_latency_fix/board_package"

g++ -std=gnu++17 -fsyntax-only -Wall -Wextra -Werror \
    -isystem "$INC" -I"$PKG" \
    "$PKG/continuous_joint_stress_baseline_diag.cpp"
echo "baseline_diag: syntax OK"

g++ -std=gnu++17 -fsyntax-only -Wall -Wextra -Werror \
    -isystem "$INC" -I"$PKG" \
    "$PKG/continuous_joint_stress_fixed.cpp"
echo "fixed: syntax OK"
