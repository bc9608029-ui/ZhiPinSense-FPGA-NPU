# AD-AMR Net V1 — 训练前准备完成报告 (Pre-training readiness report)

Date: 2026-10-02
Model line: **AD-AMR Net V1** (independent) — ICC 2024 "Adaptive Denoising With
Efficient Channel Attention for Automatic Modulation Recognition" (`ma.pdf`).
Final status: **`ready-for-cuda-preflight`** (NOT `ready-for-formal-training`).

---

## 1. Scope and completion

This track delivered the *pre-training preparation* only, exactly as scoped:

| # | Item | Status |
| --- | --- | --- |
| 1 | Audit of existing project + paper | ✅ `docs/audit.md` |
| 2 | Model code | ✅ `models/ad_amr_net.py` |
| 3 | Training code | ✅ `training/` |
| 4 | Evaluation code | ✅ `evaluation/evaluate_ad_amr.py` |
| 5 | Data code | ✅ `datasets/` + `channel/` |
| 6 | CPU tests | ✅ 33 passed (14.75 s) |
| 7 | CPU short smoke (train → eval → ONNX) | ✅ all three stages pass |
| 8 | AutoDL CUDA preflight / pilot / packaging scripts | ✅ `autodl_ad_amr_v1/` + `scripts/` |
| 9 | Final ZIP + report | ✅ `dist/ad_amr_v1_autodl.zip` + this report |

No formal AutoDL long training was started; no final blind data was accessed.

## 2. Prohibitions honored (verbatim, unchanged)

- ❌ No AutoDL formal long training started.
- ❌ No final blind data (`final_blind_test` / `ad_amr_final_blind_test`) accessed.
- ❌ No board / SDR / FPGA touched.
- ❌ No modification of V2, V3, V3.1, V3.2, V3.3.
- ❌ No modification of RTL / Golden / bitstream / iCraft / EDIF / NPU project.
- ❌ No comparison thresholds lowered to fabricate "success".
- ❌ No paper-unstated value presented as a "paper setting" — every such value is a
  documented, configurable implementation assumption (A1–A13).
- ❌ No new-model *validation* result compared to V2 *test* result.
- ✅ P0 / P1 differ **only** in the MSE target (identical network / init / data /
  seed / optimizer / lr / augmentation / epochs).
- ✅ Final status is `ready-for-cuda-preflight` only (no CUDA preflight has run on
  this host, so `ready-for-formal-training` is forbidden and not claimed).
- ❌ No paper-model modification to force an operator gate through; no NPU
  deployment claimed.
- ✅ Split leakage check performed — none found (separate namespace, non-overlapping
  sample-id ranges).

## 3. Paper audit (summary — full record in `docs/audit.md`)

- **Title:** "Adaptive Denoising With Efficient Channel Attention for Automatic
  Modulation Recognition", ICC 2024.
- **Pipeline:** IQ-only `x ∈ R^{2×L}` → ADM (WaveUNet + ECA denoiser) → FEM
  (stem Conv + ERSBs) → GAP → FCL → softmax.
- **ADM:** L down blocks (Conv1d k=15, downsampling, ECA) + L up blocks (Conv1d k=5,
  upsampling, ECA) + crop-and-concat skips + kernel-1 conv; shape-preserving.
- **FEM (Table I):** Conv(k=3,s=1,16) then ERSB(k=3,s=2) at channels 16, 32, 32, 64.
- **ERSB:** two conv + shortcut + adaptive soft-thresholding; SE replaced by ECA.
- **Soft-threshold (Eq. 1):** piecewise shrink toward zero by λ.
- **Loss (Eq. 4):** `L = α·L_MSE + L_CE`, α = 0.1.
- **Training:** Adam lr 0.001, 100 epochs, ReduceLROnPlateau + early stopping,
  RTX 3090, RadioML 2018.01A (24 mods). Paper results: OA 0.6460 / F1 0.6480 /
  Kappa 0.6306 / 0–10 dB 0.8480 / **0.25M params**.

## 4. Frozen V2 champion (authoritative reference — never modified)

- Checkpoint: `init/v2_time_power_phase_best.pt`
- SHA-256: `f9e4b5e5513f60907aa69416df3374353848272e14744cb193a46d06b02d71a6`
- Frozen **test** metrics: accuracy 0.705476, macro-F1 0.697538, QAM mean 0.464762.
- Class order: BPSK / QPSK / 8PSK / 16QAM / 64QAM / 2FSK / CPFSK / OFDM.
- Input: IQ-only `[N,2,1024]`; physical features `[N,3,1024]` derived *in-model*.
  Sample rate 128000 Hz, symbol rate 16000 Hz, 1024 samples/frame.

These are the champion **test** facts. AD-AMR V1 reports **validation**-only
metrics in this preparation phase; the two are never compared (prohibition).

## 5. Architecture (paper → implementation, full mapping in `docs/architecture_mapping.md`)

`models/ad_amr_net.py` implements `ECA`, `ERSB`, `_DownBlock`, `_UpBlock`, `ADM`,
`FEM`, `ADAMRNet`, and the `ADAMRClassifier` ONNX wrapper. `ADAMRNet.forward`
returns `(logits, denoised_iq)`; `denoised_iq` feeds only the training MSE term and
is dropped by `ADAMRClassifier` for export.

Measured budget (`profile_ad_amr_model`):
- parameters **288236** (trainable 288236)
- neural MACs **32 525 014**, FLOPs **65 050 028**
- FP32 parameter size ≈ 1.10 MB

## 6. Implementation assumptions (A1–A13, full table in `docs/implementation_assumptions.md`)

Every paper-unstated dimension is an explicit constructor/config parameter with a
documented default, never a "paper setting":

| # | Dimension | Default |
| --- | --- | --- |
| A1 | ADM levels L | 4 (1024 → 64 bottleneck) |
| A2 | ADM base channels | 16 (→ 16/32/64/128) |
| A3 | Down-sampling mechanism | stride-2 conv k=15 |
| A4 | Up-sampling mechanism | nearest ×2 + conv k=5 |
| A5 | ECA kernel size | `\|log2(C)/2 + 1/2\|_odd` (γ=2, β=1) |
| A6 | Soft-threshold scaling | λ = α·mean(\|out\|), α = ECA(\|out\|) |
| A7 | FCL hidden size | 128 |
| A8 | Dropout | 0.2 |
| A9 | Batch size | 128 |
| A10 | Weight decay | 0.0 |
| A11 | LR scheduler metric | val macro-F1 (mode=max) |
| A12 | Classes | 8 (contest task, not RadioML 24) |
| A13 | Denoising supervision | P0 = MSE→noisy (Eq. 4 literal); P1 = MSE→clean |

## 7. Data pipeline, determinism, namespace isolation

- Split: train 25200 / val 5040 / test 8400, seed 2026, 21 SNR points −20:2:20.
- Determinism: `SeedSequence([seed, split_code, epoch, index])`,
  `split_code = blake2s(split_string)`; sample id = `split_code·1_000_000 + index`.
- Namespace: `ad_amr_train` / `ad_amr_validation` / `ad_amr_test` — disjoint from V2
  (`train`/`validation`/`test`) and V3.3 (`v3_3_*`), so no cross-track split leakage.
- `evaluate_ad_amr` has `FORBIDDEN_SPLITS = ("final_blind_test", "ad_amr_final_blind_test")`
  and writes `access_audit.json` proving the blind namespace was never read.

## 8. Loss variants P0 / P1

`training/ad_amr_loss.py` returns `(loss, {ce, mse, loss})`; the MSE target is
`noisy_iq` for P0 and `clean_iq` for P1; `α = 0.1`. The two configs
`configs/ad_amr_v1_p0.yaml` / `ad_amr_v1_p1.yaml` are byte-identical except
`training.loss.variant` and `output_root` — enforced by `test_ad_amr_loss.py`.

## 9. Training recipe (`training/ad_amr_trainer.py`)

Adam lr 0.001, 100 epochs, ReduceLROnPlateau (mode=max on val macro-F1), early stop
(min 20 epochs, patience 10), grad clip 1.0, AMP with **FP32 loss accumulation**
(the `logits.float()` / `denoised.float()` path, mirroring the V3.3 Phase-5 lesson),
`best.pt` + `last.pt`, full resume (model / optimizer / scheduler / AMP / RNG /
best-metric / stale-epochs / history). Non-finite losses raise `RuntimeError` with
diagnostics — never swallowed.

## 9.1 Single-batch overfit verification (real execution, P0 + P1)

`scripts/overfit_probe.py` (results also saved to
`outputs/ad_amr_v1/smoke/overfit_probe.json`) fixes one balanced batch (8 classes
x 4 samples, generated once via the deterministic dataset so the channel
augmentation is frozen for the loop — **no augmentation during training**), trains
only that batch for 500 Adam steps (lr 0.001), and reports initial/final loss and
accuracy plus a per-group gradient audit.

| Variant | init loss | final loss | init acc | final acc | CE (final) | MSE (final) |
| --- | --- | --- | --- | --- | --- | --- |
| P0 | 3.7857 | 1.1636 | 0.125 | **1.000** | 0.00022 | 11.6333 |
| P1 | 2.1524 | 0.0602 | 0.125 | **1.000** | 0.00756 | 0.5267 |

Loss falls clearly in both variants (P0 Δ = 2.62, P1 Δ = 2.09) and **training
accuracy reaches 100%** in both (P0 by iter 350, P1 by iter 400).  P0's MSE stays
high because its denoising target is the *noisy* input (exactly reproducing noise is
impossible while also classifying); the classification head still overfits to 100%.
The overfit succeeds, so **no hyperparameter/model change is needed** — the 2-epoch
smoke's 0.125 accuracy is expected for an untrained model and is *not* treated as a
reason to retune.

Gradient health (every trainable parameter finite & non-zero, both variants):

| Group | # params | all finite & non-zero |
| --- | --- | --- |
| ADM (incl. ECA) | 34 | ✅ |
| ECA | 12 | ✅ |
| FEM | 43 | ✅ |
| FCL head | 4 | ✅ |

## 9.2 Verification checklist → executable test mapping

Each release-check item is a real test that ran and passed:

| Checklist item | Test |
| --- | --- |
| P0/P1 configs identical except MSE target | `test_ad_amr_verification.py::test_p0_p1_configs_identical_except_variant_and_root` |
| clean/noisy from same underlying signal | `test_ad_amr_verification.py::test_clean_noisy_same_underlying_signal` |
| train/val/test fingerprint zero overlap | `test_ad_amr_verification.py::test_split_sample_id_zero_overlap` + `test_ad_amr_data.py::test_sample_id_no_overlap_across_splits` |
| final blind never instantiated | `test_ad_amr_verification.py::test_final_blind_split_refused` |
| checkpoint strict resume | `test_ad_amr_train.py::test_reload_and_resume` |
| model / optimizer / scheduler / AMP / all RNG restored | `test_ad_amr_verification.py::test_resume_restores_full_state` |
| ONNX Runtime parity | `test_ad_amr_onnx.py::test_ort_parity` + `test_ad_amr_verification.py::test_ort_parity_self_contained` |

Note on AMP: on this CPU host AMP is disabled (`amp:false`), so the AMP scaler state
is exercised for the restore *code path* but only carries real scale history on GPU;
the CUDA preflight (`amp:true`) is the authoritative AMP test.

## 10. CPU test results

`python -m pytest tests -q` → **33 passed, 8 warnings** (14.75 s). All 8 warnings
are third-party deprecations (torch ONNX `setup_onnx_logging`, legacy TorchScript
exporter); none originate from this project's code.  The 33 tests include the
dedicated pre-release verification suite (`tests/test_ad_amr_verification.py`) that
backs every checklist item in section 9.2 with an executable assertion.

## 11. CPU short smoke (train → eval → ONNX)

- `training.train_ad_amr --config configs/ad_amr_v1_smoke.yaml` →
  `best_epoch=1 best_val_macro_f1=0.027778 params=288236` (2-epoch smoke).
- `evaluation.evaluate_ad_amr --config ... --split ad_amr_validation` →
  accuracy 0.125, macro_f1 0.02778, kappa 0.0, qam_mean 0.0, accuracy_0_10db 0.125,
  denoising MSE→clean 0.7061, MSE→noisy 13.6676, params 288236. `access_audit.json`
  confirms `final_blind_test_accessed: false`.
- `scripts.export_ad_amr_onnx --config ...` →
  opset 17, checker passed, ORT parity ok (max abs diff 1.12e-08).

These numbers are a 128/64/32-sample, 2-epoch smoke with `amp:false`; they are
**not** a trained model result and are never compared to V2.

## 12. Deployment gap (honest, not hidden)

`outputs/.../onnx/deployment_gap_report.md` and `export_report.json` record the
exported op set and the gap vs the frozen 8-op NPU policy
(`Add, BatchNormalization, Concat, Conv, Gemm, Mul, ReduceMean, Relu`):

- Exported op types: Abs(4), Add(4), Concat(4), Constant(52), Conv(34), Gemm(2),
  Mul(16), ReduceMean(13), Relu(22), Resize(4), Sigmoid(12), Sign(4),
  Squeeze(24), Sub(4), Unsqueeze(24).
- **Outside the whitelist:** Abs, Constant, Resize, Sigmoid, Sign, Squeeze, Sub,
  Unsqueeze — originating from soft-thresholding (Abs/Sign/Sub), ECA (Sigmoid/
  Squeeze/Unsqueeze) and nearest upsampling (Resize).

**Conclusion:** AD-AMR V1 is **not deployable** to the ZG330 NPU under the current
8-op policy without re-architecting the denoiser and re-validating. **No NPU
deployment is claimed.**

## 13. AutoDL scripts and packaging

`autodl_ad_amr_v1/`:
- `setup_env.sh` — installs Python deps only; never reinstalls torch/CUDA (the GPU
  image provides them).
- `run_preflight.sh` — pytest suite + `run_cuda_preflight` (P0+P1 2-epoch AMP smoke,
  resume round-trip, eval, ONNX/ORT); prints `AD_AMR_V1_CUDA_PREFLIGHT_PASS` only on
  full success.
- `run_pilot.sh` / `resume_pilot.sh` — staged pilot (Stage A: P0/P1 seed 2026 ×8
  epochs, winner on val macro-F1; Stage B: winner seeds 2026/2027 ×15 epochs) with
  10 hard gates; prints `AD_AMR_V1_PILOT_PASS` / `AD_AMR_V1_PILOT_NO_GO`
  (chance 0.125, margin 0.05).
- `package_results.sh` — re-runs packaging on AutoDL.

Packaging (`scripts/package_ad_amr_autodl.py`) builds
`dist/ad_amr_v1_autodl.zip` with a `sha256_manifest.txt` (LF-only, no BOM);
excludes `outputs/`, `dist/`, `__pycache__`, `*.pyc`, and local-only trackers
(`pretraining_readiness.json`, `access_audit.json`, `_paper_text.txt`). CRC, digest,
residue and LF/BOM are verified in-script and by `test_ad_amr_packaging.py`.

Final archive (authoritative, recomputed via `Get-FileHash` after the final build):

- **SHA-256 (full 64 hex chars):** recorded in `dist/ad_amr_v1_autodl.zip.sha256`
  and `pretraining_readiness.json` (both outside the archive — a file cannot embed
  its own archive's hash without changing it).
- **Size:** ~896 KB (exact byte size in `pretraining_readiness.json`)
- **Manifest:** 48 entries; LF-only, no BOM; 0 digest mismatches; ZIP CRC ok;
  no excluded residue.

Hash audit: no truncated hash and no SHA-1 appears anywhere in the project — the
package hash is a genuine SHA-256 (64 hex chars = 256 bits), cross-checked against
`Get-FileHash` (which returns the identical value in uppercase).

## 14. Final status

**`ready-for-cuda-preflight`.** The next action is, and only is:

```bash
bash autodl_ad_amr_v1/run_preflight.sh     # on a GPU host
```

No formal training, no blind evaluation, and no deployment work is authorized from
this state. See `pretraining_readiness.json` for the machine-readable tracker.
