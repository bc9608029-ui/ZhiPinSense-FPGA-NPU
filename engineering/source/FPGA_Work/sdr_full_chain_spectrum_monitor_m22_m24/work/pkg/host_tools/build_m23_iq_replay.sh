#!/usr/bin/env bash
# Standalone build of the M23 P0 IQ replay / parameter-estimation tool.
#
# Links the M20 OOD-U detector + fail-closed manifest loader so the optional
# --ood-manifest switch works.  iCraft-free, libiio-free; does not touch M22.
set -euo pipefail
cd "$(dirname "$0")"

CXX="${CXX:-g++}"
FLAGS="-std=gnu++17 -O2 -Wall -Wextra -Werror -I../sdr_adapter"

mkdir -p bin

echo "== build m23_iq_replay =="
$CXX $FLAGS m23_iq_replay.cpp \
    ../sdr_adapter/ood_u_detector.cpp \
    ../sdr_adapter/ood_threshold_manifest.cpp \
    -o bin/m23_iq_replay

echo "build_m23_iq_replay.sh: OK -> host_tools/bin/m23_iq_replay"
