# V3.3 Method ↔ Hardware Deployability Matrix

This matrix is the *binding* cross-check between each architecture candidate and
the frozen FPGA/NPU constraints. The constraints are never relaxed; a candidate
that cannot satisfy a row is rejected, not patched.

## Frozen constraints (source of truth)

| Constraint | Value |
| --- | --- |
| IQ input | `[1, 2, 1024]` |
| Physical planes | `[1, 3, 1024]` = power, lag1_real, lag1_imag |
| Output logits | `[1, 8]` |
| Class order | BPSK, QPSK, 8PSK, 16QAM, 64QAM, 2FSK, CPFSK, OFDM |
| Quantization | SInt8, NCL; IQ dequant `1/127`, physical dequant `2/127`, zero-point 0, round-nearest-away-from-zero, saturate `[-127, 127]` |
| Operator policy (hard gate) | `Add, BatchNormalization, Concat, Conv, Gemm, Mul, ReduceMean, Relu` |
| Forbidden ops | Transformer attention, Softmax routing, GRU/LSTM, FFT/STFT, Capsule, LayerNorm, dynamic control flow, custom ops |
| ONNX | opset 17 |
| Export target | ZG330 NPU / iCraft 3.39 |

## Candidate matrix

| Candidate | Deployable graph | Train-only machinery | Trainable params | Operator-safe? |
| --- | --- | --- | --- | --- |
| A0 (frozen V2) | V2 `TimePowerPhaseRFNet` exactly | none | 0 | yes (unchanged V2) |
| A1 (residual expert) | `core` = V2 backbone + `BoundedResidualExpert` | none | 681 (expert only) | yes |
| A2 (family multitask) | same as A1 | family head (`PSK/QAM/FSK/OFDM`) | 681 + family head | yes |
| A3 (domain consistency) | same as A1 | dual-domain consistency loss | 681 + family head | yes |

## Operator-level decomposition of the deployable A1 graph

The NPU partition is `source.core` (see `build_qam_aware_v3_3_partition`); the
physical frontend and input emulator are training/evaluation-only and excluded.

| Component | Ops used | Policy-compliant |
| --- | --- | --- |
| Time branch conv + BN + ReLU + residual blocks | `Conv`, `BatchNormalization`, `Relu`, `Add` | yes |
| Global temporal pool | `ReduceMean` (replaces `AdaptiveAvgPool1d`+`Flatten`) | yes |
| Physical branch (affine input norm + conv + residual) | `BatchNormalization`, `Conv`, `Relu`, `Add` | yes |
| Statistical pool | `ReduceMean`, `Mul`, `Concat` | yes |
| Fusion classifier | `Gemm` (Linear) | yes |
| HigherOrderMomentPool | `Mul`, `ReduceMean`, `Concat` | yes |
| Residual expert MLP | `Gemm`, `Relu` | yes |
| Expert combine | `Add` (v2_logits + gate·delta), `Mul` (gate·delta) | yes |
| Optional hard clamp | `Add`, `Mul`, `Relu` only (no `Clip`/`Constant`/`Sub`) | yes |

## Export gates (never lowered)

1. **Partition gate** — the exported `qam_aware_v3_3_npu_partition_opset17.onnx`
   must contain *only* the 8 allowed operators, `[1,2,1024]`+`[1,3,1024]` in and
   `[1,8]` out, FLOAT dtype. Any unexpected node hard-fails (see
   `scripts/export_qam_aware_v3_3_onnx.py::_gate_partition`).
2. **End-to-end gate** — `qam_aware_v3_3_e2e_opset17.onnx` wraps the frontend; used
   for host-side parity checks only, never deployed as-is.
3. **FPGA-sim gap floor** — the promotion gate requires every seed's
   FP32-vs-FPGA-sim accuracy/macro-F1 gap `<= 0.03` (`maximum_fpga_sim_*_gap`).

## Why the residual expert has no BatchNorm

The physical planes are already O(1) in both the full-precision and FPGA-emulated
domains. An eval-mode `BatchNormalization` in the expert exported as a
`BatchNormalization` node that some torch versions decorate with `Identity` aliases
outside the 8-op policy. Removing it keeps the expert strictly `Gemm/Relu/Add/Mul`
and makes the export deterministic. The single `Linear` layer learns the scale
instead.

## Deployment partition contract (must not change)

The five-plane tensor contract, the `1/127`/`2/127` dequant scales, SInt8 NCL
storage, round-nearest-away-from-zero, and saturation `[-127,127]` are all frozen.
V3.3 changes none of them; it only adds a trainable residual term that is bounded
and additive on top of the unchanged V2 logits.
