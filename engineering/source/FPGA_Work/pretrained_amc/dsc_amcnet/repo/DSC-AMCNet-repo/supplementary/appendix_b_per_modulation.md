# Appendix B: Per-Modulation and Multi-Tier Accuracy Findings

All values below are the paper's verified measurements on the locked test
split (`split_indices.npz`, SEED = 42). To regenerate the full per-class
confusion matrix, evaluate the released checkpoint per class:

```bash
python models/train.py --data datasets/RML2016.10a_dict.dat \
    --split datasets/split_indices.npz --epochs 0   # or load checkpoint
# then run per-class evaluation on the +10 dB test bin
```

## Confusion Structure at +10 dB (INT8)

- Near-perfect (≥99%) for AM-DSB, CPFSK, BPSK, PAM4.
- QAM16/QAM64 confusion persists: QAM16→QAM64 ≈ 30%,
  QAM64→QAM16 ≈ 44% — a known dataset-level limitation of RML2016.10a.

## Four-Tier OTA Validation (paper Table X(a); hi-SNR = mean over +6..+18 dB)

| Tier | Context | Hi-SNR Acc. | Δ (pp) |
|---|---|---|---|
| 1 | Laptop FP32 (synthetic) | 85.80% | baseline |
| 2 | STM32 HIL (synthetic, MCU INT8) | 85.78% | −0.02 |
| 3 | STM32 loopback (real RF, INT8) | 82.76% | −3.02 |
| 4 | Real broadcast, WBFM (live, Kerala) | 0–2.4% | — |

- Tier 1→2 (−0.02 pp): quantization cost is negligible in practice.
- Tier 2→3 (−3.02 pp): consistent with oscillator phase noise, ≈20 ppm
  frequency offset (HackRF TX–RX mismatch), and non-ideal antenna
  matching (individual contributions not isolated by direct measurement).
  AM-SSB degrades most (−14.0 pp, frequency-offset sensitive);
  QAM16/QAM64 improve (+18.8/+7.0 pp) as phase noise de-correlates their
  synthetic-test-set confusion.
- Tier 4: near-zero WBFM accuracy reflects a RadioML dataset synthesis
  limitation, not a model failure; Tier 3 remains the valid hardware
  characterization.
- Latency under real RF: 3.901 ms mean (FP32; WCET 3.950 ms, jitter 1.3%)
  across 22,000 live inference calls.

## Simulated Fading Robustness (paper Table X(b); FP32, no retraining)

| Channel model | Hi-SNR Acc. | Δ (pp) |
|---|---|---|
| Clean AWGN (baseline) | 85.68% | — |
| Flat Rayleigh (1-tap) | 76.91% | −8.77 |
| 2-tap multipath (exp. PDP) | 69.49% | −16.19 |
| 4-tap multipath (exp. PDP) | 60.82% | −24.85 |

Graceful, retraining-free degradation; per-window L2 normalization applied
after channel distortion. (The 85.68% clean baseline and the 85.80%
Tier-1 baseline are independent runs over the same split, within the
±0.23 pp seed variance.)

## Cross-Dataset Generalization (paper Table IX)

| Model | Flash (KB) | RAM (KB) | Lat. (ms) | FP32 | INT8 | PTQ Deg. |
|---|---|---|---|---|---|---|
| DSC-AMCNet-11 | 51.26 | 12.09 | 1.183 | 87.01% | 86.92% | +0.09 pp |
| DSC-AMCNet-24 | 48.28 | 31.70 | 9.743 | 63.34% | 63.33% | +0.01 pp |
