#!/usr/bin/env bash
# Standalone build of the M23 P0 offline module tests.
#
# Does NOT touch M22's build_host_tests.sh / run_tests.sh or their outputs; it
# builds only test_m23_p0 into bin/test_m23_p0 and links the M20 OOD-U detector
# (the single .cpp the switchable interface depends on).  iCraft-free, libiio-free.
set -euo pipefail
cd "$(dirname "$0")"

CXX="${CXX:-g++}"
FLAGS="-std=gnu++17 -O2 -Wall -Wextra -Werror -I../board_package -I../sdr_adapter -I../ui_sw"

mkdir -p bin

echo "== build test_m23_p0 =="
$CXX $FLAGS test_m23_p0.cpp ../sdr_adapter/ood_u_detector.cpp -o bin/test_m23_p0

echo "build_m23_p0.sh: OK -> host_tests/bin/test_m23_p0"
