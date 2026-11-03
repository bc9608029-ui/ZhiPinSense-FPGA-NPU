# Wideband Golden Interface Contract

This contract describes the board-independent software reference. It does not
select an SDR, DMA IP, DDR address map, NPU runtime, or final fixed-point width.

## Analysis input

| Field | Software Golden contract | Future streaming boundary |
|---|---|---|
| IQ | Finite one-dimensional `complex64` or `complex128` array | Signed I/Q stream; initial transport is expected to be int16 I + int16 Q from PS DDR |
| Sample rate | Positive `sample_rate_hz`, carried explicitly | Runtime configuration register/descriptor; never inferred from samples |
| Record length | At least one FFT length; remaining incomplete tail is not analyzed | Framer supplies complete FFT windows and overlap state |
| FFT length | `DiscoveryConfig.fft_length`, default 1024 | Configurable/frozen after replay evaluation |
| Hop length | `DiscoveryConfig.hop_length`, default 512 | Default 50% overlap; must be no greater than FFT length |
| Frequency convention | Complex baseband, signed frequencies in `[-Fs/2, Fs/2)` | Same convention at all CPU/PL boundaries |

The software path performs no hidden per-record normalization. A future int16
advanced-path output must carry a frozen scale into the already defined
Mandatory Core numerical contract rather than independently renormalizing each
candidate.

## Candidate descriptor output

Each candidate is represented by:

```text
candidate_id             CPU queue identity
first_bin, last_bin      inclusive indices in fftshift order
center_frequency_hz      power-weighted excess-power centroid
occupied_bandwidth_hz    thresholded merged-bin span
integrated_power         sum of power above estimated floor, relative units
estimated_snr_db         integrated excess / estimated in-region noise
```

The analysis result also carries sample rate, record length, FFT/hop/threshold
configuration, bin width, spectrum values, scalar noise floor and threshold.
`integrated_power` is not calibrated watts and the current SNR estimate is not
an absolute receiver SNR measurement.

Before RTL, descriptor fields still need fixed widths, units, rounding,
valid/error flags and a version field. Candidate lifetime, priority and buffer
ownership remain CPU policy.

## Extraction request

CPU supplies:

```text
candidate_id
center_frequency_hz
occupied_bandwidth_hz
target_sample_rate_hz = 128000
target_length = 1024
```

The Golden path applies `exp(-j*2*pi*fc*n/Fs)`, designs a low-pass FIR, removes
its integer input-sample group delay, and uses rational polyphase resampling.
Metadata reports filter cutoff/taps/delay and reduced up/down factors.

## AMR output

The software output is finite `complex64[1024]` at 128 ksample/s. It feeds the
Mandatory Core as IQ `[2,1024]`, followed by Power/Lag and TimePowerPhase. The
training relation is:

```text
128 ksample/s / 16 ksymbol/s = 8 samples/symbol
```

This relation is valid only after correct channel extraction and symbol-rate
matching. Arbitrary real signal rates are not solved: `TODO-SYMBOL-RATE`.
