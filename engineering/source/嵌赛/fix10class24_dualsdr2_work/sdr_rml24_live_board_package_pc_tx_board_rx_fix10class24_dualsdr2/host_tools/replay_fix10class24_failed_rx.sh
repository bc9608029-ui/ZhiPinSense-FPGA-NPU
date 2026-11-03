#!/usr/bin/env bash
# replay_fix10class24_failed_rx.sh -- fix10class24-dualsdr2 Phase C offline replayer
# WSL wrapper: compile-once + content-addressed cache, then exec.
#
# The replayer reproduces the board's 24-class BF16 dual-SDR recovery from a
# failed_rx/<source_index>/ dump (produced by the runner under --dump-failed-rx) using
# the UNCHANGED production C++ recovery functions.  It never touches the board.
#
#   replay_fix10class24_failed_rx.sh --self-test
#   replay_fix10class24_failed_rx.sh --dump-dir failed_rx/1500 [--curves] [--fractional-den 512]
#   replay_fix10class24_failed_rx.sh --dump-dir failed_rx/1500 --canonical-reference [--canonical-file FILE]
#   replay_fix10class24_failed_rx.sh --canonical-vs-runtime
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

CXX="${CXX:-g++}"
# Identical flags to host_tests/build_host_tests.sh (host = WSL g++, -Werror).
FLAGS="-std=gnu++17 -O2 -Wall -Wextra -Werror -I../board_package -I../sdr_adapter -I../ui_sw"
SRC="replay_fix10class24_failed_rx.cpp"
CACHE_DIR="${REPLAY24_CACHE:-.replay24_cache}"
mkdir -p "$CACHE_DIR"

# Full preprocessor dependency closure so any change to a recovery header invalidates
# the cached binary (same scheme as build_burst_cli.sh).
DEPS="$("$CXX" $FLAGS -MM "$SRC" | tr -d '\\\n' | sed 's/^[^:]*: //; s/[[:space:]][[:space:]]*/ /g')"
DEP_HASHES="$(printf '%s\n' $DEPS | xargs sha256sum)"
COMPILER_ID="$("$CXX" --version | head -n 1)"
TOOL_SHA="$(
  {
    printf 'FLAGS=%s\n' "$FLAGS"
    printf 'COMPILER=%s\n' "$COMPILER_ID"
    printf '%s\n' "$DEP_HASHES"
  } | sha256sum | cut -d' ' -f1
)"
BIN="$CACHE_DIR/replay_fix10class24_failed_rx.$TOOL_SHA"
if [ ! -x "$BIN" ]; then
  "$CXX" $FLAGS "$SRC" -o "$BIN"
fi
exec "$BIN" "$@"
