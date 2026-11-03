#!/usr/bin/env bash
# build_force_classify_wl.sh -- fix10class24-dualsdr-repeat3-audit1 Phase B/C
# Compile the wide-linear-corrected force classifier against the FROZEN production tree
# (read-only; no production file is modified).  Run INSIDE WSL.
#
#   MSYS_NO_PATHCONV=1 wsl.exe bash /mnt/f/.../cpp/build_force_classify_wl.sh
set -euo pipefail

# Frozen production tree (read-only baseline).
PROD="/mnt/f/嵌赛/fix10class24_tx_rms_sweep1_work/sdr_rml24_fix10class24_tx_rms_sweep1"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CXX="${CXX:-g++}"
# Identical flags to host_tools/replay_fix10class24_failed_rx_force_classify.sh,
# PLUS -I<PROD>/host_tools (this tool lives outside the production tree, so the
# replay24:: helper header must be found via an include path).
FLAGS="-std=gnu++17 -O2 -Wall -Wextra -Werror \
  -I$PROD/board_package -I$PROD/sdr_adapter -I$PROD/ui_sw -I$PROD/host_tools"
SRC="$HERE/replay_fix10class24_force_classify_wl.cpp"
RESAMPLER="$PROD/sdr_adapter/resampler.cpp"   # sdr::StreamResampler (PreprocessChain)
OUT="$HERE/bin/replay_fix10class24_force_classify_wl"

mkdir -p "$HERE/bin"
"$CXX" $FLAGS "$SRC" "$RESAMPLER" -o "$OUT"
echo "BUILD_OK $OUT"
