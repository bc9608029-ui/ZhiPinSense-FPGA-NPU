# Advanced Wideband Cognition Golden Architecture

## Processing chain

```text
wideband IQ
 -> overlap/frame + window
 -> FFT (V1) or PFB channelizer (later option)
 -> power spectrum / averaging
 -> robust noise-floor estimate
 -> global robust threshold (V1) / local CFAR-like detector (future candidate)
 -> contiguous-bin merging
 -> {count, center frequency, occupied bandwidth, power, estimated SNR}
 -> CPU candidate policy / extraction request
 -> NCO complex mixing (DDC)
 -> low-pass FIR
 -> decimation or rational resampling
 -> 128 ksample/s complex baseband
 -> 1024-sample mandatory core
 -> TimePowerPhase queue
```

The executable float golden reference is `dsp/wideband_discovery.py`; the
candidate/extraction interface is `hardware/fpga/python/wideband_reference.py`.
It already covers Hann overlap FFT, PSD averaging, robust scalar noise floor,
threshold detection, bin merging, descriptor estimation, DDC, FIR and rational
resampling. It is not bit-exact wideband RTL yet.

The formal software/stream interface is defined in `wideband_interface.md`.
The implementation and validation matrix is maintained in
`wideband_golden_audit.md`.

## FFT versus PFB

| Choice | Benefits | Costs/risks | First-stage decision |
|---|---|---|---|
| Windowed FFT | Simpler control/reference, less coefficient memory, direct bin/frequency mapping, easiest incremental verification | Scalloping and leakage; weaker adjacent-channel isolation | Recommended V1 |
| PFB channelizer | Better stopband isolation and reduced leakage/scalloping for dense spectra | FIR polyphase multipliers, coefficient RAM, more latency and verification complexity | Evaluate only after FFT detector replay tests |

The first RTL implementation should therefore be overlap/window plus FFT/PSD.
PFB is an evidence-driven replacement, not an assumed requirement.

## Planned fixed-point decisions—not yet frozen

- NCO starting study point: 32-bit phase accumulator with 16-bit Q1.15 sine and
  cosine from LUT or CORDIC. Spur/error requirements must select final widths.
- FIR tap count must be derived from input rate, candidate occupied bandwidth,
  transition width, stopband attenuation, and decimation factor. The Python
  default of 129 taps is not a hardware contract.
- Rate change is configurable. Prefer cascaded integer decimation (and halfband
  stages where applicable); use rational resampling only when input/target rates
  demand it.
- The output contract is 128 ksample/s and 1024 complex samples. It matches the
  training distribution's 16 ksymbol/s at 8 samples/symbol only when the real
  candidate has been correctly rate-matched.

`TODO-SYMBOL-RATE`: estimation and arbitrary-symbol-rate normalization are not
solved. Until they are, CPU configuration or known waveform profiles must set
the DDC/filter/rate-change parameters, and claims must be limited accordingly.

## Operating modes

Single-signal mode may bypass discovery when center frequency and occupied
bandwidth are known; DDC/FIR/rate change directly produces AMR frames. In
multi-signal mode, the detector emits multiple descriptors, the CPU owns the
candidate queue and buffer lifetime, and PL time-multiplexes or replicates an
extraction pipeline according to measured resource/rate constraints.

PL is suited to deterministic sample-rate operations: window/FFT/PSD, detection,
NCO, FIR and rate change. CPU is suited to policies: candidate aging, overlap
resolution, priority, DDC parameter programming, NPU scheduling and UI. NPU
receives only extracted fixed-shape tensors.
