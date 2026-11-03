#!/usr/bin/env bash
# common.sh -- shared shell helpers for the twelve-class Gate 6-9 run scripts.
#
# Sourced (never executed directly) by scripts/run_gate{6,7,8,9}.sh.  It only
# resolves paths and prints a banner; it does NOT add any logging or serial I/O
# to the gate program's hot path (the v3 lesson: serial observer effect).  The
# gate binary's own single GATE_RESULT line is the source of truth, printed
# straight to stdout and exited through unchanged.

set -euo pipefail

# Package root = one level above scripts/.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Where the built gate binaries live.  Override with BIN_DIR=/path if needed.
BIN_DIR="${BIN_DIR:-$ROOT/bin}"

# Model artifacts (authoritative, read from the frozen sidecar).
MODEL_JSON="$ROOT/model_12class/model_12class.json"
MODEL_RAW="$ROOT/model_12class/model_12class.raw"
MODEL_RAW_SHA="$(awk '{print $1}' "$ROOT/model_12class/model_12class.sha256")"

# Authoritative combined bitstream (frozen; used only as provenance in the Gate 10
# dump-error manifest).  Never re-programmed by any script.
BITSTREAM_SHA="22fec95c64f3db727dd250e5768cdadec82f4c4d2de088392980b95a632932e9"

# Deployment golden set.
GOLDEN="$ROOT/deployment_golden"

# Locate a gate binary in BIN_DIR, failing with a clear message if not built.
require_bin() {
    local name="$1"
    local bin="$BIN_DIR/$name"
    if [ ! -x "$bin" ]; then
        echo "ERROR: $bin not found or not executable." >&2
        echo "       Build it first:  ./board_package/build_on_board.sh  (Gate 6/8)" >&2
        echo "                        ./board_package/build_npu_on_board.sh  (Gate 7/9)" >&2
        echo "       then copy the output into $BIN_DIR/ (see scripts/package_board_release.sh)." >&2
        exit 2
    fi
    printf '%s\n' "$bin"
}

# Ensure the dynamic loader can find libiio when LIBIIO_ROOT is set.  Gate 6 /
# Gate 9 / the §九 calibrator link the REAL libiio backend (no Mock fallback on
# board), so libiio.so must resolve at run time.  The builds bake an rpath in
# too; this is a second layer and fails closed (non-zero) if the library is
# missing.  When LIBIIO_ROOT is unset it is a no-op (rpath / system path apply).
require_libiio_runtime() {
    if [ -z "${LIBIIO_ROOT:-}" ]; then
        return 0
    fi
    local so="${LIBIIO_ROOT}/lib/libiio.so"
    if [ ! -f "$so" ]; then
        echo "ERROR: libiio runtime library not found: $so" >&2
        echo "       Set LIBIIO_ROOT=/path/to/libiio (e.g. /tmp/sdr_pluto_gate1_5/libiio-arm64)." >&2
        return 2
    fi
    export LD_LIBRARY_PATH="${LIBIIO_ROOT}/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
    return 0
}

banner() {
    echo "== $1 =="
    echo "   root=$ROOT"
    echo "   model_sha=$MODEL_RAW_SHA"
}
