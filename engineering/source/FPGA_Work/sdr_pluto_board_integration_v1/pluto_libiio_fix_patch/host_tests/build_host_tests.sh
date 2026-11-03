#!/usr/bin/env bash
# Build every host/board unit test for sdr_adapter (gnu++17, -Werror).
# No iCraft, no SDR, no board, no libiio required.  Exits nonzero on any failure.
set -euo pipefail
cd "$(dirname "$0")"

CXX="${CXX:-g++}"
FLAGS="-std=gnu++17 -Wall -Wextra -Werror -O2 -I../sdr_adapter"

# Regression suite (reused v1 system-layer groups + extended category contract).
"$CXX" $FLAGS test_all.cpp ../sdr_adapter/iq_source.cpp -o test_all

# Core SDR modules (this batch's new primitives).
"$CXX" $FLAGS test_nco.cpp -o test_nco
"$CXX" $FLAGS test_attr_routing.cpp -o test_attr_routing   # header-only
"$CXX" $FLAGS test_receiver_scale.cpp -o test_receiver_scale
"$CXX" $FLAGS test_rx_format.cpp -o test_rx_format
"$CXX" $FLAGS test_resampler.cpp ../sdr_adapter/resampler.cpp -o test_resampler
"$CXX" $FLAGS test_sample_rate_negotiate.cpp ../sdr_adapter/sample_rate_negotiate.cpp \
    -o test_sample_rate_negotiate
"$CXX" $FLAGS test_pluto_tx.cpp ../sdr_adapter/pluto_tx.cpp -o test_pluto_tx

echo "build_host_tests.sh: all binaries built OK"
