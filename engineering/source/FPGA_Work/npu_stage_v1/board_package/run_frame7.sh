#!/usr/bin/env bash
# Single-frame NPU inference: frame 7 = first meaningful case (BPSK +20 dB).
# Frame 0 is OOD/degenerate and is NOT the first meaningful test.
#
# This script only runs the compiled model. It does NOT write QSPI, does NOT
# modify SD boot, does NOT update the system, does NOT install packages, does
# NOT download a bitstream, and does NOT auto-retry.
set -euo pipefail
cd "$(dirname "$0")"

BIN="${NPU_SMOKE_BIN:-./build/npu_only_smoke}"
if [ ! -x "$BIN" ] && [ -x ./npu_only_smoke ]; then BIN=./npu_only_smoke; fi

exec "$BIN" --model model.json --raw model.raw \
            --tensor expected_tensor_plddr.bin \
            --frame 7 --reference reference_argmax.txt
