# AD-AMR V1 release-blocker audit and fix report

Date: 2026-10-02

This addendum supersedes the original package's CUDA-readiness and pilot-gate
claims. No GPU formal training, final-blind evaluation, board work, or SDR work
was performed during this repair.

## Confirmed defects in the previous archive

1. `profile_ad_amr_model` created a CPU input after the production model had
   already moved to CUDA, causing a CPU/CUDA Conv1d mismatch.
2. CUDA preflight expected resumed cumulative history `[2,3]`, although the
   trainer correctly retains history and returns `[1,2,3]`.
3. The checkpoint omitted the train DataLoader generator state, so the advertised
   strict resume was not reproducible across a shuffled epoch boundary.
4. The old pilot did not compare against V2. It could pass a candidate merely for
   exceeding `0.175`, even if that candidate was materially worse than V2.
5. Pilot did not enforce per-class, QAM, SNR, mid-SNR, or OOD regression floors.
6. ONNX Runtime absence was accepted as `skipped`, allowing a false export PASS.
7. Pilot did not bind its run to the exact source/config/checkpoint hash that had
   passed CUDA preflight.
8. The reported best validation accuracy could come from a different epoch than
   the best-macro-F1 checkpoint.

## Repairs

- Profiling input now inherits the live model parameter device and dtype.
- Checkpoint format is version 3. It serializes loader, CPU, and per-device CUDA
  RNG states as CPU uint8 tensors and restores the loader state before training.
- Optimizer tensors are explicitly migrated to the selected training device.
- `run_training` reports accuracy from the same best-macro-F1 epoch.
- CUDA preflight invokes the real `run_training`, `evaluate`, and `export_ad_amr`
  entrypoints for both P0 and P1; resume must yield `[1,2,3]`.
- ONNX checker/opset 17 and ONNX Runtime parity status `ok` are mandatory.
- Preflight writes a source-bound marker; the pilot rejects missing or stale
  markers.
- Stage A still performs the controlled P0/P1 mechanism comparison. Stage B runs
  the winner at seeds 2026 and 2027. Candidate and strict-loaded frozen V2 are
  evaluated on the exact same deterministic validation records.
- Promotion requires every configured gate: mean macro-F1 and accuracy gains,
  each-seed macro-F1 floor, every-class regression floor, 0/10/20 dB floors,
  0–10 dB gain, QAM non-regression, validation-only OOD domain floors, complete
  finite metrics, no test/blind access, and ONNX Runtime parity.

## Verification performed locally

- Full CPU test suite: see the final delivery report for the exact count.
- Strict continuous-vs-split/resume training produces element-wise identical
  model state on CPU.
- The real frozen V2 checkpoint strictly loads its expected 91 model-state keys
  and runs paired evaluation on identical candidate/V2 records.
- Two-epoch CPU train, validation evaluation, ONNX checker/opset 17, and ONNX
  Runtime parity all pass.
- CUDA-only production integration remains intentionally pending until executed
  on the target AutoDL GPU.

## Honest remaining boundaries

- CUDA preflight has not been executed locally because this host has no CUDA GPU.
- Passing functional tests does not guarantee better accuracy; only the paired
  two-seed pilot can authorize promotion.
- The unmodified paper architecture remains outside the current NPU operator
  whitelist. This package evaluates research performance; it does not claim an
  immediately deployable NPU graph.
