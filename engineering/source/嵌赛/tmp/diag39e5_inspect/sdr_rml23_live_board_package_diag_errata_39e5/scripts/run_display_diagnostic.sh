#!/usr/bin/env bash
# run_display_diagnostic.sh -- M18-0 display root-cause diagnostic runner.
#
#   ./run_display_diagnostic.sh [a|b|c|d] [--switch-hz=1.0] [--hold-sec=0]
#
# Runs board_display_diagnostic in one of the four M18-0 diagnostic modes:
#   a  black-clear + static hold   (Q7: uninitialised-buffer stripes)
#   b  single-buffer lock, no flip (Q4/Q6: dynamic band without the flip path)
#   c  red/blue low-freq switch     (Q3/Q8: flip/CDC cleanliness + which buffer)
#   d  pre/post submit CRC          (Q5: write + sync_for_device link; no screen)
#
# a/b/c hold the display until Ctrl-C (SIGINT) and print DISPLAY_DIAG_TOOL_<X>
# result=READY / STOPPED.  d prints result=PASS/FAIL with the two CRCs and exits.
#
# Needs root (maps /dev/mem + /dev/udmabuf0).  No other UI server may be running.
set -euo pipefail
. "$(dirname "$0")/common.sh"

BIN="$BIN_DIR/board_display_diagnostic"
if [ ! -x "$BIN" ]; then
    echo "ERROR: $BIN not found or not executable." >&2
    echo "       Build it first:  ./board_package/build_display_diagnostic.sh g++" >&2
    exit 2
fi

MODE="${1:-}"
case "$MODE" in
    a|b|c|d) ;;
    A|B|C|D) MODE="$(printf '%s' "$MODE" | tr 'ABCD' 'abcd')" ;;
    *) echo "usage: $0 [a|b|c|d] [--switch-hz=1.0] [--hold-sec=0]" >&2; exit 2 ;;
esac
shift

banner "M18-0 display root-cause diagnostic (mode=$MODE)"
exec "$BIN" --mode="$MODE" "$@"
