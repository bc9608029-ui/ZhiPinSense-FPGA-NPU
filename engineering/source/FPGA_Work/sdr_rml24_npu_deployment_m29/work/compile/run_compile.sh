#!/usr/bin/env bash
# Reproduce the iCraft 3.39 compile of the RML2018 24-class raw-I/Q NPU partition.
# Tool: C:/Icraft/CLI v3.39.0/bin/icraft.exe  (Vivado is NOT involved here)
# Config: compile_config.toml (single-input ONNX [1,2,1024] -> logits [1,24])
#
# Pipeline: parse -> optimize -> quantize -> adapt -> generate
# Final artifact: jsonraw/model_24class_ZG.json + model_24class_ZG.raw
#
# Runs from Git Bash (Windows exe + Windows paths in the toml).
set -euo pipefail

# iCraft's HostBackend (CPU forward engine, libtorch) resolves its install root
# from GetModuleFileName of the spawned sub-tool.  Its native `std::ifstream`
# fails to open `poly_params.json` whenever the RESOLVED install path contains a
# space (`C:\Icraft\CLI v3.39.0\bin\...`).  Directory symlinks/junctions at
# space-free paths still resolve to that space-containing target, so they fail
# the same way.  The fix is a REAL space-free COPY of the install (no reparse
# point).  Create it once with:
#   robocopy "C:\Icraft\CLI v3.39.0" "D:\icraft" /E /XF *.pdb /NFL /NDL /NJH /NP
# See M29 audit §八 (Phase D toolchain note).
ICRAFT_COPY="D:/icraft"
if [ ! -f "$ICRAFT_COPY/bin/icraft.exe" ] || [ ! -f "$ICRAFT_COPY/bin/poly_params.json" ]; then
  echo "ERROR: space-free iCraft copy $ICRAFT_COPY is missing." >&2
  echo "       Create it with:  robocopy \"C:/Icraft/CLI v3.39.0\" \"D:/icraft\" /E /XF *.pdb /NFL /NDL /NJH /NP" >&2
  exit 1
fi
ICRAFT="$ICRAFT_COPY/bin/icraft.exe"
export PATH="$ICRAFT_COPY/bin:$PATH"

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

echo "DONE. Final artifact: jsonraw/model_24class_ZG.json + model_24class_ZG.raw"
ls -la jsonraw/ 2>/dev/null || true
