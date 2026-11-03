#!/usr/bin/env bash
# Reproduce the iCraft 3.39 compile of the frozen NPU partition.
# Tool: C:/Icraft/CLI v3.39.0/bin/icraft.exe  (Vivado 2018.3 is NOT involved here)
# Config: compile_config.toml (frozen ONNX -> ZG330 / zhuge)
#
# Pipeline: parse -> optimize -> quantize -> adapt -> generate
# Final artifact: jsonraw/rfnet_npu_ZG.json + rfnet_npu_ZG.raw
set -euo pipefail

ICRAFT="C:/Icraft/CLI v3.39.0/bin/icraft.exe"
cd "$(dirname "$0")"

echo "[1/5] parse"
"$ICRAFT" parse compile_config.toml
echo "[2/5] optimize"
"$ICRAFT" optimize compile_config.toml
echo "[3/5] quantize"
"$ICRAFT" quantize compile_config.toml
echo "[4/5] adapt"
"$ICRAFT" adapt compile_config.toml
echo "[5/5] generate"
"$ICRAFT" generate compile_config.toml

echo "DONE. Final artifact: jsonraw/rfnet_npu_ZG.json + rfnet_npu_ZG.raw"
