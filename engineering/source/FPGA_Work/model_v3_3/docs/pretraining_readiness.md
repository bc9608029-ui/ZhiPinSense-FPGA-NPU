# V3.3 Pretraining Readiness Checklist

This is the go/no-go checklist for starting formal GPU training on AutoDL. Every
item is verified on the local (CPU) machine before the package is produced. No
formal training is started from this pass.

## Model & freeze (verified against the real V2 checkpoint)

- [x] `load_v2_into_v3_3` strictly loads the V2 champion into the V3.3 backbone.
- [x] `freeze_v2_backbone` pins every V2 parameter + BatchNorm running stats.
- [x] Init equivalence: `max_abs_diff(V3.3(gate=0), V2) < 1e-6` (asserted).
- [x] Frozen backbone is byte-identical after a real optimizer step (asserted).
- [x] Only the residual expert receives gradient (asserted).
- [x] Profile: 71,662 frozen / 681 trainable / 72,343 total (asserted).

## Bounded residual (audit fix)

- [x] `residual_bound = 1.0`, `residual_penalty_weight = 0.01` (finite, ablable — never 0/unbounded).
- [x] Clamp is applied to the **final residual** `gate * delta`, not `delta`.
- [x] Final residual never exceeds the configured bound under *any* input (regression-tested with extreme weights/gate).
- [x] Clamp uses Add/Mul/Relu + pre-registered buffers only — no `Clip`/`Sub`/`Constant` in the exported graph.

## Numerical stability (Phase 5 fix — the RTX 5090 Stage-1 failure)

- [x] Root cause: `-20 dB` frames reach `physical_max_abs ≈ 975.61`; the order-2/order-4 moment products overflow FP16 (`x² ≈ 951815 > 65504 → Inf`, `x⁴ → NaN`).
- [x] Deployable input clamp to `[-2, 2]` added **before** `HigherOrderMomentPool` via Add/Mul/Relu over pre-registered 1-D buffers (`_input_bound=2.0`, `_input_two_bound=4.0`, `_neg_one`); matches the deployment dequant range `int8·(2/127)`; `|x|≤2 ⇒ x⁴≤16`.
- [x] No `Clip`/`Sub`/`Constant` introduced; the partition stays on the 8-op whitelist (verified: only `+3 Add, +2 Mul, +2 Relu` vs. baseline, zero `Identity`).
- [x] Frozen V2 backbone input/behavior unchanged; `gate=0` still element-wise equals V2.
- [x] Numerically-sensitive losses computed in FP32: `(residual.float()**2).mean()` and `mse_loss(logits.float(), hw_logits.detach().float())`; NaN is never swallowed or replaced by 0.
- [x] Enhanced non-finite diagnostics (variant/seed/epoch/batch/SNR range/IQ max/physical max/moments max/CE/family/residual/domain).
- [x] Release-blocking full-SNR CUDA gate `tests/test_qam_aware_v3_3_full_snr_cuda.py` (A1/A2/A3, 21 SNR, FP16 autocast, clamp, per-component/grad/param finiteness, ONNX 8-op gate, residual bound).
- [x] CPU host-equivalent `tests/test_qam_aware_v3_3_numeric_cpu.py` reproduces the FP16 overflow without the clamp and proves the clamp fixes it.
- [x] `run_preflight.sh` runs the full-SNR CUDA gate at step `[2]` **before** the 2-epoch smoke; `INPUT_HASH` includes model + trainer + both new tests.

## Data isolation (audit fix)

- [x] Stage-1 trains/evaluates on `v3_3_validation` only; `test` and `v3_3_final_blind_test` are forbidden and raise immediately.
- [x] Two selection seeds change both training randomness and validation data (distinct fingerprints asserted).
- [x] A0 is re-inferred from the real V2 checkpoint (FP32 + FPGA-sim + OOD), never copied from the acceptance YAML.
- [x] `access_audit.json` proves Stage-1 never instantiated `test`/`v3_3_final_blind_test`.
- [x] Only after candidate freeze may a single formal 3-seed dev-test evaluation run.

## Synthetic OOD (audit fix)

- [x] OOD battery wired into the pilot: CFO, SFO, phase offset/noise, IQ imbalance, Rayleigh/Rician, multipath, amplitude & sample-start, ≥1 cross-parameter-family/cross-generator holdout.
- [x] OOD metrics enter validation selection only (never test/blind).

## Operator & export contract

- [x] ONNX opset 17 export produces both e2e and NPU-partition graphs.
- [x] NPU partition contains only the 8 allowed operators (gate hard-fails otherwise), including the now-active input clamp and residual clamp paths.
- [x] Input `[1,2,1024]`+`[1,3,1024]`, output `[1,8]`, FLOAT — asserted by the gate.

## Dataset integrity

- [x] Fingerprint overlap across train/validation/test is 0 (no exact waveform leakage).
- [x] `v3_3_final_blind_test` namespace is never instantiated (source-scanned + runtime-spied).

## Selection, pilot threshold & narrow search

- [x] Stage-1 selection rule is fixed and lexicographic; A0 can win.
- [x] Selection adds worst-domain macro-F1, worst-seed macro-F1, worst-class regression, FPGA-sim gap.
- [x] Every regression baseline is the same-seed A0 (real inference), never the acceptance YAML's V2 test per-class; each OOD domain is compared same-seed, same-domain.
- [x] Pilot hard gates are hard constraints (not tie-breakers): improvement `≥ 0.01`, per-seed macro-F1 `≥` same-seed A0, per-seed worst-domain OOD regression `≤ 0.01`, per-seed per-class drop `≤ 0.03`, per-seed FPGA-sim accuracy/macro-F1 gap `≤ 0.03`, and no NaN/Inf/missing. Any fail ⇒ `promoted: false`.
- [x] Narrow search is enabled by default, targets the actual Stage-1 winning mechanism (never a fixed A3), and freezes its best config into `selected_candidate` (tuned kept only if better than the untuned winner).
- [x] Multi-seed gate fails closed below the bars (asserted).
- [x] FPGA-sim gap floor is enforced per seed (asserted).
- [x] Gate script exits non-zero (2) on a failed gate (asserted).

## Pipeline gates & hash guards (audit fix)

- [x] `run_preflight.sh` = CUDA hard gate + functional smoke only; `run_pilot.sh` = performance gate; the two are not conflated.
- [x] Pilot hash guard covers model/trainer/evaluators/selection/search code/Stage-1 (search + pilot-gate) config/acceptance/dataset/channel config + V2 checkpoint hash.
- [x] Preflight hash guard now also covers every test file and the init-equivalence script.

## CUDA formal-training preflight (release-blocking audit)

- [x] Three device/dtype bugs fixed: CUDA test assertion (`logits.is_cuda`); `verify_init_matches_v2` shared input on the model device; `_finite_probe` DataLoader inputs moved to the model device (plus a defensive fix in `verify_qam_aware_v3_3_init.py`).
- [x] **GPU resume bug fixed** (found on the real RTX 5090): the structured checkpoint is now loaded with `map_location="cpu"` (not `self.device`), so the DataLoader generator state and the CPU/CUDA RNG states stay CPU `ByteTensor`s; the optimizer state is migrated to the exact CUDA device; the AMP scaler state (scalar-only in torch 2.8) restores device-free; the legacy migration path was audited the same way.
- [x] **CUDA RNG state restored element-wise** (found on the real RTX 5090): `torch.cuda.get_rng_state_all()` returns a `list[ByteTensor]` (one per device), so the resume restore validates the list/tuple + device count and restores each state on CPU before `set_rng_state_all` — the previous single-tensor `.detach().cpu()` would have raised `AttributeError` on GPU.
- [x] **Resume history assertion corrected**: `load_resume` restores round 1's history and `fit` appends round 2, so a resumed `fit()` returns the cumulative `[1, 2]` (not `[2]`); the CUDA test asserts `[1, 2]` / `len == 2` / `[-1]["epoch"] == 2` without clearing history or weakening the assertion.
- [x] Real-model CUDA integration test (`tests/test_qam_aware_v3_3_cuda.py`) covers load-real-V2 → build-real-V3.3+teacher → CUDA → init-equivalence → round-1 micro train/val → `_finite_probe` → checkpoint save → **CUDA resume from `last.pt`** (every RNG source is perturbed first, then `load_resume` restores the generator / torch CPU RNG / CUDA RNG per-device / Python random / NumPy RNG / scheduler / AMP scaler / optimizer-on-`cuda:0` to round 1's exact state; round 2 executes with cumulative history `[1, 2]`) → evaluator reads `best.pt` → no NaN/Inf/mismatch. Skipped on CPU only.
- [x] `run_preflight.sh` asserts `torch.cuda.is_available()`, prints the runtime, runs the CUDA test first, then the full-SNR numerical-stability gate at step `[2]`, and writes `V3_3_PREFLIGHT_DONE` only after every step — a CPU skip is never a CUDA pass.
- [x] `run_complete.sh` requires the CUDA preflight marker (with a source-hash match) before entering the pilot.
- [x] Preflight and pilot hash guards now include the resume core (`training/resumable_trainer.py`, `training/trainer.py`, `training/utils.py`) and the resume-related tests.
- [ ] **Pending on AutoDL**: `bash autodl_v3_3/run_preflight.sh` must print `V3_3_PREFLIGHT_FUNCTIONAL_PASS` on the real GPU before the formal stage is considered fully ready.

## Smoke pipeline (run end-to-end on CPU)

- [x] 2-epoch smoke train completes (loss finite, checkpoint written).
- [x] Smoke evaluation completes (`final_blind_test_accessed: false`).
- [x] Smoke ONNX export passes the operator gate (input clamp + residual clamp active, `residual_bound=1.0`).

## Packaging

- [x] `dist/qam_aware_v3_3_autodl.zip` produced with LF-only manifest (authoritative SHA recorded in `pretraining_readiness.json`; old pre-fix `baabc407…` discarded).
- [x] `sha256_manifest.txt` digests match every packaged file (`sha256sum -c` clean, 0 mismatches).
- [x] Archive residue scan clean (no `outputs`/`dist`/`input`/`__pycache__`/`*.pyc`), CRC 0 failures.
- [x] AutoDL shell scripts pass `bash -n`.

See `docs/v3_3_phase5_stability_fix_report.md` for the full Phase 5 repair report.

## Verdict

**Ready to ship to AutoDL — but not yet certified CUDA-ready.** Upload the
package and run the CUDA preflight-only stage first:

```bash
bash autodl_v3_3/run_preflight.sh
```

Only after `V3_3_PREFLIGHT_FUNCTIONAL_PASS` is pasted back is the one-command
workflow (`bash autodl_v3_3/run_complete.sh`) cleared. See `docs/v3_3_report.md`
section P for the workflow and the residual risks.
