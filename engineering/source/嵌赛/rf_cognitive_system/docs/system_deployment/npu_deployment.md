# NPU deployment plan for TimePowerPhase

## Exported graph boundary

The frozen candidate can be represented in two equivalent forms:

1. PC end-to-end reference: input `iq[1,2,1024]`, internal Power/Lag-1,
   output `logits[1,8]`.
2. Planned hardware partition: FPGA supplies Power/Lag-1; NPU receives
   `iq[1,2,1024]` and `physical_features[1,3,1024]`, channel order
   `[power, lag1_real, lag1_imag]`, and outputs `logits[1,8]`.

Both use NCL layout. Class order is exactly:
`BPSK, QPSK, 8PSK, 16QAM, 64QAM, 2FSK, CPFSK, OFDM`.

The NPU-side graph keeps the learned TimePowerPhase layers unchanged. A PyTorch
parity test requires bit-identical logits when its physical input is produced
by the original float frontend.

## Operator policy

The graph is restricted to standard real-valued operations: Conv1D,
BatchNormalization, ReLU, Add, Mul, ReduceMean, Concat, Flatten/Reshape and
Gemm. There are no complex tensors, FFT, `angle`, square root, attention,
dynamic loop or data-dependent Python branch.

ONNX checker success proves graph validity, not NPU support. `TODO-NPU`: run
the exact board-supplied Icraft/versioned converter and record which operations
are native, fused, CPU-fallback or rejected. No fallback is acceptable in the
final latency claim without being disclosed.

## INT8 feasibility

INT8 is feasible in principle because all learned layers are conventional
Conv/Linear/BatchNorm/ReLU and BatchNorm can normally be folded into Conv.
The main risk is not weights but the very different dynamic ranges of IQ,
Power and signed correlation.

Recommended sequence:

1. Keep a verified FP32 ONNX reference.
2. Create a deterministic, class/SNR-balanced calibration set from the frozen
   training distribution only. Do not use development_test or final blind.
3. Fold BatchNorm where the vendor converter supports it.
4. Use symmetric per-channel weight quantization. Prefer separate activation
   scales for IQ, Power, CorrRe and CorrIm. Zero point should be zero for signed
   correlation and IQ.
5. Reproduce the selected scales in `feature_quantizer_axis` using round-to-
   nearest, explicit saturation and configurable shifts/multipliers.
6. Compare FPGA tensor dumps, dequantized NPU inputs, intermediate activations
   where available and final logits against PyTorch.
7. Predeclare an acceptance target such as less than 1 percentage point loss in
   development Accuracy and QAM high-SNR mean. If PTQ misses it, consider a
   short, separately approved QAT run without changing model structure.

Power uses an unsigned exact representation, but the NPU tensor may remain
signed INT8 after calibration. Correlation is signed. Do not force a single
scale across all three physical channels unless the toolchain requires it; if
it does, apply FPGA shifts first and record them in metadata/configuration.

## Runtime buffers

| Tensor | Logical shape | FP32 bytes | Planned INT8 bytes |
|---|---:|---:|---:|
| IQ | `[1,2,1024]` | 8192 | 2048 |
| Physical | `[1,3,1024]` | 12288 | 3072 |
| Logits | `[1,8]` | 32 | implementation dependent |

Use fixed batch 1 for streaming latency. Each input buffer must be contiguous,
aligned to the runtime/DMA requirement and owned by exactly one producer or
consumer. Frame ID and quantization scale/exponent are metadata, never model
features.

The CPU receives eight logits. Argmax yields the class; softmax is optional for
display confidence and need not consume NPU capacity. Unknown/open-set logic is
explicitly out of scope for this phase.

## Deployment gates

- ONNX opset 17 checker passes.
- PyTorch end-to-end and external-feature partition logits match.
- Icraft conversion completes with no undisclosed fallback.
- FP32/INT8 runtime logits meet the declared tolerance on replay vectors.
- Development metrics meet the quantization acceptance threshold.
- FPGA and PC feature tensors match after fixed-point scaling.
- Board latency, throughput, memory, power and temperature are measured, not
  estimated.
