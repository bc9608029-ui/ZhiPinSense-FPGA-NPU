# V3.2 Delivery Report — Frozen-V2 Backbone + Zero-Gated QAM Delta Branch

Scope: full V3.2 workflow from diagnosis through local testing to the AutoDL
training package. **No formal GPU training has been started**, per the freeze
constraints. This report is the A–N handoff that accompanies
`dist/qam_aware_v3_2_autodl.zip`.

---

## A. Diagnosis (V3.1 root cause)

Fully documented in [`docs/v3_1_diagnosis.md`](v3_1_diagnosis.md). Verdict:

V3.1 is a **capacity + loss-reweighting overfit**. It gained +0.138 QAM-mean by
systematically relabeling non-QAM classes as 64QAM (BPSK→64QAM ×195,
QPSK→64QAM ×222, 16QAM→64QAM ×345 in the V2-namespace confusion matrix). The
gains are subsidized: BPSK −0.0733, QPSK −0.1438, CPFSK −0.0829, OFDM −0.1029,
0 dB −0.046. The root design flaw (point 9) is a single monolithic classifier
whose only lever was class reweighting — there was **no mechanism to preserve
the V2 logit path while adding QAM discriminative power**.

V3.2 inverts this: keep V2's logit path **intact** and add a separate,
zero-gated QAM delta branch that can only *add* a correction, anchored to the
frozen V2 teacher by knowledge distillation.

## B. Design / goal

Documented in [`docs/v3_2_design.md`](v3_2_design.md). The governing equation:

```
logits = v2_logits + gate * delta_logits      (gate = nn.Parameter(zeros(1)))
```

with a small `HigherOrderMomentPool(order=4) → BN → Linear(12,16) → ReLU →
Linear(16,8)` delta branch. Two parameter-free deployability substitutions
(`AdaptiveAvgPool1d+Flatten → mean(dim=-1)`; `BatchNorm1d(3,affine=False) →
affine=True frozen weight=1/bias=0`) make the NPU partition use **only** the
eight allowed operators. The hard pre-training contract:

1. initial V3.2 logits **element-wise equal** to V2 (gate = 0);
2. gate and delta branch have **non-zero, finite gradients** (not dead);
3. NPU partition exports with **only** `{Conv, BatchNormalization, ReLU, Add,
   Concat, ReduceMean, Mul, Gemm}`.

## C. Model — `models/qam_aware_rfnet_v3_2.py`

- `MeanPool1D`, `DeployableTimeFeatureExtractor`, `DeployablePhysicalFeatureEncoder`
  (frozen affine input norm), `V2BackboneCore` (V2-identical `state_dict` keys),
  `QAMAwareRFNetV32Core` (`v2_logits + gate*delta`), `QAMAwareRFNetV32` wrapper
  (`simulate_hardware_inputs: false` by default).
- `build_qam_aware_v3_2`, `build_qam_aware_v3_2_partition`,
  `load_v2_into_v3_2` (prefixes `v2_backbone.`, synthesizes the two affine-norm
  keys as ones/zeros, `strict=True`), `qam_aware_v3_2_profile`.
- Profile: **72,031 params** (V2 backbone 71,656 + delta branch ~360 + gate 1),
  72,025 trainable. Input contract `iq [1,2,1024]` / `physical_features
  [1,3,1024]`, class order, tensor layout, quant scale 127 / zero-point 0 — all
  unchanged from V2.

## D. Config — `configs/`

- `qam_aware_v3_2.yaml` — formal: inherits baseline (V2-mild channel/dataset,
  21 SNR, seed 2026); `v2_checkpoint: init/v2_time_power_phase_best.pt`;
  model + training (60 epochs, batch 128, `checkpoint_metric: val_macro_f1`,
  distillation `{enabled, temperature 4.0, alpha 0.7}`); `final_blind_test`
  (seed 26093032, split `v3_2_final_blind_test`, 16800 samples).
- `qam_aware_v3_2_smoke.yaml` — 2-epoch/3-SNR/512-sample smoke overrides.
- `qam_aware_v3_2_acceptance.yaml` — V2 reference numbers + the five promotion
  gates (accuracy ≥ +0.02, macro-F1 ≥ +0.02, QAM-mean ≥ +0.05, per-class drop
  ≤ 0.03, 0/10/20 dB drop ≤ 0.01).
- `qam_aware_v3_2_ablation.yaml` — A1/A2/A3-1.05/A3-1.10 spec, 15 ablation epochs.

## E. Trainer — `training/qam_aware_v3_2_trainer.py`

`QAMAwareV32Trainer(QAMAwareV3Trainer)`: adds a frozen `teacher` and
`_distillation_loss = alpha·T²·KL(log_softmax(s/T), softmax(t/T),
reduction="batchmean")`; `_run_epoch` adds the KD term under `no_grad` teacher;
`_complete_checkpoint` records distillation metadata. Strict resume inherited
unchanged (macro-F1 selection + `minimum_epochs_before_stopping` floor).

`training/train_qam_aware_v3_2.py`: builds model → `load_v2_into_v3_2` →
builds the frozen V2 teacher from the checkpoint's own `qam_aware` config →
`_verify_init_matches_v2` (eval-mode, `<1e-5`) → `_finite_probe` → writes
`model_profile.json` / `effective_config.json` / `experiment_snapshot.json` →
trains → reloads best and re-verifies finite.

## F. Evaluation — `evaluation/`

- `evaluate_qam_aware_v3_2.py` — single `v2_compatible` suite on `split="test"`
  (the exact V2 namespace), writing `evaluation.json` + per-class / per-SNR /
  confusion CSVs.
- `check_qam_aware_v3_2_acceptance.py` — mirror of V3.1's fail-closed gate,
  exits 2 on any gate failure.
- `audit_qam_aware_v3_2_dataset.py` — delegates to the frozen dataset audit.

## G. Ablation — `training/train_qam_aware_v3_2_ablation.py`

Controlled train/val-only search over A1/A2/A3 (QAM weights ∈ {1.05, 1.10}).
Writes per-variant override YAML, runs `train_v3_2(stop_after_epoch=15)`, then
`ablation_comparison.csv` + `ablation_summary.json`. **A0 (frozen V2
re-evaluation) is implicit** — the acceptance gate compares against the V2
reference numbers baked into `qam_aware_v3_2_acceptance.yaml`; the V3.2
evaluator re-runs on the exact V2 namespace so the delta is apples-to-apples.

## H. Leakage prevention

- Selection uses **train + validation only**; the blind split
  (`v3_2_final_blind_test`) is never instantiated by training/selection code.
- Fixed seed, fixed split names, fixed SNR list — identical to V2's protocol.
- Pilot ≥2 seeds; final report 3 seeds with mean ± std. CIs are reported but
  never used to bypass a failed gate. Gates are never lowered.

## I. AutoDL — `autodl_v3_2/`

`setup_env.sh`, `run_smoke.sh`, `run_ablation.sh`, `run_pilot.sh`,
`run_formal.sh`, `resume_formal.sh`, and the 10-step one-command entry
`run_complete.sh` (smoke → audit → ablation → init==V2 verify → strict-resume
formal train → eval → ONNX export → acceptance gate → result packaging). Safe to
rerun after interruption: formal training resumes from `last.pt`. `README.md`
documents every step and the pass/fail markers.

## J. Tests — `tests/`

**31 smoke tests, all passing** (`pytest`, 15.0 s):

- `test_qam_aware_rfnet_v3_2.py` (10): shape/finite, partition identity,
  init==V2 element-wise, gate grad, delta grad, moment math, backprop, profile,
  smoke config, config wiring.
- `test_qam_aware_v3_2_trainer.py` (5): `CE + alpha·T²·KL` formula, teacher
  required, teacher frozen/eval + not in optimizer, distillation fit + best
  checkpoint, macro-F1 checkpoint selection.
- `test_qam_aware_v3_2_resume.py` (1): strict-resume equivalence under
  distillation (history/state/optimizer/scheduler/checkpoint identical).
- `test_qam_aware_v3_2_acceptance.py` (3): fail-closed below gates, missing
  suite raises, script exit code 2 on failed gate.
- `test_qam_aware_v3_2_onnx_gate.py` (4): clean partition passes, unexpected
  operator / wrong IQ shape / wrong output dtype each fail hard.

End-to-end smoke (`autodl_v3_2/run_smoke.sh`) completes with
`V3_2_AUTODL_SMOKE_PASS`, exporting a partition whose
`npu_partition_unexpected_operators` is `[]` and whose
`allowed_operator_policy` is exactly the eight-op list.

## K. Freeze constraints (unchanged, honored)

V2/V3/V3.1 code, checkpoints, ONNX, and result packages are untouched; the six
Mandatory Core RTL, the Python Golden, fixed IQ/tensor, FPGA/NPU numeric
contract, bitstream/LTX/capture/STA, the iCraft model, and the FMSH patch are
untouched. No board bring-up, no SDR entry, no NPU compile, and **no formal
AutoDL training started** from this session. All V3.2 work is confined to
`F:\FPGA_Work\model_v3_2\`.

## L. Delivery

`dist/qam_aware_v3_2_autodl.zip` — self-contained source archive (English-named,
`sha256_manifest.txt` inside) shipping `autodl_v3_2/`, `init/` (the frozen V2
checkpoint), `configs/`, `channel/`, `datasets/`, `deployment/`, `docs/`,
`dsp/`, `evaluation/`, `models/`, `scripts/`, `tests/`, `training/`,
`visualization/`, plus root `pyproject.toml`, `requirements_autodl_v3.txt`,
`train.py`, `generate_dataset.py`. Entry point:

```
bash autodl_v3_2/run_complete.sh
```

On success it prints `V3_2_AUTODL_COMPLETE_PASS`; on a failed gate it prints
`V3_2_AUTODL_COMPLETE_TRAINED_BUT_GATE_FAILED` and exits non-zero while V2 stays
the frozen champion. The result archive is
`outputs/qam_aware_v3_2/qam_aware_v3_2_formal_results.tar.gz`.

## M. What happens next (on AutoDL, not from here)

1. Unzip, `bash autodl_v3_2/run_complete.sh` on the RTX 5090 (torch 2.8.0+cu128).
2. Review the ablation table; promotion is decided **only** by the acceptance
   gate on the 3-seed formal run.
3. If `V3_2_AUTODL_COMPLETE_PASS` → V3.2 becomes champion; proceed to NPU
   compilation and deployment as a separate, authorized step.
4. If gate-failed → V2 stays frozen champion; diagnosis uses the result archive.

## N. Stop condition

**Work is complete and stops here.** No formal GPU training is started from this
session; the handoff is the AutoDL package above plus this report.
