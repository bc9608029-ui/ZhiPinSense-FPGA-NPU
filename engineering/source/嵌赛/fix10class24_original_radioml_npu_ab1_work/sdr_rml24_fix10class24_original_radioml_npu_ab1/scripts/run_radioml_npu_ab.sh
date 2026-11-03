#!/usr/bin/env bash
# run_radioml_npu_ab.sh -- task fix10class24-original-radioml-npu-ab1 (board side)
# Re-feed the 480 frozen original-RadioML test frames to the REAL NPU
# (phase radioml-original-npu-ab-24class-bf16-fix10) and write per-frame raw-24
# argmax + 24-dim logits for the host-side Host-vs-NPU A/B.
#
# This is a MEASUREMENT, never a regression PASS.  Forbidden tokens it must never
# print on its own: RF_PASS, SMOKE_PASS, PROJECT_COMPLETE, FINAL_*, HOST_MATCH,
# HOST_DISAGREEMENT (the host judger owns those verdicts).  It never opens an SDR,
# never transmits, never re-captures, and uses the frozen 24-class BF16 model
# (NOT the 23-class ZG model that common_rml23.sh defaults to).
#
# The runner refuses a pre-existing --out-dir (fail-closed), so this script MUST
# NOT create $OUT_DIR before launching.  It tees the transcript to a sibling log
# and moves it into $OUT_DIR/run.log only after the runner has created the dir.
#
# Usage (run on the board, from the project root):
#   bash scripts/run_radioml_npu_ab.sh \
#       --input-dir=<unpacked input data package> \
#       --out-dir=/root/rml24_npu_ab_<timestamp>
#
# Required: <input data package> contains manifest.tsv + 480 .bin (the export
#           written by scripts/export_radioml_npu_ab_inputs.py; SHA256SUMS.txt is
#           verified separately by the operator, not by this script).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ---------------------------------------------------------------------------
# Frozen model identity (the 24-class BF16 model; NOT the 23-class ZG default).
# ---------------------------------------------------------------------------
MODEL_JSON="$ROOT/model_rml24_bf16/rml24_adamrv11_bf16.json"
MODEL_RAW="$ROOT/model_rml24_bf16/rml24_adamrv11_bf16.raw"
MODEL_RAW_SHA="c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"

INPUT_DIR=""
OUT_DIR=""

usage() {
    echo "Usage: $0 --input-dir=<input data package dir> --out-dir=<fresh out dir>" >&2
    exit 2
}

for arg in "$@"; do
    case "$arg" in
        --input-dir=*) INPUT_DIR="${arg#--input-dir=}" ;;
        --out-dir=*)   OUT_DIR="${arg#--out-dir=}" ;;
        *) echo "ERROR: unknown arg: $arg" >&2; usage ;;
    esac
done

# ---- fail-closed validation (mirrors the runner's own checks) ---------------
if [ -z "$INPUT_DIR" ]; then
    echo "ERROR: --input-dir=<input data package dir> is required." >&2; usage
fi
if [ ! -f "$INPUT_DIR/manifest.tsv" ]; then
    echo "ERROR: manifest.tsv not found in input dir: $INPUT_DIR" >&2; exit 2
fi
if [ -z "$OUT_DIR" ]; then
    echo "ERROR: --out-dir=<fresh dir> is required." >&2; usage
fi
if [ -e "$OUT_DIR" ]; then
    echo "ERROR: output dir already exists (refuse overwrite): $OUT_DIR" >&2
    echo "       Use a fresh timestamped dir, e.g. /root/rml24_npu_ab_\$(date +%s)." >&2
    exit 2
fi
if [ ! -f "$MODEL_JSON" ] || [ ! -f "$MODEL_RAW" ]; then
    echo "ERROR: frozen 24-class BF16 model artifacts missing under model_rml24_bf16/" >&2
    exit 2
fi

# ---- transcript (sibling of $OUT_DIR; moved inside after the runner creates it) ----
LOG="${OUT_DIR}.run.log"

echo "RADIOML_ORIGINAL_NPU_AB_START input_dir=$INPUT_DIR out_dir=$OUT_DIR model_sha=$MODEL_RAW_SHA"
echo "RADIOML_ORIGINAL_NPU_AB_SAFETY no_sdr no_tx no_recapture fixed_480 real_npu_only"

set +e
bash "$ROOT/scripts/run_gate9_rml23.sh" \
    --phase=radioml-original-npu-ab-24class-bf16-fix10 \
    --model-json="$MODEL_JSON" \
    --model-raw="$MODEL_RAW" \
    --model-sha="$MODEL_RAW_SHA" \
    --input-dir="$INPUT_DIR" \
    --out-dir="$OUT_DIR" \
    2>&1 | tee "$LOG"
rc=${PIPESTATUS[0]}
set -e

if [ -d "$OUT_DIR" ]; then
    mv "$LOG" "$OUT_DIR/run.log"
    echo "RADIOML_ORIGINAL_NPU_AB_END rc=$rc out_dir=$OUT_DIR run.log moved into out_dir"
else
    echo "RADIOML_ORIGINAL_NPU_AB_END rc=$rc out_dir=$OUT_DIR (runner failed before mkdir; log left at $LOG)"
fi

echo "Next (host, after copying the whole \$OUT_DIR back):"
echo "  python -I scripts/audit_radioml_npu_ab.py --out-dir <copied \$OUT_DIR> \\"
echo "      --host-results <accuracy1 results dir>"

exit $rc
