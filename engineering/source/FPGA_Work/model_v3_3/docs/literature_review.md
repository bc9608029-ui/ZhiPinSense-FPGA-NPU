# V3.3 Literature Review — Frontier AMC Ideas and How They Map to the Design

This note records the recent automatic-modulation-classification (AMC) results and
adjacent methods that motivated V3.3, and — critically — how each idea is *used*
or *deliberately rejected*. V3.3 is a pre-training preparation pass only; no
formal GPU training is started from any claim here. Each citation is a real,
published work; the mapping column is the design consequence, not a performance
claim.

## 1. Deep learning for AMC — the baseline consensus

- O'Shea, Roy & Clancy, *Over-the-Air Deep Learning Based Radio Signal
  Classification*, IEEE JSTSP 2018 (RadioML 2016/2018).
- O'Shea & Hoydis, *An Introduction to Deep Learning for the Physical Layer*,
  IEEE TCCN 2017.
- West & O'Shea, *Deep Architectures for Modulation Recognition*, DySPAN 2017.

These established the standard I/Q (and I/Q+features) CNN baselines. V2 — the
frozen champion `frozen_qam_aware_v2_time_power_phase` — is exactly this class of
network (time-branch 1-D conv + physical-feature branch + fusion classifier), so
V3.3 treats it as a frozen, verified asset rather than re-deriving it.

## 2. Hand-crafted higher-order statistics help QAM ring separation

- Swami & Sadler, *Hierarchical Digital Modulation Classification Using Cumulants*,
  IEEE TCOM 2000 (HOC — higher-order cumulants).
- Zhang, Xu, et al., HOC- and constellation-based AMC; power-of-moment features for
  16QAM/64QAM amplitude-ring discrimination.

HOC is the one V3.1/V3.2 result that genuinely improved the 16QAM/64QAM
amplitude-ring boundary. V3.3 keeps this insight but scopes it narrowly: the
residual expert consumes `E[x], E[x²], …, E[x^order]` of the three physical planes
(power, lag1_real, lag1_imag) and can only *additively* correct the V2 logits.
`order=2` reproduces V2's `StatisticalPooling1D` exactly, so the expert's input is
a strict superset of what V2 already used.

## 3. Parameter-efficient fine-tuning of a frozen backbone

- He, Zhang, Ren & Sun, *Deep Residual Learning for Image Recognition*, CVPR 2016
  (residual learning).
- Hu et al., *LoRA: Low-Rank Adaptation of Large Language Models*, 2021 (parameter-
  efficient adaptation).
- Zhang, Rao & Agrawala, *Adding Conditional Control to Text-to-Image Diffusion
  Models* (ControlNet), 2023 — the **zero-init gate** that reproduces the frozen
  backbone exactly at initialization, then learns a bounded additive correction.

V3.3's `BoundedResidualExpert` is the ControlNet "zero-convolution" idea applied
to AMC: `logits = v2_logits + gate * delta` with `gate = 0` at init, so
`max_abs_diff(V3.3, V2) == 0` before training and the correction can only grow
under an explicit gate + residual L2 penalty + optional deployable hard clamp.

## 4. Truly freezing the source model

- The V3.2 failure audit (see `v3_2_failure_audit.md`) is the direct evidence:
  V3.2 froze only 6 affine-norm parameters, leaving 72,025/72,031 trainable, and
  the backbone drifted 42.16% / 25.30% / 9.05% across seeds 2026/2027/2028.

V3.3's `freeze_v2_backbone` pins every V2 parameter *and* the BatchNorm running
statistics (eval mode re-applied on every `model.train()`), so no drift is possible
by construction. This is the single most important design decision.

## 5. Multitask / auxiliary-head regularization

- Ruder, *An Overview of Multi-Task Learning in Deep Neural Networks*, 2017.
- Multitask auxiliary losses as representation regularizers in AMC (family-level
  PSK/QAM/FSK/OFDM supervision).

A2 adds a train-only family head (`PSK/QAM/FSK/OFDM`) that regularizes the shared
hidden representation. It is deliberately excluded from the exported graph so it
can never violate the NPU operator policy.

## 6. Domain adaptation / numeric-domain consistency

- Sun & Saenko, *Deep CORAL: Correlation Alignment for Deep Domain Adaptation*,
  ECCV 2016.
- Ganin et al., *Domain-Adversarial Training of Neural Networks* (DANN), JMLR 2016.
- The FPGA's Q15→SInt8→host-dequant input contract is a fixed numeric domain the
  deployed graph must tolerate (see `deployment/numerical_contract.py`).

A3 adds a train-only dual-domain consistency loss between the FP32 path and the
FPGA Mandatory-Core emulated path. Only one mechanism is enabled per ablation
(V3.3 default: logit MSE "consistency"), and the promotion gate now includes an
FPGA-sim-vs-FP32 gap floor (`maximum_fpga_sim_*_gap = 0.03`).

## 7. Quantization-aware training and robustness to the deployed domain

- Jacob et al., *Quantization and Training of Neural Networks for Efficient Integer
  Arithmetic Inference*, CVPR 2018 (QAT).
- Krishnamoorthi, *Quantizing Deep Convolutional Networks for Efficient Inference*,
  2018.

V3.3 does **not** insert fake-quant nodes into training (that would mutate the
frozen contract); instead it keeps a bit-exact `DeploymentInputEmulator` mirror of
the Mandatory-Core reference and gates the FP32-vs-FPGA-sim gap offline.

## 8. Ideas considered and rejected (with reason)

- **Transformer attention, softmax routing, GRU/LSTM, capsule, FFT/STFT** — all
  rejected: they fall outside the NPU operator policy
  `{Add, BatchNormalization, Concat, Conv, Gemm, Mul, ReduceMean, Relu}`.
- **Stacking A1+A2+A3 simultaneously** — rejected: candidates are validated
  individually (one mechanism per ablation), never stacked, so the winning
  mechanism is attributable.
- **Forced 60-epoch full trajectory** (V3.1) — rejected: checkpoint selection is on
  macro-F1 with a minimum-epoch floor of 10 and early stopping.
- **QAM reweighting of the base classifier** (V3.1) — rejected: all classes keep
  weight 1.0; improvement must come from the residual expert alone.

## Summary mapping

| Idea | Paper(s) | V3.3 consequence |
| --- | --- | --- |
| I/Q+feature CNN | RadioML / DeepSig | frozen V2 backbone (unchanged) |
| HOC / power moments | Swami-Sadler 2000 | residual expert input = `E[x^k]` of 3 planes |
| Zero-init residual gate | ControlNet 2023 / ResNet 2016 | `logits = v2 + gate·delta`, `gate=0` at init |
| Parameter-efficient adaptation | LoRA 2021 | only 681 trainable expert params; 71,662 frozen |
| Multitask aux head | Ruder 2017 | A2 family head (train-only) |
| Domain alignment | CORAL / DANN | A3 dual-domain consistency + FPGA-sim gap floor |
| QAT | Jacob 2018 | bit-exact input emulator + offline gap gate |
