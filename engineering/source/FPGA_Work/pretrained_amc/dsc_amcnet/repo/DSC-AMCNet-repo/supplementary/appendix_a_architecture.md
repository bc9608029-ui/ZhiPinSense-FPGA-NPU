# Appendix A: DSC-AMCNet Architecture Specification

Full layer-by-layer specification of DSC-AMCNet as deployed in the paper
(Table V). Corresponds to `models/dsc_amcnet.py` (`width=24`) and to the
released checkpoint `dscamcnet_best.pt` (loads with `strict=True`).

## Input

| Property | Value |
|---|---|
| Format | (batch, 2, 128) — 2-channel (I/Q), 128 time samples |
| Dtype | float32 (training), signed INT8 (deployment) |
| Source | RML2016.10a 128-sample complex IQ windows |
| Normalization | Per-window L2 norm (paper Section III-C) |

## Layer-by-Layer Table (paper Table V)

All conv layers `bias=False`; FC layers include bias; params include BN
scale/shift (BN = BatchNorm1d, 2C params). DWC = depthwise Conv1d (g=C);
PWC = pointwise Conv1d (k=1).

| Block | Operation | Output shape | Params |
|---|---|---|---|
| Stem | PWC(2→24), BN, ReLU | (B, 24, 128) | 96 |
| DSC-1 | DWC(k=3), BN, ReLU | (B, 24, 128) | 120 |
|       | PWC(24→24), BN, ReLU | (B, 24, 128) | 624 |
|       | MaxPool1d(k=2) | (B, 24, 64) | — |
| DSC-2 | DWC(k=3), BN, ReLU | (B, 24, 64) | 120 |
|       | PWC(24→24), BN, ReLU | (B, 24, 64) | 624 |
|       | MaxPool1d(k=2) | (B, 24, 32) | — |
| DSC-3 | DWC(k=3), BN, ReLU | (B, 24, 32) | 120 |
|       | PWC(24→24), BN, ReLU | (B, 24, 32) | 624 |
|       | MaxPool1d(k=2) | (B, 24, 16) | — |
| SE | GAP → FC(24→6), ReLU | (B, 6) | 150 |
|    | FC(6→24), Sigmoid; channel scale | (B, 24, 16) | 168 |
| Shuffle | Channel shuffle (g=4) | (B, 24, 16) | — |
| GAP | GlobalAvgPool1d | (B, 24) | — |
| FC-1 | Linear(24→64), ReLU | (B, 64) | 1,600 |
| FC-2 | Linear(64→11) | (B, 11) | 715 |
| **Total** | | | **4,961** |

## Design Rationale (paper Sections V–VII)

- **3 DSC stages at W=24** — Finding F4: three stages is the accuracy knee;
  W=24 meets the ≈50 KB Flash target with capacity for SE attention.
- **SE channel attention (r=4)** after DSC Block 3 — 6-unit bottleneck,
  318 parameters, following Hu et al.
- **Channel shuffle (g=4)** — restores cross-channel mixing suppressed by
  the groupwise depthwise structure at near-zero compute.
- **No Dropout** — Finding F2: at 4,961 parameters the model is
  capacity-constrained; regularization impedes training.
- **MaxPool before SE is load-bearing** — spatial compression
  (L: 128→16) is a prerequisite for SE's quantization benefit
  (paper Section VIII-B).

## Deployment Profile (paper Table II)

| Property | Value |
|---|---|
| PTQ | onnxruntime `quantize_static`, QDQ, signed INT8, 1,024 calib samples |
| Released ONNX | opset 13, IR 8 (X-CUBE-AI 10.2 requires IR ≤ 8) |
| Toolchain | ST Edge AI Core 2.2.0 / X-CUBE-AI 10.2.0 |
| Flash (INT8, incl. ST runtime) | 51.26 KB |
| RAM | 12.09 KB |
| Latency (INT8, 544 MHz, ICache + DCache) | 1.183 ms (WCET 1.183 ms, jitter 0.086%) |
| Accuracy @+10 dB | 86.92% INT8 / 87.01% FP32 (PTQ degradation 0.09 pp) |
| Energy | 0.091 mJ/inference (955.1 acc/mJ); EDP 0.107 mJ·ms |
