#!/usr/bin/env bash
# Diagnostic experiments for the iCraft 3.39 same-process one-frame output
# delay. Each experiment processes frames 7-18 in ONE process and changes
# exactly ONE variable at a time:
#
#   0 baseline       : single Session reused (Device + Network once)
#   1 current scheme : fresh Session + fresh tensors per frame (npu_only_smoke)
#   2 reload network : Network re-created from JSON + raw per frame
#   3 fresh host dev : fresh HostDevice::Init() per frame
#   4 reopen device  : Device::Close + Device::Open per frame
#   5 two sessions   : two pre-created Sessions alternated (ping-pong)
#   6 log-only       : layerCount() before/after forward (NOT scored)
#
# Experiments 0-5 are scored; 6 is observation-only and never counts toward
# PASS. Each experiment's full output is saved to diag_logs/exp<N>.log; the
# script continues past any per-experiment failure and never exits early on an
# expected MISMATCH. The final table summarizes every DIAG line.
#
# Read-only diagnostic: it only runs the compiled model and reads layerCount().
# It does NOT write QSPI, modify SD boot, update the system, install packages,
# download a bitstream, or auto-retry. It never writes any handshake/FPGA
# register.
set -u
cd "$(dirname "$0")"

BIN="${NPU_DIAG_BIN:-./build/npu_diag}"
if [ ! -x "$BIN" ] && [ -x ./npu_diag ]; then BIN=./npu_diag; fi

log_dir=./diag_logs
rm -rf "$log_dir"
mkdir -p "$log_dir"

summary_file="$log_dir/summary.txt"
: > "$summary_file"

for exp in 0 1 2 3 4 5 6; do
    log="$log_dir/exp${exp}.log"
    echo "================ experiment $exp ================" | tee "$log"
    "$BIN" --experiment "$exp" \
           --model model.json --raw model.raw \
           --tensor expected_tensor_plddr.bin \
           --reference reference_argmax.txt 2>&1 | tee -a "$log"
    rc=$?
    echo "---------------- experiment $exp rc=$rc ----------------" | tee -a "$log"

    # Capture the DIAG summary + verdict lines for the final table.
    if grep -q '^DIAG exp=' "$log"; then
        grep '^DIAG exp=' "$log" | tail -1 >> "$summary_file"
        grep '^DIAG_RESULT=' "$log" | tail -1 >> "$summary_file"
    else
        echo "DIAG exp=$exp (no summary: setup error)" >> "$summary_file"
    fi
done

echo
echo "================ summary ================"
cat "$summary_file"
echo "========================================="
echo "Full per-experiment logs: $log_dir/exp{0..6}.log"

# The script always completes so the human can read the table; pass/fail is
# carried by each DIAG_RESULT line, not by this script's exit code.
exit 0
