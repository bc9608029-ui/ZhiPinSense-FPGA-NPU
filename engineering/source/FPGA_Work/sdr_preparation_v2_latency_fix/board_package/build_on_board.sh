#!/usr/bin/env bash
# Board-side build of the continuous joint stress program.
# Run this ON the FMQL30TAI Linux image (aarch64) after the bitstream is confirmed.
# The on-chip iCraft 3.39 package must provide /usr/cmake/icraft-zg330backend*.cmake
# and /usr/cmake/icraft-hostbackend*.cmake. Built with -std=gnu++17 and linked
# against Icraft::ZG330Backend + Icraft::HostBackend. Any build failure stops
# the script immediately (set -e).
set -euo pipefail

cd "$(dirname "$0")"

rm -rf build && mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
# Build the three programs: the v1-equivalent stress, the baseline diagnostic
# (timing/RSS/counters only), and the fixed (input-reuse) diagnostic.
make -j"$(nproc)" continuous_joint_stress continuous_joint_stress_baseline_diag continuous_joint_stress_fixed

echo "Built: $(pwd)/continuous_joint_stress"
echo "Built: $(pwd)/continuous_joint_stress_baseline_diag"
echo "Built: $(pwd)/continuous_joint_stress_fixed"
