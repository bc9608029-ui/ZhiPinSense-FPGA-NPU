#!/usr/bin/env bash
# Build and run the sdr_adapter unit tests (host or board; gnu++17).
# No iCraft, no SDR, no board required.  Exits nonzero on any failure.
set -euo pipefail
cd "$(dirname "$0")"

g++ -std=gnu++17 -Wall -Wextra -O2 \
    -I../sdr_adapter \
    test_all.cpp ../sdr_adapter/iq_source.cpp \
    -o test_all

./test_all
