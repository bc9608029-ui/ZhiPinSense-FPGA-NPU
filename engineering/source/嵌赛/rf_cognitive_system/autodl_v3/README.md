# QAM-Aware RFNet V3 AutoDL workflow

This package trains a new V3 track.  It does not overwrite V2 checkpoints,
ONNX files, Golden vectors, FPGA RTL or board-validation artifacts.

## One-command recommended workflow

After extracting the package under an English-only path, run:

```bash
bash autodl_v3/run_complete.sh
```

This command checks CUDA, installs non-Torch dependencies, runs the V3 smoke
gate, audits the data contract, trains the complete formal trajectory,
evaluates both robust and exact V2-compatible suites, exports both ONNX graphs,
applies promotion gates and creates
`outputs/qam_aware_v3/qam_aware_v3_formal_results.tar.gz`.

It is safe to run the same command again after an AutoDL interruption.  If
`outputs/qam_aware_v3/formal/checkpoints/last.pt` exists, training resumes from
that exact checkpoint, including optimizer, scheduler, AMP scaler, RNG and
DataLoader generator state.

`V3_AUTODL_COMPLETE_PASS` means every configured promotion gate passed.
`V3_AUTODL_COMPLETE_TRAINED_BUT_GATE_FAILED` means training, evaluation and
export still completed, but V2 remains the frozen champion.  Do not hide or
weaken a failed gate; download the result archive for diagnosis.

## Manual staged workflow

1. Choose an AutoDL GPU image that already contains CUDA-enabled PyTorch.
2. Upload and extract the package under an English-only path, preferably
   `/root/autodl-tmp/qam_aware_v3`.
3. Run `bash autodl_v3/setup_env.sh` once.
4. Run `bash autodl_v3/run_smoke.sh`.  Do not start the formal job unless it
   prints `V3_AUTODL_SMOKE_PASS`.
5. Run `bash autodl_v3/run_pilot.sh`.  This executes epochs 1-5 of the real
   formal trajectory, not a throw-away duplicate run.
6. Inspect the pilot log.  If loss/logits are finite and validation improves,
   continue the exact checkpoint with `bash autodl_v3/resume_formal.sh`.
   `run_formal.sh` is only for starting a clean formal run from epoch 1.
7. If a formal job is interrupted, use `bash autodl_v3/resume_formal.sh`.
8. `resume_formal.sh` automatically runs final evaluation and ONNX export after
   the resumed formal training reaches its configured end.
9. Download the complete `outputs/qam_aware_v3/formal/` directory, including
   checkpoints, effective config, logs, tables and ONNX files.

The formal evaluator deliberately does not access `v3_final_blind_test`.
That namespace remains reserved until architecture and hyperparameters are
frozen.  V2 remains the champion baseline until V3 passes offline, iCraft and
real-board acceptance gates.

The final script also runs `check_qam_aware_v3_acceptance`.  V3 is not promoted
unless it improves the exact V2 development namespace in overall accuracy,
macro-F1 and QAM accuracy without unacceptable per-class/SNR regressions.
