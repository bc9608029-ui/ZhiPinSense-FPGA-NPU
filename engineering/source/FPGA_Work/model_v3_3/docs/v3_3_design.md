# V3.3 Design — Truly-Frozen V2 + Bounded Residual Expert

V3.3 is a pre-training preparation pass. This document specifies the architecture,
the candidate space, the training/evaluation procedure, the selection rule, and the
promotion gate — everything needed so that the *only* remaining step is the formal
GPU run on AutoDL.

## 1. Objective

Produce a **single deployable model** that:
1. improves QPSK/8PSK and 16QAM/64QAM fine-grained confusion;
2. does **not** sacrifice BPSK/CPFSK/OFDM;
3. tolerates SNR/channel/hardware numeric-domain variation;
4. exports to the ZG330 NPU / iCraft 3.39 under the frozen operator policy;
5. changes none of the FPGA Mandatory Core, the 5-plane tensor contract, or the
   verified bitstream.

## 2. Architecture

```
QAMAwareRFNetV33
  ├─ physical_frontend : PowerLagOneFeatures()        # training/eval only
  ├─ deployment_emulator : DeploymentInputEmulator()   # A3 / FPGA tests only
  └─ core : QAMAwareRFNetV33Core                       # <== exported NPU graph
       ├─ v2_backbone : V2BackboneCore                 # frozen V2, strict load
       │    ├─ time_branch       : DeployableTimeFeatureExtractor(22)
       │    ├─ physical_branch   : DeployablePhysicalFeatureEncoder(3, 8)
       │    └─ classifier        : FusionClassifier(120, 64, 8, 0.1)
       └─ expert      : BoundedResidualExpert          # A1+ only
            ├─ moment_pool : HigherOrderMomentPool(order=4)
            ├─ mlp         : Linear(12→32)→ReLU→Linear(32→8)
            └─ gate        : nn.Parameter(zeros(1))
```

The deployable forward is `logits = v2_logits + clamp(gate * delta, ±residual_bound)`.
The clamp is applied to the **final residual** `gate * delta` (not to `delta`), so the
residual added to the V2 logits is provably bounded. At initialization `gate = 0`, so
`V3.3(x) == V2(x)` element-wise (`max_abs_diff < 1e-6`). With `residual_bound = 1.0`
(the configured value), `|logits - v2_logits| ≤ 1.0` under *any* input — asserted by a
regression test that drives the expert weights and gate to extreme values.

The clamp is realised with Add/Mul/Relu only (no `Clip`, no `Sub`, no `Constant`):
`clamp(x, ±b) = b + (-1)·ReLU(2b + (-1)·ReLU(x + b))`. `b`, `2b`, and `-1` are
pre-registered as buffers (`_clamp_bound`, `_two_bound`, `_neg_one`) so ONNX
constant-folding cannot collapse `b + b` or the `-1` scalar into a `Constant` node.

## 3. Candidate space (validated individually, never stacked)

| Candidate | Definition |
| --- | --- |
| A0 | Frozen V2 baseline (`residual_expert.enabled = false`); real dev metrics; can win |
| A1 | A0 + zero-gated bounded residual expert (`gate_init = 0.0`) |
| A2 | A1 + train-only family aux head (PSK/QAM/FSK/OFDM) |
| A3 | A2 + dual numeric-domain consistency (FP32 vs FPGA Mandatory-Core emulation) |

Only the `core` is exported; the family head and consistency machinery are
train/eval-only and can never leak into the deployed partition.

## 4. Numeric-domain handling

- `simulate_hardware_inputs: false` by default → V3.3 trains/evaluates in full
  precision, exactly the condition that makes init-equivalence hold.
- The `DeploymentInputEmulator` mirrors the frozen Q15→SInt8→host-dequant contract
  bit-exactly (IQ `1/127`, physical `2/127`, round-nearest-away-from-zero, saturate
  `[-127,127]`); it feeds the A3 consistency loss and the FPGA-sim gap gate.

## 5. Training

- Frozen V2 backbone: `requires_grad_(False)` + eval mode (re-applied on every
  `model.train()`); 71,662 params frozen, 681 trainable (A1).
- Optimizer AdamW, cosine schedule, grad clip 5.0, AMP, label smoothing 0.
- Class weights all 1.0 (no QAM reweighting).
- Loss = CE(+label smoothing) + `residual_penalty_weight·‖delta‖²`
  + `family_aux_loss_weight·CE_family` + `domain_consistency.weight·MSE(logits)`.
  `residual_bound = 1.0` and `residual_penalty_weight = 0.01` are the finite,
  ablable defaults (never `0`/unbounded). All train-only terms default to 0.
- Checkpoint on `val_macro_f1` (max), `minimum_epochs_before_stopping: 10`, early
  stopping patience 12.

## 6. Stage-1 selection (two validation seeds, 15 epochs)

**Data isolation.** Stage-1 trains and evaluates on the `v3_3_validation` namespace
only — never the `test` (development) namespace and never `v3_3_final_blind_test`.
A split-access guard (`training/v3_3_split_guard.py`) wraps the whole Stage-1 run and
raises immediately if either forbidden split is instantiated; an `access_audit.json`
recording every accessed split is written and is a precondition for the formal stage.
The two selection seeds (2026/2027) change **both** training randomness **and** the
validation data seed, so each candidate is genuinely re-trained and re-evaluated.
A0 (frozen V2) is re-inferred from the real V2 checkpoint on the same two validation
seeds (FP32 + FPGA-sim + OOD) — metrics are never copied from the acceptance YAML.

**Synthetic OOD.** Each seed is also evaluated on a synthetic OOD battery — CFO, SFO,
phase offset/noise, IQ imbalance, Rayleigh/Rician fading, multipath parameter
variation, amplitude & sample-start variation, and at least one cross-parameter-family
/cross-generator holdout. OOD metrics enter selection only (never the test or blind
evaluation).

Fixed lexicographic rule (`select_qam_aware_v3_3_candidate.py`):
1. two-seed mean macro-F1 (desc) → 2. worst-seed macro-F1 (desc) →
3. worst-domain OOD macro-F1 (desc) → 4. mean accuracy (desc) →
5. mean QAM accuracy (desc) → 6. worst-class regression vs **same-seed A0** (asc) →
7. FPGA-sim accuracy gap (asc) → tie-break variant name (asc).

Every regression baseline is the **same-seed A0** (frozen V2) re-inferred on the
identical `v3_3_validation` data — candidate seed 2026 vs A0 seed 2026, seed 2027 vs
A0 seed 2027, and each OOD domain vs the same-seed, same-domain A0 result. The
Stage-1 ranking therefore never depends on the acceptance YAML's V2 *test*-namespace
per-class numbers.

A0 participates and may win (`promoted: false` ⇒ V2 stays champion; formal run
skipped, `no_promotion.json` written).

**Pilot hard gates (pre-formal go/no-go).** A trained candidate is promoted only if
**all** of the following hold, each measured against the same-seed A0 baseline:

1. two-seed mean validation macro-F1 improves over A0 by `≥ 0.01`;
2. every seed's macro-F1 is not below the same-seed A0 macro-F1;
3. every seed's worst-domain OOD macro-F1 drops `≤ 0.01` below the same-seed A0;
4. every seed, every class validation accuracy drops `≤ 0.03` below same-seed A0;
5. every seed's FPGA-sim accuracy gap `≤ 0.03`;
6. every seed's FPGA-sim macro-F1 gap `≤ 0.03`;
7. no NaN / Inf / timeout / missing metric.

Any gate failure disqualifies the trained candidate (the winner falls back to A0 /
frozen V2, `promoted: false`, and the exact failed gate is printed). Hard gates are
constraints, not ranking tie-breakers — a `+0.01` mean macro-F1 gain alone never
promotes a candidate that regresses a class, an OOD domain, or the FPGA-sim gap.

**Narrow search.** A budget-controlled random search (`training/narrow_search_v3_3.py`,
**enabled by default**) tunes the expert's own knobs — expert learning rate, residual
bound, residual penalty, family auxiliary weight, numeric/domain consistency weight —
over the two fixed validation seeds + synthetic OOD (8 trials × 6 epochs, best point
re-confirmed at the full 15 epochs on both seeds). It runs **only on the actual
Stage-1 winning mechanism** (never a fixed A3) and only if that trained winner cleared
the preliminary improvement threshold; an A0 win or a below-threshold candidate stops
the search. The best configuration is frozen into `selected_candidate.yaml/.json`
(never a reference-only side output), and the tuned candidate is kept only if it
actually improves the untuned winner. Test/blind never participate in tuning.

## 7. Promotion gate (three seeds 2026/2027/2028, never lowered)

- **mean improvement**: 3-seed mean accuracy `≥ +0.02`, macro-F1 `≥ +0.02`,
  QAM mean `≥ +0.05` over V2.
- **per-seed regression floors**: every seed's per-class accuracy drop `≤ 0.03`
  and 0/10/20 dB SNR accuracy drop `≤ 0.01`.
- **FPGA-sim gap floor**: every seed's FP32-vs-FPGA-sim accuracy gap `≤ 0.03` and
  macro-F1 gap `≤ 0.03`.

PASS = all three halves hold on every seed.

## 7b. AutoDL pipeline — functional smoke vs performance pilot

Two distinct gates precede the formal run, and they are deliberately not conflated:

- **`run_preflight.sh`** = *functional* smoke: source tests + 2-epoch train/eval/ONNX
  export. It certifies only that the code runs and the 8-op export gate holds. A
  2-epoch model is expected to miss the 0.03 FPGA-sim floor; preflight does **not**
  certify performance readiness.
- **`run_pilot.sh`** = *performance* pilot: the full Stage-1 ablation + validation/OOD
  selection + pilot threshold. Only a pilot that satisfies its predefined conditions
  produces a promotion decision, and only that lets `run_complete.sh` enter the
  3-seed formal run.

Both scripts are hash-guarded: the pilot input hash covers the model, trainer,
evaluators, selection, the narrow-search code, the Stage-1 (search + pilot-gate)
config, acceptance, dataset/channel config, and the V2 checkpoint hash, so a changed
dependency invalidates a stale pilot/preflight result instead of reusing it.

## 8. Frozen contract (unchanged)

IQ `[1,2,1024]`, physical `[1,3,1024]`, logits `[1,8]`, class order
BPSK/QPSK/8PSK/16QAM/64QAM/2FSK/CPFSK/OFDM, SInt8 NCL, dequant `1/127`/`2/127`,
zero-point 0, round-nearest-away-from-zero, saturation `[-127,127]`, ONNX opset 17,
operator policy `{Add, BatchNormalization, Concat, Conv, Gemm, Mul, ReduceMean, Relu}`.

## 9. Config layout

- `configs/qam_aware_v3_3.yaml` — formal base (A1 default).
- `configs/qam_aware_v3_3_smoke.yaml` — 2-epoch / 3-SNR rehearsal.
- `configs/qam_aware_v3_3_stage1.yaml` — A0–A3 ablation plan.
- `configs/qam_aware_v3_3_acceptance.yaml` — V2 reference + promotion gates.
