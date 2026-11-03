# AD-AMR V1.1 design and acceptance contract

## Objective

Train one deployable ten-class IQ classifier for the contest demonstrator. The
model consumes a normalized complex-baseband record as `[N,2,1024]` and emits
ten logits. It is not a model ensemble at inference time.

## Architecture

The student consists of a shape-preserving residual denoiser, four stride-two
residual feature stages, temporal global-average pooling, and a two-layer linear
classifier. Its export path uses only `Conv`, `BatchNormalization`, `Relu`,
`Add`, `ReduceMean`, and `Gemm`, a strict subset of the frozen eight-op policy.

This is a deployability-oriented adaptation inspired by AD-AMR, not a claim of
an exact reproduction of the ICC 2024 network. The original V1 model remains a
teacher because its `Abs/Sign/Sub/Sigmoid/Resize/Squeeze/Unsqueeze` graph is not
accepted by the current NPU policy.

## Training

- Ground-truth cross-entropy for all ten classes.
- Small clean-IQ reconstruction loss on the residual denoiser.
- Frozen V2 and two-seed V1 logit distillation on the eight compatible outputs.
- SNR-aware weighting: very-low-SNR samples remain present but do not dominate;
  rated 0–20 dB and the 0 dB boundary receive extra weight.
- AdamW, ReduceLROnPlateau, FP16 AMP on CUDA, gradient clipping, strict resume.
- Checkpoint score = 45% full macro-F1 + 30% rated accuracy + 15% 0 dB
  accuracy + 10% worst-class accuracy.

## Data isolation

Training and model selection instantiate only `ad_amr_v1_1_train` and
`ad_amr_v1_1_validation*`. Any final-blind namespace raises immediately. Sample
IDs are split-hash namespaced, and the two seeds alter both train and validation
records. The ten-class order is asserted at dataset construction.

## Search budget

Stage A compares `student_only`, `v1_distill`, and `dual_distill` for 30 epochs
on seed 2026. The gate-aware winner is confirmed at 30 epochs on seeds 2026 and
2027. Only a pilot pass enables two-seed formal runs of up to 100 epochs.

## Formal validation gates

- Mean full-range macro-F1 and accuracy ≥ 0.72.
- Mean 0–20 dB accuracy ≥ 0.90.
- Mean 10–20 dB accuracy ≥ 0.95.
- Each seed's 0 dB accuracy ≥ 0.85.
- Each seed's worst rated-class accuracy ≥ 0.75.
- Each OOD macro-F1 drop ≤ 0.08.
- Fake symmetric INT8 weight accuracy drop ≤ 0.03.
- ONNX Runtime max absolute difference ≤ 0.001.
- Zero operators outside the NPU whitelist.

These are promotion requirements, not promised outcomes. Failure preserves the
previous champion and triggers analysis instead of lowering the gates.

## Remaining external gates

The source package cannot prove the vendor compiler, FPGA/NPU timing, SDR
front-end calibration, real-channel domain gap, or HDMI integration. After a
formal pass: compile the ONNX model, compare FP32/emulator/board logits on golden
vectors, then evaluate recorded and live PlutoSDR IQ without retraining on the
final evaluation capture.
