# V3.2 Design — Frozen V2 Backbone + Zero-Gated QAM Delta Branch

## 1. Goal

Preserve the frozen V2 champion exactly and *incrementally* absorb V3.1's one
proven result — that higher-order amplitude moments are a strong QAM
discriminator — without reproducing V3.1's regressions.

Concretely, V3.2 must satisfy, before any training:

- initial V3.2 logits are **element-wise identical** to V2 logits (gate = 0);
- the delta branch and gate have **non-zero, finite gradients** (not dead);
- the NPU partition exports with **only** the eight allowed operators.

## 2. Architecture

```
iq [N,2,1024] ──▶ time_branch (V2, mean-pooled)  ─────────┐
                                                           ├─ cat ─▶ FusionClassifier ─▶ v2_logits ─┐
physical [N,3,1024] ─▶ physical_branch (V2, frozen affine BN) ─┘                              ┌── Add ─▶ logits
physical [N,3,1024] ─▶ HigherOrderMomentPool(order=4) ─▶ BN ─▶ Linear(12,16) ─▶ ReLU ─▶ Linear(16,8) ─▶ delta ─▶ Mul(gate) ┘
```

- `logits = v2_logits + gate * delta_logits`, with `gate` a **scalar**
  `nn.Parameter(torch.zeros(1))`.
- The V2 backbone is the deployable re-implementation of the frozen V2
  `TimePowerPhaseRFNet`; its parameters are **loaded strictly** from
  `init/v2_time_power_phase_best.pt` and its `requires_grad` is **left trainable**
  (anchored by distillation).
- The delta branch is small (`12 → 16 → 8`, ≈ 360 params) and uses only
  `Mul/ReduceMean/Concat/Gemm/Relu/BatchNormalization`.

### 2.1 The two deployability substitutions (parameter-free, numerically identical)

V2's own ONNX export contains operators outside the eight-op NPU policy
(`GlobalAveragePool`, `Flatten`, `Constant`, `Identity`, `Slice`, `Sub`). Two of
these live in the backbone (the rest are the fixed physical frontend, which is
excluded from the partition). V3.2 replaces them without changing any learned
parameter or key:

1. `TimeFeatureExtractor`: `nn.AdaptiveAvgPool1d(1)` + `nn.Flatten()`
   → a single `mean(dim=-1)` (`ReduceMean`). Same `[N, 4c]` output, no parameters.
2. `PhysicalFeatureEncoder` input norm: `nn.BatchNorm1d(3, affine=False)`
   → `nn.BatchNorm1d(3, affine=True)` frozen at `weight=1, bias=0`
   (`requires_grad_(False)`). Numerically identical to `affine=False`, exports as
   initializers instead of `Constant` nodes.

Both keep the `state_dict` keys of the param-bearing layers identical to V2
(indices 0–4 in `time_branch`, 0–6 in `physical_branch`, 0/3 in `classifier`).
The only synthesized keys are `physical_branch.network.0.weight/bias`, created as
ones/zeros during loading (see §3).

### 2.2 Input contract (unchanged from V2)

- `iq` FP32 `[1,2,1024]` `[I,Q]` order; `physical_features` FP32 `[1,3,1024]`
  `[power, lag1_real, lag1_imag]` order.
- Class order `[BPSK, QPSK, 8PSK, 16QAM, 64QAM, 2FSK, CPFSK, OFDM]`, tensor
  layout, quantization scale (127) and zero-point (0) all unchanged.
- Training uses `simulate_hardware_inputs: false` (full-precision, exactly as
  the frozen V2 was trained/evaluated). This is what makes "init == V2"
  verifiable end-to-end and keeps the promotion comparison apples-to-apples.
  The `DeploymentInputEmulator` and the quantized partition remain available and
  unchanged; the deployment contract is untouched.

## 3. Strict V2 parameter loading

`load_v2_into_v3_2(model, checkpoint)`:

1. Read `checkpoint["model_state"]` (91 keys).
2. Prefix every key with `v2_backbone.`.
3. Synthesize `v2_backbone.physical_branch.network.0.weight = ones(3)` and
   `.bias = zeros(3)` (the only keys V2's `affine=False` norm does not store).
4. `model.core.v2_backbone.load_state_dict(..., strict=True)` — any other key
   mismatch (missing or unexpected) is a hard error, so no parameter is ever
   silently dropped or randomly initialized.

This is verified by `test_initial_logits_equal_v2` (see §7).

## 4. Knowledge distillation

- **Teacher**: frozen V2 `TimePowerPhaseRFNet` loaded from
  `init/v2_time_power_phase_best.pt`, set to `eval()`, all params
  `requires_grad_(False)`. It is never part of the student graph or the ONNX
  export; it only produces soft targets during training.
- **Student**: the V3.2 wrapper.
- **Loss** (following the specification verbatim):

  ```
  loss = CrossEntropy(student_logits, y)
       + alpha * T^2 * KL( softmax(student_logits/T), softmax(teacher_logits/T) )
  ```

  with `temperature T` (default 4.0) and `alpha` (default 0.7). At initialization
  student == teacher, so the KL term starts at zero and only grows to the extent
  the delta branch genuinely improves the fit.

## 5. Controlled ablations (small, train/val-only)

All candidates share the same V2-initialized backbone + delta branch and the
same fixed split/seed. They differ only in the loss:

| id | description | distill | QAM class weights |
|---|---|---|---|
| A0 | frozen V2 re-evaluation (no training) — establishes the exact baseline | — | — |
| A1 | zero-gated delta branch, plain cross-entropy | off | all 1.0 |
| A2 | A1 + knowledge distillation | on | all 1.0 |
| A3 | A2 + mild QAM weights | on | 16QAM/64QAM ∈ {1.05, 1.10} |

QAM weights are searched only over `{1.05, 1.10}` (the user-specified small
search). Every candidate is selected on validation only and evaluated on the
exact V2 `test` namespace; the final blind set is never touched.

## 6. Leakage prevention

- Candidate selection uses **train + validation only**; the blind test split is
  never instantiated by training or selection code.
- Fixed `seed`, fixed `split` names, fixed SNR list — identical to V2's frozen
  protocol.
- Pilot runs use ≥2 seeds; the final report uses **3 seeds** with mean ± std and
  paired-bootstrap CIs on the exact V2 namespace.
- The promotion decision is made by the acceptance gate (below); CIs are reported
  but never used to bypass a failed gate.

## 7. Promotion gates (never lowered)

| gate | bar |
|---|---|
| accuracy gain | ≥ +0.02 |
| macro-F1 gain | ≥ +0.02 |
| QAM mean gain | ≥ +0.05 |
| per-class accuracy drop | ≤ 0.03 (any class) |
| key-SNR (0/10/20 dB) accuracy drop | ≤ 0.01 |

Ordered Pareto selection: first reject any candidate that violates a per-class or
per-SNR regression cap, then maximize accuracy/macro-F1/QAM-mean. Gates are
enforced by `check_qam_aware_v3_2_acceptance.py`, which fails closed.

## 8. Test contract (13 categories)

1. Output shape `[N,8]` and finite values.
2. Partition (`build_qam_aware_v3_2_partition`) is exactly the training core.
3. **Initial logits == V2 element-wise** (gate = 0, backbone == V2).
4. **gate has non-zero finite gradient** at initialization (can leave zero).
5. **delta branch has non-zero finite gradient** once the gate is non-zero (not a dead branch).
6. Higher-order moment pool computes exact E[x^k].
7. Backprop produces finite loss/gradients.
8. Profile is bounded and the deployment contract string is present.
9. Config keeps the frozen class order / 1024-frame / physical-channels contract.
10. Config wires distillation + checkpoint-selection + no-blind-access.
11. Trainer checkpoint selection tracks macro-F1 and honors the minimum-epoch floor.
12. Distillation loss equals `CE + alpha·T²·KL` (unit test) and teacher is frozen.
13. ONNX export gate passes a clean partition and rejects any unexpected operator / wrong I/O.

## 9. Freeze constraints (unchanged)

V2/V3/V3.1 code, checkpoints, ONNX, and result packages are never modified.
All V3.2 work lives in `F:\FPGA_Work\model_v3_2\`. No board bring-up, no SDR
entry, no NPU compile, and no formal AutoDL GPU training is started from here.
