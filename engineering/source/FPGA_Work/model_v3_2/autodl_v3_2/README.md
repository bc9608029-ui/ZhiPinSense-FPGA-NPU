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

The 8 steps are:

1. `setup_env.sh` — check CUDA and install non-Torch dependencies (configurable
   pip mirror).
2. `run_smoke.sh` — source tests + a 2-epoch train/eval/ONNX-export smoke gate
   (marker-guarded, so a rerun keeps the previously passed result).
3. Dataset contract audit on the formal config.
4. Controlled ablations (A1–A3) and **freezing the validation-only winner** into
   `outputs/qam_aware_v3_2/formal/selected_candidate.yaml` (skipped if already
   frozen; reuses `ablation_summary.json` if present).
5. Init-equivalence check — the zero-gate V3.2 reproduces V2 logits element-wise
   on a single shared input (`max_abs_diff < 1e-5`).
6. Three-seed formal trajectory (per-seed train → eval → ONNX export), then the
   multi-seed acceptance gate.
7. Packaging of all formal artifacts into a deterministic LF manifest + portable
   archive.
8. Final status: `V3_2_AUTODL_COMPLETE_PASS` or
   `V3_2_AUTODL_COMPLETE_TRAINED_BUT_GATE_FAILED`.

The result archive is
`outputs/qam_aware_v3_2/qam_aware_v3_2_formal_results.tar.gz`.

## Resume after interruption

The same command is safe to run again:

* A **completed seed** is skipped (its `seeds/seed<seed>/SEED_DONE.json` marker
  exists).
* An **incomplete seed** resumes from its own `seeds/seed<seed>/checkpoints/last.pt`,
  including optimizer, scheduler, AMP scaler, RNG and DataLoader generator state.
  `CUBLAS_WORKSPACE_CONFIG=:4096:8` is exported before every Python process so a
  resumed run is bit-reproducible with the continuous run.
* The frozen `selected_candidate.yaml` is **never** re-derived or silently
  changed on resume.
* `V3_2_AUTODL_COMPLETE_PASS` is printed **only** after every seed, the
  multi-seed gate, ONNX export, acceptance and packaging have all completed.

## Selection rule (frozen before any formal seed)

The ablation winner is chosen by a **pre-written, validation-only rule**
(`training/select_qam_aware_v3_2_candidate.py`):

* scope: train/validation only — `v3_2_final_blind_test`, `test` and
  `v2_compatible` scores are never consulted;
* metric: `val_macro_f1`, tie-broken by `val_accuracy`;
* the winner's full `training` override (distillation + class weights) is frozen
  into `selected_candidate.yaml` (and `.json`) together with the ablation
  summary SHA-256, so the formal run cannot drift from what was selected.

## Multi-seed promotion gate

Three independent seeds (2026/2027/2028) train, evaluate and export into
separate directories.  The gate
(`evaluation/check_qam_aware_v3_2_multi_seed_acceptance.py`) applies a fixed rule
that is never lowered and never cherry-picks:

* **mean improvement** — the three-seed mean of accuracy, macro-F1 and QAM mean
  must each clear the `minimum_*_gain` bars;
* **per-seed regression floors** — EVERY seed must individually clear the
  per-class and 0/10/20 dB `maximum_*_drop` caps.

Final PASS = both halves hold.  The evaluation always uses the exact V2
development namespace (test seed 2026, 21 SNR) and never accesses the final
blind set.

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
5. **Controlled ablations** (A1–A3) search only the loss (distillation on/off,
   mild QAM weights ∈ {1.05, 1.10}) on train/validation, never the blind set,
   and the winner is frozen by the validation-only rule above before any formal
   seed starts.
6. **Strict ONNX export gate** — unchanged from V3.1: hard-fails on any operator
   outside `Conv/BatchNorm/ReLU/Add/Concat/ReduceMean/Mul/Gemm`, any wrong
   shape/dtype, or any non-opset-17 graph.
7. **Checkpoint selection on macro-F1** with a minimum-epoch floor of 10 (not
   the forced full 60-epoch trajectory that overfit V3.1).
8. **Reproducible CUDA**, **three-seed evaluation with mean ± std**, and a
   **configurable pip mirror**, unchanged in spirit from V3.1.

The frozen FPGA→model contract, class order, sample length, and NPU operator
policy are unchanged.

## Manual staged workflow

1. Choose an AutoDL GPU image that already contains CUDA-enabled PyTorch.
2. Upload and extract the package under an English-only path, preferably
   `/root/autodl-tmp/qam_aware_v3_2`.
3. Run `bash autodl_v3_2/setup_env.sh` once.
4. Run `bash autodl_v3_2/run_smoke.sh`.  Do not start the formal job unless it
   prints `V3_2_AUTODL_SMOKE_PASS`.
5. (Optional) Run `bash autodl_v3_2/run_smoke_full.sh` to rehearse the complete
   ablation → selection → three-seed → gate → package path with tiny configs
   (the gate is expected to FAIL there).
6. Run `bash autodl_v3_2/run_complete.sh` for the full workflow.  If a formal job
   is interrupted, either re-run `run_complete.sh` (it skips finished seeds) or
   run `bash autodl_v3_2/resume_formal.sh` to resume the formal stage only.
7. `run_complete.sh` automatically runs the multi-seed acceptance gate, final
   evaluation, ONNX export and result packaging after the seeds reach their
   configured end.
8. Download the complete `outputs/qam_aware_v3_2/formal/` directory, including
   per-seed checkpoints, effective config, logs, tables, ONNX files and the
   `aggregate/` gate report.

The formal evaluator deliberately does not access `v3_2_final_blind_test`.
That namespace remains reserved until architecture and hyperparameters are
frozen.  V2 remains the champion baseline until V3.2 passes the offline
multi-seed gate, iCraft and real-board acceptance gates.

## Script inventory

| Script | Purpose |
| --- | --- |
| `setup_env.sh` | Check CUDA, install non-Torch dependencies from a configurable mirror |
| `run_smoke.sh` | Source tests + 2-epoch train/eval/ONNX smoke gate |
| `run_ablation.sh` | Controlled A1–A3 search on train/validation only |
| `run_smoke_full.sh` | Tiny full-pipeline rehearsal (ablation → selection → 3-seed → gate → package) |
| `resume_formal.sh` | Resume only the formal stage (requires a frozen `selected_candidate.yaml`) |
| `run_complete.sh` | One-command entry: all eight steps above |

## Layout of the formal output

```
outputs/qam_aware_v3_2/
  ablation/ablation_summary.json            # A1-A3 comparison (train/val only)
  formal/
    selected_candidate.yaml                 # frozen validation-only winner
    seeds/seed2026/{checkpoints,tables,onnx,logs,config,SEED_DONE.json}
    seeds/seed2027/...
    seeds/seed2028/...
    aggregate/{v3_2_acceptance.json, aggregate_summary.json, per_seed_summary.json}
  qam_aware_v3_2_formal_results.tar.gz      # deterministic archive + LF manifest
```
