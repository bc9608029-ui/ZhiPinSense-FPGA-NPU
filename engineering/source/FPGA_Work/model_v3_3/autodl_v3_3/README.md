# QAM-Aware RFNet V3.3 AutoDL workflow

V3.3 keeps the frozen V2 champion backbone *strictly* (parameters **and** BatchNorm
running stats pinned) and adds a separate, zero-gated residual expert on the
higher-order moments of the physical planes that can only *additively* correct
the V2 logits.  A train-only family head (A2) and a dual numeric-domain
consistency loss (A3) are optional.  It does not overwrite V2, V3/V3.1/V3.2
checkpoints, ONNX files, Golden vectors, FPGA RTL or board-validation artifacts.

## One-command recommended workflow

After extracting the package under an English-only path, run:

```bash
bash autodl_v3_3/run_complete.sh
```

The six steps are:

1. `setup_env.sh` — check CUDA and install non-Torch dependencies (configurable
   pip mirror; **never** reinstalls or downgrades the image's CUDA torch).
2. `run_preflight.sh` — source tests + a 2-epoch train/eval/ONNX-export smoke
   gate (hash-guarded).
3. `run_pilot.sh` — Stage-1 ablations (A0–A3, two selection seeds) and freezing
   the pre-written-rule winner into `selected_candidate.yaml` (hash-guarded).
4. Init-equivalence check — the zero-gate V3.3 reproduces V2 logits element-wise
   on a single shared input (`max_abs_diff < 1e-6`).
5. Three-seed formal trajectory (per-seed train → eval → ONNX export), then the
   multi-seed acceptance gate (including the FPGA-sim-vs-FP32 gap floor).
6. Packaging of all formal artifacts into a deterministic LF manifest + portable
   archive.

The result archive is
`outputs/qam_aware_v3_3/qam_aware_v3_3_formal_results.tar.gz`.

## Resume after interruption

The same command is safe to run again:

* A **completed seed** is skipped (its `seeds/seed<seed>/SEED_DONE.json` marker
  exists).
* An **incomplete seed** resumes from its own `seeds/seed<seed>/checkpoints/last.pt`,
  including optimizer, scheduler, AMP scaler, RNG and DataLoader generator state.
  `CUBLAS_WORKSPACE_CONFIG=:4096:8` is exported before every Python process so a
  resumed run is bit-reproducible with the continuous run.
* The preflight/pilot results are **hash-guarded** — they are re-run only if a
  key input (config or source) changed.
* The frozen `selected_candidate.yaml` is **never** re-derived or silently
  changed on resume.
* `V3_3_AUTODL_COMPLETE_PASS` is printed **only** after every seed, the
  multi-seed gate, ONNX export, acceptance and packaging have all completed.

## Selection rule (frozen before any formal seed)

Stage-1 ranks A0–A3 by a **pre-written, fixed lexicographic rule**
(`training/select_qam_aware_v3_3_candidate.py`) over the `v2_compatible`
development namespace:

1. two-seed mean macro-F1 (desc);
2. worst-seed macro-F1 (desc);
3. two-seed mean accuracy (desc);
4. two-seed mean QAM (16QAM/64QAM) accuracy (desc);
5. worst-class regression vs V2 (asc);
6. FPGA-sim-vs-FP32 accuracy gap (asc);
tie-break: variant name (asc).

**A0 (frozen V2) participates and may win.**  If it does, `promoted` is `false`
and V2 stays champion — the three-seed formal run is skipped and a
`no_promotion.json` result is written.  `v3_3_final_blind_test` is never
consulted.

## Multi-seed promotion gate

Three independent seeds (2026/2027/2028) train, evaluate and export into separate
directories.  The gate
(`evaluation/check_qam_aware_v3_3_multi_seed_acceptance.py`) applies a fixed rule
that is never lowered and never cherry-picks:

* **mean improvement** — the three-seed mean of accuracy, macro-F1 and QAM mean
  must each clear the `minimum_*_gain` bars;
* **per-seed regression floors** — EVERY seed must individually clear the
  per-class and 0/10/20 dB `maximum_*_drop` caps;
* **FPGA-sim gap floors** (V3.3 addition) — EVERY seed's FPGA Mandatory-Core
  emulated accuracy/macro-F1 must not fall more than `maximum_fpga_sim_*_gap`
  below its own full-precision result.

Final PASS = all three halves hold.  The evaluation always uses the exact V2
development namespace (test seed 2026, 21 SNR) and never accesses the final
blind set.

## What V3.3 changes relative to V3.2

1. **Truly frozen V2.** V3.2 froze only 6 affine-norm parameters; V3.3 pins every
   V2 backbone parameter *and* its BatchNorm running stats (the `train()` override
   keeps the backbone in eval mode), so the backbone can never drift.
2. **Zero-gated residual expert.** A tiny `3·order → hidden → 8` head on the raw
   higher-order moments (`E[x], E[x²], …, E[x^order]` of the power/lag1 planes)
   can only *additively correct* the V2 logits; `gate = 0` at init reproduces V2
   element-wise.
3. **Train-only family head (A2).** A PSK/QAM/FSK/OFDM auxiliary head regularizes
   the shared hidden representation; it never enters the deployed graph.
4. **Dual numeric-domain consistency (A3).** A consistency loss between the FP32
   path and the FPGA Mandatory-Core emulated input domain; one mechanism (MSE on
   logits) per ablation.
5. **FPGA-sim gap floor.** The promotion gate now also requires the deployed graph
   not to be materially weaker under the FPGA-emulated input domain than FP32.
6. **Strict ONNX export gate** — unchanged: hard-fails on any operator outside
   `Conv/BatchNorm/ReLU/Add/Concat/ReduceMean/Mul/Gemm`, any wrong shape/dtype,
   or any non-opset-17 graph.
7. **Checkpoint selection on macro-F1** with a minimum-epoch floor of 10.

The frozen FPGA→model contract, class order, sample length, and NPU operator
policy are unchanged.

## Manual staged workflow

1. Choose an AutoDL GPU image that already contains CUDA-enabled PyTorch.
2. Upload and extract the package under an English-only path, preferably
   `/root/autodl-tmp/qam_aware_v3_3`.
3. Run `bash autodl_v3_3/setup_env.sh` once.
4. Run `bash autodl_v3_3/run_preflight.sh`.  Do not start the pilot unless it
   prints `V3_3_PREFLIGHT_PASS`.
5. Run `bash autodl_v3_3/run_pilot.sh` for the Stage-1 selection.  The formal
   stage is forbidden unless it prints `V3_3_PILOT_PASS`.
6. Run `bash autodl_v3_3/run_complete.sh` for the full workflow.  If a formal job
   is interrupted, either re-run `run_complete.sh` (it skips finished seeds) or
   run `bash autodl_v3_3/resume_formal.sh` to resume the formal stage only.
7. Download the complete `outputs/qam_aware_v3_3/formal/` directory, including
   per-seed checkpoints, effective config, logs, tables, ONNX files and the
   `aggregate/` gate report.

The formal evaluator deliberately does not access `v3_3_final_blind_test`.  That
namespace remains reserved until architecture and hyperparameters are frozen.
V2 remains the champion baseline until V3.3 passes the offline multi-seed gate,
iCraft and real-board acceptance gates.

## Script inventory

| Script | Purpose |
| --- | --- |
| `setup_env.sh` | Check CUDA, install non-Torch dependencies from a configurable mirror |
| `run_preflight.sh` | Source tests + 2-epoch train/eval/ONNX smoke gate |
| `run_pilot.sh` | Stage-1 A0–A3 selection + freeze `selected_candidate.yaml` |
| `resume_formal.sh` | Resume only the formal stage (requires a frozen `selected_candidate.yaml`) |
| `run_complete.sh` | One-command entry: all six steps above |

## Layout of the formal output

```
outputs/qam_aware_v3_3/
  ablation/ablation_summary.json            # A0-A3 comparison (dev namespace)
  preflight/V3_3_PREFLIGHT_DONE             # smoke gate marker
  formal/
    selected_candidate.yaml                 # frozen winner (A0 -> promoted: false)
    seeds/seed2026/{checkpoints,tables,onnx,logs,config,SEED_DONE.json}
    seeds/seed2027/...
    seeds/seed2028/...
    aggregate/{v3_3_acceptance.json, aggregate_summary.json, per_seed_summary.json}
  qam_aware_v3_3_formal_results.tar.gz      # deterministic archive + LF manifest
```
