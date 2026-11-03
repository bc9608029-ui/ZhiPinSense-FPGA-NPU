#!/usr/bin/env bash
# run_display_integrity_test.sh -- Task B (HDMI dirty-frame / tearing) board test.
#
# Drives board_ui_live_12class in its two display-integrity modes:
#
#   diagnostic   Read-only probe (no register writes).  Maps the framebuffer,
#                enforces the frame_ctrl version gate, and prints DISPLAY_DIAGNOSTIC
#                (phys / capacity / frame_bytes / version / h_sync / v_sync /
#                vtc_enable / disable_hdmi) then exits 0.  This proves the FB map +
#                version gate before any write is attempted (the B4 bring-up audit).
#
#   static       Static-frame hold.  Runs the full render -> sync -> flip -> swap
#                path on a fixed frame at --display-refresh-hz, so a tear in the flip
#                path is separable from a tear caused by the live data feed.  Holds
#                until Ctrl-C (SIGINT) then exits 0.
#
#   ./run_display_integrity_test.sh              # diagnostic first, then static
#   ./run_display_integrity_test.sh diagnostic   # read-only probe only
#   ./run_display_integrity_test.sh static       # static-frame hold only
#   DISPLAY_REFRESH_HZ=60 ./run_display_integrity_test.sh static
#
# Needs root to map /dev/mem + /dev/udmabuf0 (run as root, same as run_ui_live.sh).
# No other UI server may be running (the data socket /run/sdr_amr_ui.sock is bound).
set -euo pipefail
. "$(dirname "$0")/common.sh"

BIN="$(require_bin board_ui_live_12class)"
SOCK="/run/sdr_amr_ui.sock"
REFRESH="${DISPLAY_REFRESH_HZ:-30}"

run_diagnostic() {
    banner "Display integrity: read-only diagnostic (no register writes)"
    # --no-touch keeps the probe free of touch enumeration noise.
    "$BIN" --sock="$SOCK" --display-diagnostic --no-touch
}

run_static() {
    banner "Display integrity: static-frame flip/tear hold at ${REFRESH} Hz (Ctrl-C to stop)"
    "$BIN" --sock="$SOCK" --display-static --display-refresh-hz="$REFRESH" --no-touch
}

case "${1:-all}" in
    diagnostic) run_diagnostic ;;
    static)     run_static ;;
    all)
        run_diagnostic
        run_static
        ;;
    *)
        echo "usage: $0 [diagnostic|static|all]" >&2
        exit 2
        ;;
esac
