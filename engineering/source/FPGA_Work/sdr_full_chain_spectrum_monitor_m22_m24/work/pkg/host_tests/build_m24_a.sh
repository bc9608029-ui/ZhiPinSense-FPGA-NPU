#!/usr/bin/env bash
# build_m24_a.sh -- build the M24-A host test with -O2 -Wall -Wextra -Werror.
set -euo pipefail
cd "$(dirname "$0")"

CXX="${CXX:-g++}"
FLAGS="-std=gnu++17 -O2 -Wall -Wextra -Werror -I../sdr_adapter"

mkdir -p ../build/m24
"$CXX" $FLAGS test_m24_a.cpp -o ../build/m24/test_m24_a

echo "BUILD_M24_A_OK"
