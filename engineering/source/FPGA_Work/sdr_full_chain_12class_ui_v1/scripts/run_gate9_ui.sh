#!/usr/bin/env bash
# run_gate9_ui.sh -- Gate 9 (NPU) -> screen.  BLOCKED under the current bitstream.
#
# Gate 9 needs the NPU bitstream (axi://zg330aiu?npu=0x40000000&dma=0x80000000);
# the LIVE UI server needs the HDMI framebuffer bitstream (frame_ctrl@0x40080000,
# version 0x20230218).  These are TWO MUTUALLY EXCLUSIVE bitstreams -- the HDMI
# bitstream has no NPU, and there is NO verified NPU+HDMI merged bitstream (see
# docs/BITSTREAM_COMPAT_AUDIT.md).  A single board in a single bitstream therefore
# cannot run a LIVE NPU -> screen chain.
#
# This script FAILS CLOSED rather than faking LIVE:
#
#   FULL_CHAIN_UI_BLOCKED bitstream_incompatible      (exit non-zero)
#
# It does NOT run the NPU bitstream, then switch to the HDMI bitstream, and call
# that "LIVE".  The offline demo is a SEPARATE, honestly-labelled path
# (OFFLINE_REPLAY, never LIVE):
#   1. under the NPU bitstream:  ./run_gate9.sh --phase=offline --sock= > gate9.jsonl
#   2. switch to the HDMI bitstream, start the UI server (run_ui_live.sh)
#   3. replay gate9.jsonl into the socket (recorded-JSONL replay; NOT provided here)
#   -- or use run_gate8_ui_socket_test.sh, which replays golden logits -> socket ->
#      screen with no NPU and is already marked OFFLINE_REPLAY.
#
# Exit 3 = blocked (no such chain under this bitstream).
set -euo pipefail
. "$(dirname "$0")/common.sh"

banner "Gate 9 -> screen (BLOCKED under current bitstream)"
echo "FULL_CHAIN_UI_BLOCKED bitstream_incompatible" >&2
echo "reason=NPU_and_HDMI_are_mutually_exclusive_bitstreams_no_merged_bitstream" >&2
echo "offline_replay=use_run_gate8_ui_socket_test.sh_or_recorded_JSONL_replay_(OFFLINE_REPLAY_never_LIVE)" >&2
exit 3
