# QAM-Aware RFNet V3.2 AutoDL workflow

This package trains a new V3.2 track that preserves the frozen V2 champion and
*incrementally* adds a zero-gated QAM delta branch.  It does not overwrite V2 or
V3/V3.1 checkpoints, ONNX files, Golden vectors, FPGA RTL or board-validation
artifacts.

## One-command recommended workflow

After extracting the package under an English-only path, run:

```bash
bash autodl_v3_2/run_complete.sh
```

This command checks CUDA, installs non-Torch dependencies from a configurable
mirror, runs the V3.2 smoke gate, audits the data contract, runs the controlled
ablations (A1-A3), verifies that the zero-gate initialization reproduces V2
element-wise, trains the complete formal trajectory (auto-resuming from
`last.pt` after any interruption), evaluates the exact V2-compatible namespace,
exports both ONNX graphs through the strict operator/shape gate, applies
promotion gates and creates
`outputs/qam_aware_v3_2/qam_aware_v3_2_formal_results.tar.gz`.

It is safe to run the same command again after an AutoDL interruption.  If
`outputs/qam_aware_v3_2/formal/checkpoints/last.pt` exists, training resumes
from that exact checkpoint, including optimizer, scheduler, AMP scaler, RNG and
DataLoader generator state.  `CUBLAS_WORKSPACE_CONFIG=:4096:8` is exported before
every Python process so the resumed run is bit-reproducible with the continuous
run.

`V3_2_AUTODL_COMPLETE_PASS` means every configured promotion gate passed.
`V3_2_AUTODL_COMPLETE_TRAINED_BUT_GATE_FAILED` means training, evaluation and
export still completed, but V2 remains the frozen champion.  Do not hide or
weaken a failed gate; download the result archive for diagnosis.

## What V3.2 changes relative to V3.1

1. **Frozen V2 preserved, not replaced.** The V2 `TimePowerPhaseRFNet` backbone
   is loaded *strictly* from `init/v2_time_power_phase_best.pt`.  Its logits are
   computed on the exact same path, so `logits = v2_logits + gate * delta_logits`
   with `gate = 0` at initialization reproduces V2 element-wise (verified at
   step 5 of `run_complete.sh` and in the test suite).
2. **Zero-gated QAM delta branch.** A tiny `12 → 16 → 8` head on the raw
   higher-order moments (`E[x], E[x²], E[x³], E[x⁴]` of the physical planes)
   can only *additively correct* the V2 logits.  There is no QAM reweighting of
   the base classifier and no capacity increase in the backbone.
3. **Knowledge distillation.** A separate frozen V2 teacher anchors the learnable
   backbone: `loss = CE + alpha·T²·KL(softmax(s/T), softmax(t/T))`.  The teacher
   is never in the student graph, checkpoint, or ONNX export.
4. **Full-precision training** (`simulate_hardware_inputs: false`) exactly as the
   frozen V2 was trained/evaluated, so "init == V2" is verifiable end-to-end and
   the promotion comparison is apples-to-apples.
5. **Controlled ablations** (A0-A3) search only the loss (distillation on/off,
   mild QAM weights ∈ {1.05, 1.10}) on train/validation, never the blind set.
6. **Strict ONNX export gate** — unchanged from V3.1: hard-fails on any operator
   outside `Conv/BatchNorm/ReLU/Add/Concat/ReduceMean/Mul/Gemm`, any wrong
   shape/dtype, or any non-opset-17 graph.
7. **Checkpoint selection on macro-F1** with a minimum-epoch floor of 10 (not
   the forced full 60-epoch trajectory that overfit V3.1).
8. **Reproducible CUDA** and **configurable pip mirror**, unchanged from V3.1.

The frozen FPGA→model contract, class order, sample length, and NPU operator
policy are unchanged.

## Manual staged workflow

1. Choose an AutoDL GPU image that already contains CUDA-enabled PyTorch.
2. Upload and extract the package under an English-only path, preferably
   `/root/autodl-tmp/qam_aware_v3_2`.
3. Run `bash autodl_v3_2/setup_env.sh` once.
4. Run `bash autodl_v3_2/run_smoke.sh`.  Do not start the formal job unless it
   prints `V3_2_AUTODL_SMOKE_PASS`.
5. (Optional) Run `bash autodl_v3_2/run_ablation.sh` to search A1-A3 and inspect
   `outputs/qam_aware_v3_2/ablation/ablation_comparison.csv`.  If A3 wins, set
   `training.class_weights` accordingly in `configs/qam_aware_v3_2.yaml` and
   re-run the formal trajectory.
6. Run `bash autodl_v3_2/run_pilot.sh`.  This executes epochs 1-5 of the real
   formal trajectory, not a throw-away duplicate run.
7. Inspect the pilot log.  If loss/logits are finite and validation improves,
   continue the exact checkpoint with `bash autodl_v3_2/resume_formal.sh`.
   `run_formal.sh` is only for starting a clean formal run from epoch 1.
8. If a formal job is interrupted, use `bash autodl_v3_2/resume_formal.sh`.
9. `resume_formal.sh` automatically runs final evaluation and ONNX export after
   the resumed formal training reaches its configured end.
10. Download the complete `outputs/qam_aware_v3_2/formal/` directory, including
    checkpoints, effective config, logs, tables and ONNX files.

The formal evaluator deliberately does not access `v3_2_final_blind_test`.
That namespace remains reserved until architecture and hyperparameters are
frozen.  V2 remains the champion baseline until V3.2 passes offline, iCraft and
real-board acceptance gates.

The final script also runs `check_qam_aware_v3_2_acceptance`.  V3.2 is not
promoted unless it improves the exact V2 development namespace in overall
accuracy, macro-F1 and QAM accuracy without unacceptable per-class/SNR
regressions.
