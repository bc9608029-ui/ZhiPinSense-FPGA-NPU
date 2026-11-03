#!/usr/bin/env bash
# common_rml23.sh -- shared shell helpers for the RML23 (M29 Phase F5) live run
# scripts.  Mirrors common.sh but points at the frozen expA_bf16_head model and
# the RML23 binaries; it NEVER modifies common.sh or the 12-class chain.
#
# Sourced (never executed directly) by scripts/run_gate9_rml23.sh,
# start_live_rml23.sh, test_live_*.sh, check_live_result.sh and the other RML23
# entry points.  It only resolves paths and prints a banner; it does NOT add any
# logging or serial I/O to the producer's hot path (the v3 lesson: serial
# observer effect).  The producer's own single GATE_RESULT line is the source of
# truth, printed straight to stdout and exited through unchanged.

set -euo pipefail

# Package root = one level above scripts/.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Where the built gate binaries live.  Override with BIN_DIR=/path if needed.
BIN_DIR="${BIN_DIR:-$ROOT/bin}"

# Frozen expA_bf16_head model artifacts (authoritative, read from the frozen
# sidecar).  The model is the 24-class source; the 24->23 AM-SSB merge is done in
# software by the producer (board_package/rml23_merged.hpp).
MODEL_JSON="$ROOT/model_rml23/model_24class_ZG.json"
MODEL_RAW="$ROOT/model_rml23/model_24class_ZG.raw"
MODEL_RAW_SHA="$(awk '$2 == "model_24class_ZG.raw" || $2 == "*model_24class_ZG.raw" {print $1}' \
    "$ROOT/model_rml23/model_rml23.sha256" | head -n 1)"

# Distinct RML23 sockets so a simultaneously-running 12-class chain can never be
# crossed.  The producer writes result frames to UI_SOCK and owns CTL_SOCK; the
# UI server listens on UI_SOCK and connects (client) to CTL_SOCK.
UI_SOCK="/run/sdr_amr_ui_rml23.sock"
CTL_SOCK="/run/sdr_amr_control_rml23.sock"

# Authoritative combined bitstream (frozen; used only as provenance).  Never
# re-programmed by any script.  Same bitstream as the 12-class chain.
BITSTREAM_SHA="22fec95c64f3db727dd250e5768cdadec82f4c4d2de088392980b95a632932e9"

# Deployment golden set (offline phase inputs + expected_argmax.tsv).
GOLDEN="$ROOT/deployment_golden"

# Locate a gate binary in BIN_DIR, failing with a clear message if not built.
require_bin() {
    local name="$1"
    local bin="$BIN_DIR/$name"
    if [ ! -x "$bin" ]; then
        echo "ERROR: $bin not found or not executable." >&2
        echo "       Build it first:  ./board_package/build_ui_live_rml23.sh  (UI server)" >&2
        echo "                        ./board_package/build_npu_on_board.sh --gate9-rml23  (producer)" >&2
        echo "       then copy the output into $BIN_DIR/." >&2
        exit 2
    fi
    printf '%s\n' "$bin"
}

# Ensure the dynamic loader can find libiio when LIBIIO_ROOT is set.  The RML23
# producer links the REAL libiio backend (no Mock fallback on board), so
# libiio.so must resolve at run time.  The build bakes an rpath in too; this is a
# second layer and fails closed (non-zero) if the library is missing.  When
# LIBIIO_ROOT is unset it is a no-op (rpath / system path apply).
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
