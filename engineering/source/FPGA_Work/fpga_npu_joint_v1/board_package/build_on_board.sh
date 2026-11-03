#!/usr/bin/env bash
# Board-side build of the FPGA -> NPU joint correctness smoke program.
# Run this ON the FMQL30TAI Linux image (aarch64) after the bitstream is confirmed.
# The on-chip iCraft 3.39 package must provide /usr/cmake/icraft-zg330backend*.cmake
# and /usr/cmake/icraft-hostbackend*.cmake. Built with -std=gnu++17 and linked
# against Icraft::ZG330Backend + Icraft::HostBackend. Any build failure stops
# the script immediately (set -e).
set -euo pipefail

cd "$(dirname "$0")"

rm -rf build && mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j"$(nproc)" fpga_npu_joint_smoke

echo "Built: $(pwd)/fpga_npu_joint_smoke"
