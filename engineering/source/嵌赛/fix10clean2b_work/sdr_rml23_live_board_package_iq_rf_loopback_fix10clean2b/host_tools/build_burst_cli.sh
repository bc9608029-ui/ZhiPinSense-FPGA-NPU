#!/usr/bin/env bash
# build_burst_cli.sh -- fix10prep2 WSL burst generator wrapper: compile-once + SHA cache.
#
# The PC TX service invokes this (via wsl.exe) to rebuild the training-frame burst from
# a frozen ci16.  g++ compiles the tool ONCE per (tool source + full preprocessor
# dependency closure) and caches the binary keyed by that SHA, so a per-START recompile
# never happens and a stale binary can never be reused silently.  The tool itself
# #include's the SAME h5 iq_rf_training_frame.hpp / iq_digital_loopback.hpp the board
# uses, so the PC and board derive byte-identical payload_sha_pre / payload_sha_post /
# burst_sha / tx_scale from the same frozen ci16 + --rf-tx-target-rms.
#
#   build_burst_cli.sh --self-check            # compile once (warm the cache), then verify
#   build_burst_cli.sh --ci16 FILE --complex-count N --expect-sha SHA \
#       --target-rms RMS --out-burst BIN --out-json JSON
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

CXX="${CXX:-g++}"
# Identical flags to host_tests/build_host_tests.sh (host = WSL g++, -Werror).
FLAGS="-std=gnu++17 -O2 -Wall -Wextra -Werror -I../board_package -I../sdr_adapter -I../ui_sw"
SRC="build_burst_cli.cpp"
CACHE_DIR="${BUILD_BURST_CACHE:-.build_burst_cache}"
BIN="$CACHE_DIR/build_burst_cli"

mkdir -p "$CACHE_DIR"

# Full preprocessor dependency closure (source + every transitively included header),
# so any change to a red-line header (iq_rf_training_frame.hpp, iq_digital_loopback.hpp,
# iq_pc_tx_board_rx_transfer_fix10.hpp, ...) invalidates the cached binary.
DEPS="$("$CXX" $FLAGS -MM "$SRC" | tr -d '\\\n' | sed 's/^[^:]*: //; s/[[:space:]][[:space:]]*/ /g')"
TOOL_SHA="$(printf '%s\n' $DEPS | xargs sha256sum | sha256sum | cut -d' ' -f1)"
STAMP="$CACHE_DIR/$TOOL_SHA.stamp"

if [ ! -x "$BIN" ] || [ ! -f "$STAMP" ]; then
    rm -f "$BIN"
    "$CXX" $FLAGS "$SRC" -o "$BIN"
    printf '%s\n' "$TOOL_SHA" > "$STAMP"
fi

exec "$BIN" "$@"
