# QAM-Aware RFNet V3.1 AutoDL workflow

This package trains a new V3.1 track.  It does not overwrite V2 or V3
checkpoints, ONNX files, Golden vectors, FPGA RTL or board-validation
artifacts.

## One-command recommended workflow

After extracting the package under an English-only path, run:

```bash
bash autodl_v3_1/run_complete.sh
```

This command checks CUDA, installs non-Torch dependencies from a configurable
mirror, runs the V3.1 smoke gate, audits the data contract, trains the complete
60-epoch formal trajectory, evaluates the robust, exact V2-compatible promotion
and SDR-like report-only suites, exports both ONNX graphs through the strict
operator/shape gate, applies promotion gates and creates
`outputs/qam_aware_v3_1/qam_aware_v3_1_formal_results.tar.gz`.

It is safe to run the same command again after an AutoDL interruption.  If
`outputs/qam_aware_v3_1/formal/checkpoints/last.pt` exists, training resumes
from that exact checkpoint, including optimizer, scheduler, AMP scaler, RNG and
DataLoader generator state.  `CUBLAS_WORKSPACE_CONFIG=:4096:8` is exported before
every Python process so the resumed run is bit-reproducible with the continuous
run.

`V3_1_AUTODL_COMPLETE_PASS` means every configured promotion gate passed.
`V3_1_AUTODL_COMPLETE_TRAINED_BUT_GATE_FAILED` means training, evaluation and
export still completed, but V2 remains the frozen champion.  Do not hide or
weaken a failed gate; download the result archive for diagnosis.

## What V3.1 changes relative to V3

1. **Gentle robustness** — the training channel reverts to the V2-mild
   impairment set as the dominant distribution and adds only low-probability
   phase noise / SFO / IQ imbalance.  Destructive fading/interference are off.
2. **Checkpoint selection on macro-F1** (`checkpoint_metric: val_macro_f1`,
   `checkpoint_mode: max`) instead of val_loss.
3. **Full-epoch floor** (`minimum_epochs_before_stopping: 60` and `epochs: 60`)
   so the cosine schedule runs to completion and early stopping can no longer
   fire before convergence.
4. **Higher-order raw QAM moments** (`physical_moment_order: 4`) in the direct
   physical shortcut, plus mild QAM class weights, targeting 16QAM/64QAM.
   `HigherOrderMomentPool` computes raw moments `E[x], E[x²], E[x³], E[x⁴]` —
   not the standardised skewness/kurtosis statistics.
5. **Strict ONNX export gate** — the dual-graph export hard-fails (non-zero
   exit) if `onnx.checker` fails, the default-domain opset is not 17, the NPU
   partition inputs are not `iq` FP32 `[1,2,1024]` + `physical_features` FP32
   `[1,3,1024]`, the output is not `logits` FP32 `[1,8]`, or any operator other
   than `Conv/BatchNorm/ReLU/Add/Concat/ReduceMean/Mul/Gemm` appears.  The
   `BatchNorm1d(affine=False)` input-norm stems are replaced at export time with
   frozen-affine equivalents so no `Constant` nodes leak into the partition.
6. **Report-only SDR robustness suite** (`sdr_robust`) — an over-the-air probe
   channel (Rayleigh/Rician/multipath/CFO/SFO/IQ-imbalance/…) is evaluated and
   reported, but it never participates in the V2 promotion gate; the gate still
   reads only the exact `v2_compatible` namespace.
7. **Reproducible CUDA** — `CUBLAS_WORKSPACE_CONFIG=:4096:8` is exported before
   every Python process in `run_complete.sh` and `run_smoke.sh`.
8. **Configurable pip mirror** — `setup_env.sh` uses `V3_PIP_INDEX_URL`
   (default Tsinghua, official PyPI as fallback) and never reinstalls or
   downgrades the image's PyTorch/CUDA.

The frozen FPGA→model contract, class order, sample length, and NPU operator
policy are unchanged.

## Manual staged workflow

1. Choose an AutoDL GPU image that already contains CUDA-enabled PyTorch.
2. Upload and extract the package under an English-only path, preferably
   `/root/autodl-tmp/qam_aware_v3_1`.
3. Run `bash autodl_v3_1/setup_env.sh` once.
4. Run `bash autodl_v3_1/run_smoke.sh`.  Do not start the formal job unless it
   prints `V3_1_AUTODL_SMOKE_PASS`.
5. Run `bash autodl_v3_1/run_pilot.sh`.  This executes epochs 1-5 of the real
   formal trajectory, not a throw-away duplicate run.
6. Inspect the pilot log.  If loss/logits are finite and validation improves,
   continue the exact checkpoint with `bash autodl_v3_1/resume_formal.sh`.
   `run_formal.sh` is only for starting a clean formal run from epoch 1.
7. If a formal job is interrupted, use `bash autodl_v3_1/resume_formal.sh`.
8. `resume_formal.sh` automatically runs final evaluation and ONNX export after
   the resumed formal training reaches its configured end.
9. Download the complete `outputs/qam_aware_v3_1/formal/` directory, including
   checkpoints, effective config, logs, tables and ONNX files.

The formal evaluator deliberately does not access `v3_1_final_blind_test`.
That namespace remains reserved until architecture and hyperparameters are
frozen.  V2 remains the champion baseline until V3.1 passes offline, iCraft and
real-board acceptance gates.

The final script also runs `check_qam_aware_v3_1_acceptance`.  V3.1 is not
promoted unless it improves the exact V2 development namespace in overall
accuracy, macro-F1 and QAM accuracy without unacceptable per-class/SNR
regressions.
