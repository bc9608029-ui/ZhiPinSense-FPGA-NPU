#!/usr/bin/env bash
# mode_ctl.sh -- send one command to the Gate 9 producer's reverse control channel.
#
#   ./mode_ctl.sh SET_MODE AUTO_LOCK
#   ./mode_ctl.sh --sock=/run/sdr_amr_control.sock STATUS
#   ./mode_ctl.sh STOP
#
# Thin wrapper over board_mode_ctl: resolves the binary and forwards every
# argument unchanged.  Exit code mirrors the client (0 = "OK" reply, 1 = "ERR"
# reply or send/recv failure, 2 = connect failure).
set -euo pipefail
. "$(dirname "$0")/common.sh"

BIN="$(require_bin board_mode_ctl)"
exec "$BIN" "$@"
