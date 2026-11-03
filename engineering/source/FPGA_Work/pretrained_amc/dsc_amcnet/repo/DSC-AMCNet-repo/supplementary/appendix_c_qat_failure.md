# Appendix C: QAT Failure Analysis (Negative Result)

Reported in the paper as Section VIII-A. Suppressing negative results
weakens reproducibility and misleads future researchers who may attempt
QAT on SE-attention AMC architectures.

## Setup

| Parameter | Value |
|---|---|
| PTQ | onnxruntime `quantize_static`, QDQ, signed INT8, 1,024 calib samples |
| QAT | self-contained FakeQuantize module, symmetric per-tensor INT8 |
| Split | locked 80/20 (SEED = 42) |

## Results (paper values)

**DSC-AMCNet (SE attention present):**

| Method | Overall (all-SNR) accuracy |
|---|---|
| FP32 baseline | ≈57% |
| PTQ | +0.03 pp vs FP32 overall; +0.09 pp at +10 dB — near-zero |
| QAT | converges to only 48.2% — WORSE than both |

**LiteAMCNet (no SE) — QAT behaves as expected:**

| Method | Overall accuracy |
|---|---|
| FP32 | 55.20% |
| PTQ | 54.20% (+1.00 pp degradation; peak +2.55 pp at +14 dB) |
| QAT-INT8 | 56.60% (+1.40 pp ABOVE FP32; recovers PTQ losses at 18 of 20 SNR bins; peak recovery +4.75 pp at −6 dB) |

## Hypothesis (stated as such in the paper)

SE Sigmoid activations may be destabilized by fake-quantization
perturbations inserted during QAT (Jacob et al., 2017). The failure is
specific to the SE path: the SE-free LiteAMCNet fine-tunes normally under
identical QAT machinery. This is an empirical hypothesis supported by the
contrast between the two architectures; it is not analytically proven.

Note the direction of the per-SNR effect (paper Section VIII-A):
PTQ degradation concentrates at HIGH SNR for LiteAMCNet
(+1.63 pp at ≥ +6 dB vs +0.16 pp at ≤ −10 dB), while DSC-AMCNet's PTQ
degradation is near-zero across ALL bins — the co-design of MaxPool
compression and SE attention removes the high-SNR concentration.

## Recommendation

Use PTQ (QDQ, signed INT8, 1,024 calibration samples) when SE attention
and MaxPool compression co-occur; do not apply QAT to the SE path.

## Reproducibility

```bash
python quantization/qat_experiment.py \
    --checkpoint models/checkpoints/dscamcnet_best.pt \
    --data       datasets/RML2016.10a_dict.dat \
    --split      datasets/split_indices.npz \
    --epochs     10
```
