# TimePowerPhase final algorithm diagnosis

## Evidence summary

TimePowerPhase is the present candidate because it reached 70.55% Accuracy and
69.75% Macro-F1 on `development_test`, versus 69.87% and 69.02% for the
parameter-matched TimeOnlyWide control. The paired overall McNemar p-value is
0.0481. This is development evidence, not confirmatory evidence; the sealed
`final_blind_test` remains untouched.

The gain is highly structured rather than uniform:

| Metric | TimeOnlyWide | TimePowerPhase | Difference |
|---|---:|---:|---:|
| Overall Accuracy | 69.87% | 70.55% | +0.68 pp |
| 16QAM Accuracy | 42.38% | 50.76% | +8.38 pp |
| 64QAM Accuracy | 43.05% | 42.19% | -0.86 pp |
| QAM high-SNR mean | 62.47% | 66.47% | +4.00 pp |

At +10/+20 dB, 16QAM reached 81.6%/86.4%, while 64QAM was only
60.4%/60.0%. Across development_test, 16QAM-to-64QAM errors fell to 21.24%,
but 64QAM-to-16QAM remained 30.00%. The combined model therefore moved the
decision boundary toward 16QAM rather than solving both directions equally.

## Bottlenecks

1. **Fine radial structure is compressed.** Instantaneous power contains the
   relevant multi-ring information, but a small convolutional branch followed
   by mean and second moment does not explicitly preserve ring occupancy.
   Several 16QAM/64QAM distributions can share similar low-order moments.
2. **Amplitude and channel effects are entangled.** Random amplitude scaling,
   AWGN and pulse-shaping transitions widen the power modes. BatchNorm handles
   global scale statistically but does not guarantee record-wise scale
   invariance.
3. **Lag-1 is not a QAM-order sufficient statistic.** It helps temporal phase
   continuity, yet a single lag cannot reliably distinguish dense QAM rings.
4. **Low-SNR information is genuinely lost.** The candidate is not better than
   TimeOnlyWide throughout -12 to -6 dB. Power squaring also creates noise-noise
   terms, so the physical branch cannot restore absent SNR.
5. **Real-channel robustness is unproven.** Formal V2 used AWGN, CFO, phase
   offset and amplitude scaling; fading, multipath, IQ imbalance, DC offset,
   clipping and interference were disabled. No Sim-to-Real or SDR result may be
   inferred from the present score.

## Recommended lightweight experiments (not started)

### 1. FPGA radial occupancy histogram — first priority

After a block gain/exponent normalization, count power samples into 8 or 16
fixed bins. Feed the normalized counts to a tiny linear/MLP fusion layer while
retaining raw IQ. This exposes the number and occupancy of QAM rings directly,
uses only comparators, counters and shifts in FPGA logic, and adds roughly tens
to a few thousand learned parameters depending on the embedding width.

Engineering target, not a measured promise: recover 2–6 percentage points of
64QAM high-SNR accuracy without losing the current 16QAM gain, corresponding to
roughly 0–1 overall Accuracy point. The risk is threshold sensitivity under AGC,
fading and clipping, so thresholds and the block exponent must be calibrated
using training/validation data only.

### 2. Multi-lag real correlation moments — second priority

Extend the same multiplier/accumulator design to lags 1, 2 and 4 and pool
`E[Re]`, `E[Im]`, `E[Re^2]`, and `E[Im^2]`. No `atan`, complex operator or
square root is needed. The hardware can time-share multipliers because the
reference sample rate is only 128 ksample/s. Expected benefit is smaller
(engineering target 0–2 overall points) but it may improve QPSK/8PSK and the
-8 to -4 dB transition. It should only be attempted after the radial histogram
experiment, with parameter count held near the current 71.7K control.

Neither proposal authorizes training. Both must use the frozen data protocol,
development evaluation and a predeclared acceptance criterion before the blind
set is opened.
