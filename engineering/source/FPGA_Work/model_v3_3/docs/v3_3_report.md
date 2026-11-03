# QAM-Aware RFNet V3.3 — Pre-Training Preparation Report

Track: V3.3 (frontier-paper-driven model optimization, pre-training preparation).
Scope: audit, design, code, tests, short smoke, and AutoDL packaging **only**.
No formal GPU training, board bring-up, or SDR is performed in this pass, and no
frozen asset (V2 / V3 / V3.1 / V3.2 / FPGA RTL / Golden vectors / bitstream) is
modified. All work lives under the independent English path `F:\FPGA_Work\model_v3_3\`.

## A. Purpose and scope

Produce a single deployable model that improves QPSK/8PSK and 16QAM/64QAM
fine-grained confusion without sacrificing BPSK/CPFSK/OFDM, tolerates
SNR/channel/hardware numeric-domain variation, and exports to the ZG330 NPU /
iCraft 3.39 under the frozen operator policy. V3.3 learns from the V3.1/V3.2
gate failures (see `v3_2_failure_audit.md`) and recent AMC literature (see
`literature_review.md`).

## B. Architecture

`QAMAwareRFNetV33` wraps `QAMAwareRFNetV33Core`, whose `forward` is the exact NPU
graph:

- `v2_backbone` = the deployable V2 champion (`time_branch` 22ch conv,
  `physical_branch` 8ch encoder on 3 planes, `FusionClassifier(120,64,8)`),
  loaded strictly and frozen;
- `expert` = `BoundedResidualExpert` on `E[x], E[x²], E[x³], E[x⁴]` of the three
  physical planes (12 → 32 → 8) with a scalar `gate` parameter.

`logits = v2_logits + clamp(gate * delta, ±residual_bound)`, `gate = 0` at
initialization. The clamp acts on the **final residual** (Add/Mul/Relu only, via
pre-registered buffers, so no `Clip`/`Sub`/`Constant` reaches the NPU graph), making
`|logits − v2_logits| ≤ residual_bound` (1.0) under any input. The `physical_frontend`
and `deployment_emulator` are training/evaluation-only.

## C. Backbone freeze

`freeze_v2_backbone` sets `requires_grad_(False)` on every V2 parameter and puts the
backbone in eval mode; a `train()` override re-applies eval mode after every
`model.train()`. Result: **71,662 parameters frozen, 681 trainable** (the expert).
The freeze is re-verified from the real V2 checkpoint, closing the V3.2 hole
(9–42% backbone drift).

## D. Candidate space (A0–A3, one mechanism per ablation)

A0 frozen V2 (can win) · A1 +zero-gated residual expert · A2 +family aux head ·
A3 +dual-domain consistency. Validated individually, never stacked.

## E. Dataset and splits

Inherited unchanged from the frozen baseline (V2-mild impairment, 8 modulations,
1024 samples, 21 SNR points, 25200/5040/8400). Fingerprint overlap across
train/validation/test is **0**. `v3_3_final_blind_test` (seed 26093032, 16800
samples) is reserved and never instantiated by any development/training code.

**Data-isolation (audit fix).** Stage-1 trains and evaluates on the dedicated
`v3_3_validation` namespace (two seeds, 2026/2027), never the `test` namespace and
never `v3_3_final_blind_test`. A split-access guard raises immediately on any forbidden
split and writes `access_audit.json`; a formal 3-seed dev-test evaluation is permitted
only after candidate freeze.

## F. Evaluation protocol

Stage-1 candidates are evaluated on the `v3_3_validation` namespace (two selection
seeds) in FP32 and FPGA-sim domains, plus a synthetic OOD battery (CFO, SFO, phase
offset/noise, IQ imbalance, Rayleigh/Rician, multipath, amplitude & sample-start,
and a cross-parameter-family/cross-generator holdout). A0 (frozen V2) is re-inferred
from the real V2 checkpoint on the same seeds — never copied from the acceptance YAML.
The formal dev-test suite stays on the V2 `test` namespace (seed 2026) with a per-SNR
sweep (0/10/20 dB floors) and FPGA-sim-vs-FP32 gap. Metrics: accuracy, macro-F1, QAM
mean, per-class accuracy/F1, confusion matrix, SNR sweep, FPGA-sim gap, OOD worst-domain
macro-F1 (selection only).

## G. FPGA/NPU contract and operator policy

Unchanged frozen contract: IQ `[1,2,1024]`, physical `[1,3,1024]`, logits `[1,8]`,
class order BPSK/QPSK/8PSK/16QAM/64QAM/2FSK/CPFSK/OFDM, SInt8 NCL, dequant
`1/127`/`2/127`, zero-point 0, round-nearest-away-from-zero, saturation
`[-127,127]`. Operator policy (hard gate):
`{Add, BatchNormalization, Concat, Conv, Gemm, Mul, ReduceMean, Relu}`.

## H. Numeric-domain handling

Training/eval runs in FP32 (`simulate_hardware_inputs: false`), the condition that
makes init-equivalence hold. `DeploymentInputEmulator` mirrors the Mandatory-Core
Q15→SInt8→host-dequant contract bit-exactly for A3 and the FPGA-sim gap gate.

## I. Init-equivalence guarantee

Asserted by test: at `gate = 0`, `max_abs_diff(V3.3(x), V2(x)) < 1e-6` on a shared
input, and the frozen backbone is byte-identical after an optimizer step.

## J. Selection rule

Stage-1 (two validation seeds, 15 epochs) ranks A0–A3 by a fixed lexicographic rule:
mean macro-F1 → worst-seed macro-F1 → worst-domain OOD macro-F1 → mean accuracy →
mean QAM → worst-class regression vs **same-seed A0** (asc) → FPGA-sim gap (asc) →
name. A0 may win (`promoted: false` ⇒ V2 stays champion, formal run skipped). Every
regression baseline is the **same-seed A0** (frozen V2) re-inferred on the identical
`v3_3_validation` data — seed 2026 vs A0 seed 2026, seed 2027 vs A0 seed 2027, and each
OOD domain vs the same-seed, same-domain A0 — never the acceptance YAML's V2
test-namespace per-class numbers.

A trained candidate is promoted only if **all** pilot hard gates hold (measured against
the same-seed A0): (1) two-seed mean validation macro-F1 `≥ +0.01`; (2) every seed's
macro-F1 not below the same-seed A0; (3) every seed's worst-domain OOD macro-F1 drops
`≤ 0.01`; (4) every seed, every class drops `≤ 0.03`; (5) every seed's FPGA-sim accuracy
gap `≤ 0.03`; (6) every seed's FPGA-sim macro-F1 gap `≤ 0.03`; (7) no NaN/Inf/missing.
Any failure ⇒ `promoted: false` and the exact gate is printed. Hard gates are
constraints, not ranking tie-breakers — a `+0.01` mean gain never alone promotes a
candidate that regresses a class, an OOD domain, or the FPGA-sim gap.

A budget-controlled narrow search (`training/narrow_search_v3_3.py`, **enabled by
default**) tunes the expert's own knobs (learning rate, residual bound, residual
penalty, family aux weight, domain-consistency weight) over the two fixed validation
seeds + synthetic OOD (8 trials × 6 epochs, best re-confirmed at 15 epochs). It runs
only on the **actual Stage-1 winning mechanism** (never a fixed A3) and only if that
trained winner cleared the preliminary improvement threshold; the best config is frozen
into `selected_candidate.yaml/.json`, and the tuned candidate is kept only if it
improves the untuned winner. Test/blind never participate in tuning.

## K. Promotion gate (three seeds 2026/2027/2028, never lowered)

Mean improvement (accuracy `≥ +0.02`, macro-F1 `≥ +0.02`, QAM mean `≥ +0.05`);
per-seed regression floors (per-class drop `≤ 0.03`, 0/10/20 dB drop `≤ 0.01`);
per-seed FPGA-sim gap floor (`≤ 0.03` accuracy and macro-F1). PASS = all three
halves hold on every seed.

## L. Tests (77; 72 passed, 5 CUDA-skipped on CPU)

`tests/` contains 77 test cases across 11 files (5 CUDA-only cases are skipped on a
CPU host): model strict-load/init/freeze/profile (9), trainer smoke/resume/domain
(3 + 1 CUDA), real-model CUDA integration incl. GPU resume round-trip (1 CUDA, 14
coverage points), ONNX op gate (5), selection
rule + pilot gates + narrow-search closure (31), multi-seed gate (6), packaging (4),
dataset fingerprint + blind-set seal (3), data-isolation/bounded-residual regression
(7), plus the Phase 5 numerical-stability files — `numeric_cpu` (4) and
`full_snr_cuda` (3 CUDA variants). Result: **72 passed, 5 skipped (CUDA unavailable)** —
the five skips are the tiny trainer CUDA smoke, the real-model CUDA integration test,
and the three full-SNR numeric-gate variants, and none is ever accepted as a CUDA
pass (the AutoDL preflight asserts CUDA before running them). The regression files pin
the audit fixes and the final selection closure: forbidden-split rejection, per-seed
validation fingerprints, real (non-copied) A0 inference, strictly bounded final
residual, OOD entering selection, below-threshold promotion blocking, the seven pilot
hard gates, the same-seed / same-domain A0 baseline, the narrow-search default run
targeting the actual winner, the tuned-vs-untuned keep-if-better rule, and a complete
pilot hash guard.

## M. ONNX export

`scripts/export_qam_aware_v3_3_onnx.py` exports
`qam_aware_v3_3_e2e_opset17.onnx` and
`qam_aware_v3_3_npu_partition_opset17.onnx`; the partition gate hard-fails on any
operator outside the 8-op policy, wrong shapes/dtype, or non-opset-17 graph.

## M2. Audit corrections (independent audit, 2026-10-02)

Ten corrections, all in-place under `F:\FPGA_Work\model_v3_3\` (no V3.4, no formal GPU run):

1. **Bounded residual** — `residual_bound = 1.0`, `residual_penalty_weight = 0.01`;
   clamp on the final residual, Add/Mul/Relu only, provably `≤ 1.0` under any input.
2. **Validation-only Stage-1** — dedicated `v3_3_validation` entry; two selection
   seeds change training + validation randomness; test/blind unreachable before freeze.
3. **Real A0** — A0 re-infers the frozen V2 checkpoint on the same seeds/domains, no
   copied acceptance metrics.
4. **Access audit** — `access_audit.json` proves Stage-1 never touched test/blind.
5. **OOD wiring** — synthetic OOD battery enters validation selection only.
6. **Selection hardening** — worst-domain/seed macro-F1, worst-class regression,
   FPGA-sim gap; pilot minimum-improvement threshold gates the 3-seed formal run.
7. **Narrow search** — budget-controlled random search over 3–5 expert knobs.
8. **Preflight vs pilot** — functional smoke (`run_preflight.sh`) and performance
   pilot (`run_pilot.sh`) are distinct; only the pilot opens the formal stage.
9. **Hash guards** — pilot/preflight hash now covers model/trainer/evaluators/
   selection/acceptance/dataset/channel config + V2 checkpoint hash.
10. **Regression tests** — 7 new tests pin every correction above.

## M3. Final selection-closure corrections (2026-10-02)

Three in-place corrections finish the selection loop (no V3.4, no formal GPU run, no
model-body change), each pinned by new regression tests:

1. **Narrow search truly enters the default pilot.** `narrow_search.enabled: true`;
   the search targets the *actual* Stage-1 winning mechanism (never a fixed A3), runs
   only after a trained winner clears the preliminary improvement threshold (an A0 win
   or a below-threshold candidate stops it), and its best config is frozen into
   `selected_candidate.yaml/.json`. The tuned candidate is kept only if it improves the
   untuned winner — otherwise the untuned winner stays.
2. **Pilot hard gates before formal training.** Seven gates (measured against the
   same-seed A0) must all hold for `promoted: true`: improvement `≥ +0.01`; per-seed
   macro-F1 not below same-seed A0; per-seed worst-domain OOD regression `≤ 0.01`;
   per-seed per-class drop `≤ 0.03`; per-seed FPGA-sim accuracy gap `≤ 0.03`; per-seed
   FPGA-sim macro-F1 gap `≤ 0.03`; no NaN/Inf/timeout/missing. Any fail ⇒
   `promoted: false` (V2 stays champion), the failed gate is printed, and
   `run_complete.sh` refuses the 3-seed formal run.
3. **Stage-1 class/OOD regression baseline is the same-seed A0.** Per-class and OOD
   regressions compare candidate seed 2026 vs A0 seed 2026 and seed 2027 vs A0 seed
   2027 (each OOD domain same-seed, same-domain), never the acceptance YAML's V2
   test-namespace per-class. `acceptance.yaml` V2 test metrics are used only for the
   post-freeze 3-seed formal test gate.

New regression tests (11): narrow search actually executes by default; search target is
the Stage-1 winner; search result is truly frozen into `selected_candidate`; a tuned
candidate that is worse is discarded; an A0 win skips the search; every pilot hard gate
fail ⇒ `promoted: false`; changing `acceptance.yaml` V2 per-class does not change the
Stage-1 ranking; both seeds use the same-seed A0 baseline; OOD is compared same-seed
same-domain; Stage-1 accessing test/final-blind fails immediately; and the pilot hash
guard covers the search code, the search config, the pilot gate, and the V2 checkpoint.

## M4. CUDA formal-training release-blocking audit (2026-10-02)

A device/dtype audit found three release-blocking bugs that only a real GPU
would trigger, plus a defensive fix in the init-equivalence source of truth:

1. **Wrong CUDA test assertion** (`tests/test_qam_aware_v3_3_trainer.py`): the
   CUDA smoke asserted `logits.device == torch.device("cuda")`, but a real
   forward on `cuda:0` reports `cuda:0`, which is not `==` a bare `"cuda"`.
   Changed to the semantically-correct, index-robust `logits.is_cuda`.
2. **CPU input to a CUDA model in `verify_init_matches_v2`**
   (`training/train_qam_aware_v3_3.py`): the shared init-equivalence input was
   built with `torch.randn(...)` on CPU after `model`/`teacher` were moved to
   CUDA, raising the "FloatTensor vs cuda.FloatTensor" mismatch. The input is now
   created on `next(model.parameters()).device`.
3. **CPU DataLoader inputs to a CUDA model in `_finite_probe`**
   (`training/train_qam_aware_v3_3.py`): the probe fed CPU DataLoader batches
   straight to the GPU model. Inputs are now moved to the model's device before
   the forward, mirroring the trainer's `inputs.to(self.device, non_blocking=True)`.
4. **Defensive** (`scripts/verify_qam_aware_v3_3_init.py`): the shared input is
   now built on the student's device (unchanged on CPU, robust if ever run on
   CUDA).

A new real-model CUDA integration test (`tests/test_qam_aware_v3_3_cuda.py`)
covers the nine release-blocking device paths against the *real* frozen V2
champion and the *real* V3.3 model (not `TinyV33Net`): (1) load the real V2
checkpoint; (2) build the real V3.3 student + V2 teacher; (3) move to CUDA;
(4) `verify_init_matches_v2` on CUDA; (5) a real `QAMAwareV33Trainer` micro
train/val epoch; (6) `_finite_probe` on CUDA; (7) checkpoint save/load/resume
round-trip; (8) the real evaluator reading `best.pt` on CUDA; and (9) a final
no-NaN/Inf, no-CPU/GPU-mismatch sweep. It is skipped on a CPU-only host.

`run_preflight.sh` is now a **CUDA hard gate**: it asserts
`torch.cuda.is_available()`, prints the runtime, runs the real-model CUDA test
first, then the source tests and the 2-epoch train/eval/ONNX smoke, and writes
`V3_3_PREFLIGHT_DONE` only after every step — a CPU skip can never be mistaken
for a CUDA pass. Its hash guard now covers every test file and the
init-equivalence script. `run_complete.sh` additionally requires the preflight
marker before entering the pilot.

## M5. GPU resume fix — structured-checkpoint device placement (2026-10-02)

The real RTX 5090 preflight found one more release-blocking bug that only a GPU
resume would trigger: `ResumableTrainer.load_resume` loaded the whole structured
checkpoint with `map_location=self.device` (`cuda:0`), which mapped *every* tensor
in it — including the DataLoader generator state and the CPU/CUDA RNG states —
onto the GPU. `Generator.set_state` then rejected the CUDA-mapped `ByteTensor`
(`TypeError: RNG state must be a torch.ByteTensor`), so the second round could
never resume. Fix (device-exact resume, no model/data/loss/hyperparameter change):

1. The structured checkpoint is loaded with `map_location="cpu"`; only the
   model/optimizer state is placed on the training device.
2. `model.load_state_dict` copies the CPU weights into the already-CUDA model;
   `optimizer.load_state_dict` is followed by `_migrate_optimizer_state_to_device`
   so every optimizer state tensor lands on the exact CUDA device.
3. `train_loader_generator_state` is restored via `.detach().cpu()` and the torch
   CPU/CUDA RNG states via `.detach().cpu()` before `set_state` — device-explicit
   even though the load is already CPU-side.
4. The scheduler state (scalars only) restores unchanged.
5. The AMP scaler state is device-free (torch 2.8 `GradScaler.state_dict` holds only
   Python scalars); `QAMAwareV33Trainer.load_resume` now also loads the checkpoint on
   CPU and `GradScaler.load_state_dict` re-creates its per-device tensors.
6. The legacy (version-1) migration path was audited too: `best.pt` is now loaded on
   CPU, and the optimizer state is migrated the same way.

The real-model CUDA integration test now asserts the full resume round-trip on the
real GPU (14 coverage points): on-disk generator/RNG state is CPU `ByteTensor`,
optimizer state is on the correct CUDA device, history/epochs are continuous, and
the scheduler + AMP scaler restore consistently — on top of the original round-1 /
init-equivalence / finite-probe / evaluator coverage.

## M6. CUDA RNG list + resume history corrections (2026-10-02)

Two more release-blocking defects surfaced on the real RTX 5090 resume path, plus
a strengthening of the resume test so restoration is *proven* rather than assumed:

1. **CUDA RNG state is a `list[ByteTensor]`, not a single Tensor.**
   `torch.cuda.get_rng_state_all()` returns one `ByteTensor` per device, so
   `restore_rng_state`'s `state["torch_cuda_all"].detach().cpu()` failed with
   `AttributeError` (`'list' object has no attribute 'detach'`) the moment the
   resume ran on a GPU. It now restores element-wise: the state must be a
   list/tuple whose length equals `torch.cuda.device_count()`, each element must be
   a `uint8` `ByteTensor`, and each is moved to CPU before `set_rng_state_all`.
2. **Resume history is cumulative, not per-round.** `load_resume` restores round 1's
   history and `fit` appends round 2, so the resumed `fit()` returns `[1, 2]`. The
   CUDA test's `== [2]` assertion was corrected to `[1, 2]` (with `len == 2` and
   `[-1]["epoch"] == 2`) — no history clearing and no weakened assertion.
3. **The resume test now proves restoration.** Before `load_resume` it perturbs every
   RNG source (Python random, NumPy, torch CPU, torch CUDA) and the loader generator,
   then asserts each source is restored to round 1's exact on-disk state (generator,
   torch CPU RNG, CUDA RNG per-device, Python random, NumPy RNG, scheduler
   `last_epoch == 1`, AMP scaler, optimizer tensors on `cuda:0`) before running round
   2 and asserting the cumulative `[1, 2]` history with no NaN/Inf.

Both fixes are covered by the preflight + pilot hash guards (which already include
`training/resumable_trainer.py`, `training/qam_aware_v3_3_trainer.py`,
`tests/test_qam_aware_v3_3_cuda.py`, `tests/test_qam_aware_v3_3_trainer.py`).

## M7. Numerical-stability repair — RTX 5090 non-finite loss (Phase 5, 2026-10-02)

The real RTX 5090 Stage-1 aborted with `V3.3 training produced a non-finite loss`.
Root cause: `-20 dB` frames reach `physical_max_abs ≈ 975.61`; the
`HigherOrderMomentPool` order-2/order-4 products overflow FP16 (`x² ≈ 951815 > 65504
→ Inf`, `x⁴ → NaN`). The fix clamps the expert's physical input to `[-2, 2]` (the
deployment dequant range `int8·(2/127)`) *before* the moment pool, built from
Add/Mul/Relu over pre-registered 1-D buffers — no `Clip`/`Sub`/`Constant`, so the
partition stays on the 8-op whitelist (`|x| ≤ 2 ⇒ x⁴ ≤ 16`). Frozen V2 input/behavior
unchanged; `gate=0` still element-wise equals V2. Numerically-sensitive losses are
computed in FP32, and a non-finite loss raises with full diagnostics (never
swallowed/replaced). A release-blocking full-SNR CUDA gate
(`tests/test_qam_aware_v3_3_full_snr_cuda.py`, A1/A2/A3 over 21 SNR) runs at
preflight step `[2]` before the smoke. Full detail in
`docs/v3_3_phase5_stability_fix_report.md`.

## N. Packaging and reproducibility

`scripts/package_qam_aware_v3_3_autodl.py` produces
`dist/qam_aware_v3_3_autodl.zip` with an LF-only `sha256_manifest.txt` whose
digests match every packaged file (verified by test). AutoDL shell scripts pass
`bash -n`. The authoritative archive SHA256 / size / manifest count is recorded in
`pretraining_readiness.json` (a local tracker that is not shipped, so the archive
never needs to self-reference its own digest); the pre-Phase-5 `baabc407…` build is
discarded.

## O. Literature and method–hardware matrix

See `docs/literature_review.md` (ControlNet zero-init gate, HOC/power moments,
parameter-efficient adaptation, CORAL/DANN domain alignment, QAT) and
`docs/method_hardware_matrix.md` (per-component operator decomposition).

## P. Readiness verdict, AutoDL command, and residual risks

**Verdict: ready to ship to AutoDL, but the CUDA formal-training preflight is
pending execution on the real GPU.** The first stage is the CUDA preflight-only
gate (never `run_complete.sh` until it passes):

```bash
bash autodl_v3_3/run_preflight.sh
```

Only after `V3_3_PREFLIGHT_FUNCTIONAL_PASS` is pasted back may the one-command
workflow (`bash autodl_v3_3/run_complete.sh`) be considered fully ready — a CPU
skip is never accepted as a CUDA pass, and the local host cannot produce that
pass on its own.

Residual risks (unchanged from design):

1. **FPGA-sim gap under training.** The 2-epoch smoke shows an FP32-vs-FPGA-sim
   accuracy gap larger than the 0.03 floor (0.087) — expected for a 2-epoch model,
   but the gap floor is exactly the gate that must be watched in the formal run;
   if A1 alone cannot clear it, A3's consistency loss is the intended remedy.
2. **QAM gain vs non-QAM regression.** The per-class regression floors (≤0.03)
   and the A0 fallback ("V2 can win") bound this risk; V2 stays champion if V3.3
   cannot clear every floor.
3. **AutoDL reproducibility.** Resumed runs export `CUBLAS_WORKSPACE_CONFIG=:4096:8`
   for bit-reproducibility; any seed that cannot resume cleanly is restarted.
4. **Unattributable wins are rejected.** Because candidates are validated
   individually, a stacked-variant win is impossible by construction.
