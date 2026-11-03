# Stage 7 board integration runbook

Status: `READY_FOR_STAGE7_BOARD_INTEGRATION_RAW_REPLAY_PENDING`.

This runbook integrates the frozen candidate and model. It does not authorize
model/recovery/RF tuning on the two frozen validation rounds.

## 1. Truth-isolated deployment

Extract `rml24_final_stage7_board_overlay.tar.gz` on the board. Use the existing
validated waterfall UI tree as `BASE`, then assemble a new tree (never overlay
the only working base in place):

```bash
PKG=/root/rml24_final_stage7_board_overlay
BASE=/root/<validated-waterfall-tree>
FINAL=/root/rml24_final_stage7_board_$(date +%s)

bash "$PKG/deploy/assemble_stage7_board_tree.sh" \
  --base-source "$BASE" \
  --overlay-source "$PKG" \
  --out-tree "$FINAL"
```

## 2. Native UI build

```bash
cd "$FINAL"
taskset -c 0 bash board_package/build_ui_live_rml24_final.sh
test -x bin/board_ui_live_rml24_final
```

The required success marker is `UI_BUILD_RESULT result=PASS`.

## 3. Start the screen first

After loading the already validated HDMI FPGA bitstream:

```bash
"$FINAL/bin/board_ui_live_rml24_final" \
  --sock=/run/sdr_amr_ui_rml24_final.sock \
  --ctl-sock=/run/sdr_amr_control_rml24_final.sock \
  --display-refresh-hz=30
```

Required screen-side markers include `UI_VERSION_CHECK ... ok=YES` and
`UI_FB_READY ...`. Page 1 is 24-class classification, page 2 is the relative
spectrum/waterfall, and page 3 is the recovered-IQ constellation.

## 4. Start PC TX

On the PC, extract the separate self-test package. The board package contains no
private truth. Use the PC Pluto URI and a fresh output directory:

```powershell
python -I pc_runtime/rml24_final_tx.py `
  --legacy-root <EVIDENCE_ROOT> `
  --dataset dataset `
  --manifest pc_runtime/selftest_manifest_240.json `
  --out <FRESH_TX_OUT> `
  --listen-host 192.168.126.10 `
  --tx-uri "usb:<TX_URI>"
```

## 5. Start board RX

In a second board terminal, use the frozen legacy runtime and model pair:

```bash
UI_SOCKET=/run/sdr_amr_ui_rml24_final.sock \
bash "$FINAL/rml24_final/board_runtime/run_final_receiver.sh" \
  --run /root/rml24_final_run_$(date +%s) \
  --legacy-root /root/amr_rescue_20261025 \
  --model-dir /root/<model_rml24_bf16> \
  --control-host 192.168.126.10 \
  --save
```

Normal production mode is candidate-only. `--paired` is diagnostic only and is
not the final demonstration path.

## 6. Acceptance

- PC TX and board RX both finish all requested frames and restore both Plutos.
- No failed recovery is forced to a class.
- UI parser rejects no valid final records and displays all 24 classes unmerged.
- Spectrum and constellation update from the same recovered tensor as inference.
- The board deployment tree contains no private labels/expected predictions.
- Accuracy uses the full requested denominator; missing/failed frames count as
  failures.
- Repeat once after stopping all processes; do not claim reboot persistence
  unless the HDMI bitstream boot problem has separately been solved.
