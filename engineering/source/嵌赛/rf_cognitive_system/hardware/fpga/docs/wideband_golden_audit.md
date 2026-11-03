# Advanced Wideband Path Golden Audit

## Implementation matrix

| Stage | Current implementation | Verification status | Remaining before RTL |
|---|---|---|---|
| Record overlap/window | Complete float reference; symmetric Hann and configurable hop | Multi-window detection tests | Streaming overlap RAM, window coefficient/scale contract |
| FFT | NumPy FFT with shifted signed-frequency order | Frequency-offset tests | Fixed-point scaling, overflow, FFT IP/architecture decision |
| Spectrum power | `abs(FFT)^2 / sum(window^2)`, then mean across windows | Finite output and detection tests | It is relative power/bin, not calibrated W/Hz; freeze accumulator width |
| Noise floor | Lower 75% selection, median divided by `ln(2)` | Multi-SNR tests | Non-stationary/colored noise and local CFAR evaluation |
| Detection | Global floor multiplied by configured dB threshold | -15/-8/0/+10 dB tone cases | False-alarm/detection curves and threshold policy |
| Bin merging | Merge gaps no larger than configured bins; reject short regions | Single, dual and finite-bandwidth cases | FFT boundary wrapping and unequal adjacent-signal cases |
| Descriptor | Center, threshold-span bandwidth, excess power and SNR estimate | Center/bandwidth assertions | Calibrated units, confidence/flags and fixed-point serialization |
| DDC | Complex exponential mixer | Three positive/negative offsets recentered | NCO phase/amplitude widths and spur budget |
| FIR | Runtime SciPy low-pass, default 129 taps | Extraction/finite/shape tests | Tap count, passband/stopband, coefficient quantization |
| Resampling | `resample_poly` with reduced integer up/down ratio | 1:8 path to 128 ksample/s | Supported rate set, multistage architecture and alias tests |
| AMR frame | Pad/truncate to complex64 `[1024]` | Shape/dtype/finite tests | Frame-valid/error policy and int16 scale handoff |
| PFB | Design option only | Not tested | Only evaluate if FFT replay results show inadequate isolation |
| Local CFAR | Not implemented | Not tested | Compare CA/OS-CFAR-like methods on colored/interference replay |
| Symbol-rate adaptation | Not implemented | Explicitly marked | `TODO-SYMBOL-RATE` |

## Why FFT first

FFT provides the shortest verifiable route from bins to signed frequency,
requires no prototype-filter coefficient bank, and allows window, PSD,
detection and descriptor stages to be tested independently. PFB improves
scalloping and adjacent-channel rejection, but adds polyphase FIR multipliers,
coefficient RAM, latency and a larger fixed-point verification surface. PFB is
therefore not part of the first RTL baseline.

## Current detector meaning

For complex white Gaussian noise, individual FFT-bin power is approximately
exponentially distributed. The estimator discards the upper quartile and uses
`median/ln(2)` as a robust scalar approximation of mean noise power. The
threshold is `noise_floor * 10**(threshold_db/10)`. This is a global robust
detector, not local CFAR. It is adequate for controlled white-noise Golden
tests but should not be called CFAR until per-cell training/guard logic and a
false-alarm policy exist.

Detected bins separated by at most `merge_gap_bins` inactive bins are joined.
Regions shorter than `min_region_bins` are rejected. Center frequency is the
excess-power centroid; occupied bandwidth is the full merged threshold span.

## CPU/FPGA partition for the next stages

Future FPGA RTL candidates are deterministic sample-rate operations: overlap
RAM/window multiply, FFT, magnitude square, averaging, selected noise estimator,
threshold/merge primitives, NCO/DDC, FIR and supported decimation stages.

CPU retains candidate identity/lifetime, overlap/conflict policy, threshold
profiles, DDC/filter/rate configuration, NPU queue ownership, logging and UI.
CPU may provide a software fallback for unsupported rational rate changes. NPU
continues to receive only the frozen TimePowerPhase tensor and is unchanged.

## Known validation gaps

- Colored and frequency-varying noise floors.
- False-alarm probability and probability-of-detection curves.
- Adjacent unequal-power modulated signals and near-far behavior.
- Signals crossing the shifted FFT boundary.
- Bursty/intermittent occupancy and descriptor temporal tracking.
- Absolute receiver power/SNR calibration.
- Fixed-point FFT/PSD/noise/DDC/FIR/resampler error budgets.
- Real SDR replay and arbitrary symbol-rate adaptation.

## Executed deterministic validation

- One tone was detected at each input SNR of -15, -8, 0 and +10 dB. The
  detector-reported SNR increased monotonically but is deliberately not
  treated as absolute calibration.
- Center-frequency cases at -310, -120, +75 and +300 kHz had less than 1 Hz
  error in these coherent-tone records.
- Two separated tones were returned as two distinct candidates.
- Injected 24/48/96 kHz band-limited records produced threshold-span estimates
  of 28.5/47.5/86.5 kHz and preserved bandwidth ordering.
- DDC cases at -240, +90 and +260 kHz had measured residual offsets below 1 Hz
  after 1:8 resampling to 128 ksample/s.
- Full project pytest excluding the sealed-blind-specific test module completed
  with 105 passed tests. The two blind-specific tests were not collected.

No wideband RTL, PFB, local CFAR, QAT, model training or blind-test evaluation
is part of this stage.
