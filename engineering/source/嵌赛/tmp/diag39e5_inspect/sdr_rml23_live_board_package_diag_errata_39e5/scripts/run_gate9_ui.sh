#!/usr/bin/env bash
# run_gate9_ui.sh -- Gate 9 (NPU) -> socket -> LIVE UI server -> HDMI screen,
# UNLOCKED under the combined NPU+HDMI bitstream (sdr_full_chain_12class_combined_v1).
#
# Under the combined bitstream BOTH the NPU (axi://zg330aiu?npu=0x40000000&dma=
# 0x80000000) and the HDMI framebuffer (frame_ctrl@0x40080000, version 0x20230218)
# are present in ONE image, so a real LIVE NPU -> screen chain runs on a single
# board in a single load.  (The old ui_v1 "FULL_CHAIN_UI_BLOCKED" verdict applied
# only to the HDMI-only / NPU-only bitstreams; it is superseded by this combined
# bitstream and is NOT copied into this project.)
#
# Combined-bitstream identity is enforced FAIL-CLOSED by the two existing checks,
# in order (no new RTL, no new binary, no Mock/Golden fallback):
#
#   HDMI present (C2) -> run_ui_live.sh only reports UI_LIVE_READY after
#       bind/listen AND the frame_ctrl version gate (0x40080000+0x0C ==
#       0x20230218) passes.  The socket existing here therefore implies HDMI is
#       present in this bitstream.
#   NPU  present (C1) -> run_gate9.sh -> board_gate9_full_chain_12class opens the
#       NPU via iCraft Device::Open(axi://zg330aiu?npu=0x40000000&dma=0x80000000).
#       Under an HDMI-only bitstream that throws and the binary exits 2
#       (device-not-found).  The model is @zhuget(330): there is no HostBackend /
#       Mock fallback in the classify path.
#
# Usage:
#   ./run_gate9_ui.sh [--phase=offline|digital|rf] [--sock=/path] [gate9 args...]
#
#   offline  replay golden inputs -> NPU -> UI   (strongest NPU -> screen proof)
#   digital  Pluto digital loopback -> NPU -> UI (chain liveness, never classif.)
#   rf       external RF loopback -- REQUIRES --confirm-safe-rf-path (refused
#            otherwise; the gate9 binary enforces it)
#
# Exit: 2 = UI socket not ready (start run_ui_live.sh first); else the gate9
#       binary's own exit code (0/1/2 = pass / fail / device-not-found).
set -euo pipefail
. "$(dirname "$0")/common.sh"

# Resolve --sock from the args (later occurrence wins, mirroring get_opt).
SOCK=/run/sdr_amr_ui.sock
for a in "$@"; do
    case "$a" in
        --sock=*) SOCK="${a#--sock=}" ;;
    esac
done

banner "Gate 9 -> screen (combined NPU+HDMI bitstream)"

# C2 (HDMI present): the UI server socket must already exist.  run_ui_live.sh
# only reports READY after the frame_ctrl version gate passes, so a socket here
# implies HDMI is present in this bitstream.
if [ ! -S "$SOCK" ]; then
    echo "UI_SOCKET_NOT_READY sock=$SOCK" >&2
    echo "  start the LIVE UI server first:  ./run_ui_live.sh --sock=$SOCK" >&2
    echo "  (run_ui_live.sh also enforces the HDMI frame_ctrl version gate.)" >&2
    exit 2
fi

# C1 (NPU present) is enforced by the gate9 binary's Device::Open, fail-closed.
# Wire the socket and defer the rest to run_gate9.sh (which passes "$@" through).
exec "$ROOT/scripts/run_gate9.sh" --sock="$SOCK" "$@"
