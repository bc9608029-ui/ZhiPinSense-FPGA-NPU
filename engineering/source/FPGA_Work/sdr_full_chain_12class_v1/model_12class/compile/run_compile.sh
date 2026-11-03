#!/usr/bin/env bash
# Reproduce the iCraft 3.39 compile of the twelve-class raw-I/Q NPU partition.
# Tool: C:/Icraft/CLI v3.39.0/bin/icraft.exe  (Vivado 2018.3 is NOT involved here)
# Config: compile_config.toml (single-input ONNX [1,2,1024] -> logits [1,12])
#
# Pipeline: parse -> optimize -> quantize -> adapt -> generate
# Final artifact: jsonraw/model_12class_ZG.json + model_12class_ZG.raw
#
# Runs from Git Bash (Windows exe + Windows paths in the toml).
set -euo pipefail

ICRAFT="C:/Icraft/CLI v3.39.0/bin/icraft.exe"
cd "$(dirname "$0")"
mkdir -p jsonraw logs

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

echo "DONE. Final artifact: jsonraw/model_12class_ZG.json + model_12class_ZG.raw"
ls -la jsonraw/ 2>/dev/null || true
