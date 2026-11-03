#!/usr/bin/env bash
# replay_fix10class24_failed_rx_force_classify.sh -- fix10class24-rxresidual-audit1 Phase B/C
# WSL wrapper: compile-once + content-addressed cache, then exec.
#
# Forces a gate-bypassed provisional recovery + verbatim classification chain from a
# failed-RX dump, exports 5 diagnostic files.  Never touches the board.
#
#   replay_fix10class24_failed_rx_force_classify.sh --self-test --clean24-dir DIR [--source-index N]
#   replay_fix10class24_failed_rx_force_classify.sh --dump-dir <capture>/failed_rx/<idx> \
#         --clean24-dir DIR --export-dir DIR
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

CXX="${CXX:-g++}"
# Identical flags to host_tests/build_host_tests.sh (host = WSL g++, -Werror).
FLAGS="-std=gnu++17 -O2 -Wall -Wextra -Werror -I../board_package -I../sdr_adapter -I../ui_sw"
SRC="replay_fix10class24_failed_rx_force_classify.cpp"
RESAMPLER="../sdr_adapter/resampler.cpp"   # sdr::StreamResampler (PreprocessChain)
CACHE_DIR="${FORCE_CLASSIFY_CACHE:-.force_classify_cache}"
mkdir -p "$CACHE_DIR"

DEPS="$("$CXX" $FLAGS -MM "$SRC" | tr -d '\\\n' | sed 's/^[^:]*: //; s/[[:space:]][[:space:]]*/ /g')"
DEP_HASHES="$(printf '%s\n' $DEPS | xargs sha256sum)"
RESAMPLER_SHA="$(sha256sum "$RESAMPLER" | cut -d' ' -f1)"
COMPILER_ID="$("$CXX" --version | head -n 1)"
TOOL_SHA="$(
  {
    printf 'FLAGS=%s\n' "$FLAGS"
    printf 'COMPILER=%s\n' "$COMPILER_ID"
    printf 'RESAMPLER=%s\n' "$RESAMPLER_SHA"
    printf '%s\n' "$DEP_HASHES"
  } | sha256sum | cut -d' ' -f1
)"
BIN="$CACHE_DIR/replay_fix10class24_failed_rx_force_classify.$TOOL_SHA"
if [ ! -x "$BIN" ]; then
  "$CXX" $FLAGS "$SRC" "$RESAMPLER" -o "$BIN"
fi
exec "$BIN" "$@"
