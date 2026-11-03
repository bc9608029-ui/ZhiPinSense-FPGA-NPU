# AD-AMR V1 — Pre-implementation audit record

Date: 2026-10-02.  Scope: audit of the paper (`ma.pdf`) and of the frozen V2/V3.x
track before any AD-AMR code was written.  This record is the evidence base for
every design choice in `docs/architecture_mapping.md` and
`docs/implementation_assumptions.md`.

## 1. The paper (`ma.pdf`, ICC 2024)

- **Title:** "Adaptive Denoising With Efficient Channel Attention for Automatic
  Modulation Recognition".
- **Architecture:** input `x ∈ R^{2×L}` (IQ-only) -> ADM (Adaptive Denoising
  Module) -> FEM (Feature Extraction Module) -> FCL -> Softmax.
- **ADM:** WaveUNet-style: L down-sampling blocks (1-D conv kernel 15 +
  downsampling + ECA) and L up-sampling blocks (1-D conv kernel 5 + upsampling +
  ECA), skip connections (crop-and-concat), concluding kernel-1 conv; output is a
  shape-preserving denoised IQ.
- **FEM (Table I):** Conv(k=3, s=1, 16 ch) then ERSB(k=3, s=2) at channels
  16, 32, 32, 64.
- **ERSB:** two conv + identity shortcut + adaptive soft-thresholding + ECA (ECA
  replaces the DRSN residual-shrinkage block's SE).
- **ECA:** GAP -> Conv1d -> Sigmoid -> channel-wise multiply.
- **Soft-threshold (Eq. 1):** piecewise shrink toward zero by threshold lambda.
- **Loss (Eq. 4):** `L = alpha * L_MSE + L_CE`, `alpha = 0.1`.  Eq. 4's L_MSE is
  the MSE between the *input noisy* signal and the *denoised output* — the unusual
  reading that motivates the P0 (literal) vs P1 (clean-supervised) split.
- **Training:** Adam, lr 0.001, 100 epochs, early stopping + ReduceLROnPlateau,
  RTX 3090, RadioML 2018.01A (24 mods, SNR -20:2:30, 6:2:2).  Paper results:
  OA 0.6460, F1 0.6480, Kappa 0.6306, 0-10 dB 0.8480, **0.25M params**.

## 2. Frozen V2 champion

- **Checkpoint:** `init/v2_time_power_phase_best.pt`
- **SHA-256:** `f9e4b5e5513f60907aa69416df3374353848272e14744cb193a46d06b02d71a6`
- **Size:** 962,417 bytes; checkpoint_version 2; 91 `model_state` keys.
- **Frozen test metrics (the authoritative champion facts):** accuracy 0.705476,
  macro-F1 0.697538, QAM mean 0.464762.
- **Class order:** BPSK, QPSK, 8PSK, 16QAM, 64QAM, 2FSK, CPFSK, OFDM.
- **Input:** IQ-only `[N, 2, 1024]` (I/Q stacked), float32; physical features
  `[N, 3, 1024]` are derived *inside* the model (power + lag-1 real/imag), not fed
  as a separate plane.  Sample rate 128000 Hz, symbol rate 16000 Hz, 1024 samples.
- **Architecture:** `TimePowerPhaseRFNet` = PowerLagOneFeatures (3 ch) -> time
  branch `TimeFeatureExtractor(22)` + physical branch `PhysicalFeatureEncoder(8)`
  -> `FusionClassifier(120, 64, 8)`.

## 3. Data split and namespace

- **Seed:** 2026.  **Split sizes:** train 25200 / val 5040 / test 8400.
- **SNR:** 21 points `[-20, -18, ..., 18, 20]`.
- **Namespace:** V2 uses `train`/`validation`/`test` (final blind test =
  `final_blind_test`, seed 26090831).  V3.3 uses `v3_3_*`.  AD-AMR V1 uses its own
  `ad_amr_train`/`ad_amr_validation`/`ad_amr_test` namespace so it can never
  collide with or read a prior track's split.
- **Determinism:** sample `index` -> `SeedSequence([seed, split_code, epoch, index])`
  with `split_code = blake2s(split_string)`; distinct split strings give distinct,
  non-overlapping sample-id ranges.

## 4. FPGA/NPU input contract and operator limits

- Inputs `iq [1,2,1024]` + `physical_features [1,3,1024]`, output `logits [1,8]`.
- Frozen 8-op NPU policy: Add, BatchNormalization, Concat, Conv, Gemm, Mul,
  ReduceMean, Relu; ONNX opset 17.
- AD-AMR is IQ-only, so it does not need the `physical_features` input, but its
  denoising front-end introduces ops outside the 8-op policy (Sigmoid, Abs, Sign,
  Resize/Upsample, Flatten) — documented in the deployment-gap report, never hidden.

## 5. Paper-unstated dimensions (=> implementation assumptions)

L (number of ADM levels), ADM channel counts, ECA kernel-size formula (gamma/beta),
down/up-sampling mechanism, soft-threshold scaling, FCL hidden size, dropout, batch
size, weight decay, LR-scheduler metric, and the number of classes' effect on FCL.
All are parameterized with documented defaults (see `implementation_assumptions.md`).

## 6. Prohibitions honored (verbatim, unchanged)

No formal AutoDL long training started; no final blind data accessed; no
board/SDR/FPGA; no modification of V2/V3/V3.1/V3.2/V3.3, RTL/golden/bitstream/
iCraft/EDIF/NPU project; no lowered comparison thresholds; no unstated
"paper settings"; no new-model validation compared to V2 test; P0/P1 differ only
in MSE target; final status only `ready-for-cuda-preflight` or `blocked`.
