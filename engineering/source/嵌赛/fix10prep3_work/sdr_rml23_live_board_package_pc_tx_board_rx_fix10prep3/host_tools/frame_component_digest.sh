#!/usr/bin/env bash
# frame_component_digest.sh -- fix10prep3 WSL wrapper for the cross-arch training-frame
# component digest.  Compile-once + content-addressed cache keyed by (dependency
# closure + FLAGS + compiler identity), so any changed header / flag / toolchain builds
# a NEW binary instead of silently reusing a stale one.
#
#   frame_component_digest.sh --self-check
#   frame_component_digest.sh --frozen-dir DIR --source-index N --target-rms RMS \
#       --out-dir DIR --source-root DIR
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

CXX="${CXX:-g++}"
# Identical flags to host_tests/build_host_tests.sh (host = WSL g++, -Werror).
FLAGS="-std=gnu++17 -O2 -Wall -Wextra -Werror -I../board_package -I../sdr_adapter -I../ui_sw"
SRC="frame_component_digest.cpp"
CACHE_DIR="${FRAME_DIGEST_CACHE:-.frame_digest_cache}"

mkdir -p "$CACHE_DIR"

# Content-addressed cache key = dependency closure + FLAGS + compiler identity.
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
BIN="$CACHE_DIR/frame_component_digest.$TOOL_SHA"

if [ ! -x "$BIN" ]; then
    "$CXX" $FLAGS "$SRC" -o "$BIN"
fi

exec "$BIN" "$@"
