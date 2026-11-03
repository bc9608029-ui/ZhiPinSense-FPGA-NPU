# V3.3 Phase 5 — Numerical-Stability Repair Report

**Date:** 2026-10-02
**Track:** `qam_aware_v3_3`
**Status:** fixed and re-packaged; CUDA preflight still pending (never certified as
"formal training ready" by this report).

---

## 1. What failed

On the real RTX 5090, Stage-1 aborted with:

```
RuntimeError: V3.3 training produced a non-finite loss
```

The failure is a genuine FP16 overflow in the residual expert's
`HigherOrderMomentPool`, not a config or data bug.

## 2. Root cause (exact mechanism)

- The formal dataset contains `-20 dB` frames. Their IQ plane reaches
  `iq_max_abs ≈ 29.84`.
- `PowerLagOneFeatures` turns that into a physical power plane with
  `physical_max_abs ≈ 975.61`.
- `HigherOrderMomentPool` (order 4) computes `E[x], E[x²], E[x³], E[x⁴]` by
  repeated multiplication. Under `torch.autocast(... , dtype=torch.float16)`
  the feature products are FP16, whose max is `≈ 65504`.
- `x² ≈ 951 815 > 65504 → Inf`, and `x⁴ → NaN`. The NaN propagates into the
  expert's delta, then into `logits = v2_logits + gate·delta`, and the loss
  goes non-finite.

This is exactly why the deployment contract matters: on the NPU the physical
plane is dequantized from SInt8 to `[-2, 2]` via `int8 · (2/127)`. The training
graph was the only place still feeding the raw, unbounded physical plane into
the expert.

## 3. The six fixes

### Fix 1 — deployable input clamp before `HigherOrderMomentPool`
`BoundedResidualExpert` now clamps its physical input to `[-2, 2]` **before**
the moment pool. The clamp is built from `Add`/`Mul`/`Relu` over pre-registered
1-D buffers (`_input_bound = 2.0`, `_input_two_bound = 4.0`, `_neg_one`), so it
exports as initializers — **no `Clip`, `Sub`, or `Constant`** enters the graph,
and the partition stays on the 8-op whitelist.

- Frozen V2 backbone input and behavior are untouched.
- `gate = 0` still yields `logits` element-wise equal to V2 (residual `gate·δ`
  is zero regardless of the clamped `δ`).
- `|x| ≤ 2 ⇒ x⁴ ≤ 16`, so the order-4 moment can no longer overflow FP16.

### Fix 2 — numerically-sensitive losses in FP32
- Residual penalty: `(aux["residual"].float() ** 2).mean()`.
- Domain consistency: `mse_loss(logits.float(), hw_logits.detach().float())`.

Non-finite loss is **not** swallowed or replaced by 0: it raises
`RuntimeError` with full diagnostics (Fix 5).

### Fix 3 — release-blocking full-SNR CUDA gate
`tests/test_qam_aware_v3_3_full_snr_cuda.py` runs A1/A2/A3 over the full
21-SNR suite `[-20 … 20]` (a superset of the required 6 points), with autocast
FP16 enabled, asserting:

1. autocast FP16 actually enabled;
2. `-20 dB` physical planes exceed `[-2, 2]` and are clamped to it, with finite
   order-4 moments;
3. forward / each loss component / total / backward / gradients / optimizer step
   all finite;
4. `gate=0` initialization reproduces V2 element-wise;
5. final residual bounded by `residual_bound`;
6. ONNX checker + opset 17 + 8-op whitelist pass.

### Fix 4 — preflight runs the gate first
`run_preflight.sh` inserts step `[2]` "Full-SNR CUDA numerical-stability gate"
**before** the 2-epoch smoke. `INPUT_HASH` now includes the model, the trainer,
and both new test files. Any non-finite ⇒ no `V3_3_PREFLIGHT_DONE` marker.

### Fix 5 — enhanced non-finite diagnostics
`_describe_non_finite` now reports: `variant`, `seed`, `epoch`, `batch`,
SNR range, `iq_max_abs`, `physical_max_abs`, `moments_max_abs`, and each loss
component (`ce`, `family`, `residual`, `domain`), plus logit finiteness/max.

### Fix 6 — re-execution and re-package (this report)
Full results below. Old package `baabc407…` is superseded and must be discarded.

## 4. Verification results

### CPU full test suite
```
72 passed, 5 skipped
```
The 5 skips are all CUDA-only and are never counted as a CUDA pass:
- `test_qam_aware_v3_3_cuda.py` (real-model CUDA integration + resume round-trip)
- `test_qam_aware_v3_3_full_snr_cuda.py` (3 variants, the new gate)
- `test_qam_aware_v3_3_trainer.py::test_cuda_smoke_forward_backward_is_finite`

`tests/test_qam_aware_v3_3_numeric_cpu.py` (host-equivalent of the CUDA gate)
passes all 4, including the regression that **reproduces** the FP16 overflow
without the clamp and proves it is fixed with the clamp.

### Smoke pipeline (CPU)
- 2-epoch smoke train: `train_loss = 0.1704`, finite.
- Smoke eval: `final_blind_test_accessed = false`, accuracy 0.9083.
- Smoke ONNX export: 8-op gate **passed**, no unexpected operators.

### ONNX 8-op whitelist
Partition operators after the fix:

```
Add 11, BatchNormalization 1, Concat 2, Conv 14, Gemm 4,
Mul 9, ReduceMean 7, Relu 16
```

vs. the pre-Phase-5 baseline (`Add 8, Mul 7, Relu 14`). The delta
(`+3 Add, +2 Mul, +2 Relu`) is exactly the clamp
`b + neg·relu(2b + neg·relu(x + b))` — all whitelisted, **zero** `Identity`,
`Clip`, `Sub`, or `Constant` introduced.

### Manifest / CRC / residue
- `sha256_manifest.txt`: every packaged file verified, **0 digest mismatches**.
- ZIP CRC: **0 failures**.
- Residue scan: no `outputs/`, `dist/`, `input/`, `__pycache__/`, `*.pyc` in the
  archive.
- All 5 `autodl_v3_3/*.sh` pass `bash -n`.

## 5. Deliverable

- **Archive:** `dist/qam_aware_v3_3_autodl.zip`
- **Authoritative SHA256 / size / manifest count:** recorded in
  `pretraining_readiness.json` (local tracker, not shipped) and printed by
  `python -m scripts.package_qam_aware_v3_3_autodl`. The archive contains this
  report, so the report cannot self-reference its own digest — see the local
  tracker and the packaging output for the final hash.

**Superseded (discard):**
`baabc407742a2b5a603bacfe4fc46c6cf7ba0863a48cbd55c94680af7741921c`
(pre-Phase-5 build without the input clamp).

## 6. What is still NOT done

- **No formal training has been started.** This report certifies only functional
  correctness and numerical stability of the code paths.
- `pretraining_readiness.json` remains `status: pending-cuda-preflight`.
- Learning rate was not lowered, gradient clipping was not raised, and NaN was
  not ignored — none of those shortcuts were used.

## 7. Next step

```bash
bash autodl_v3_3/run_preflight.sh
```

This must print `V3_3_PREFLIGHT_FUNCTIONAL_PASS` on the real GPU (now including
the full-SNR numerical-stability gate at step `[2]`) before the formal stage is
considered ready.

## 8. Phase 5.1 addendum — test device-isolation fix (2026-10-02)

The full-SNR CUDA gate had a test-isolation defect, not a model/clamp defect:
`build_qam_aware_v3_3_partition(student)` returns `student.core` with **shared**
parameters, and the test called `.cpu()` on it to export ONNX — which moved the
live CUDA student's backbone off `cuda:0`, so the later extreme-residual check
fed CUDA input to CPU weights. A1/A2/A3 had already completed the full 21-SNR,
FP16-autocast train/val with all losses, gradients, parameters and the `-20 dB`
forward finite; the failure occurred only after the export.

Fix (test-only): the export graph is now `copy.deepcopy(source_partition).eval().cpu()`
(an independent copy — verified no shared parameter/buffer tensors), followed by
an assertion that every live `student` parameter and buffer is still exactly on
`cuda:0` before the `weights×50` / `gate=100` residual-bound check. No model,
clamp, trainer, loss, dataset, SNR, LR/epoch/search/selection/acceptance, or
`build_qam_aware_v3_3_partition` shared-semantics change; no frozen asset touched.
