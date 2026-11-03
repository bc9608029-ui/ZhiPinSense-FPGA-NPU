# FPGA DSP Golden Interface (provisional)

This document defines the PC-side software contract for future Procise RTL and
FMQL30TAI validation. Every item below is provisional until captured hardware
data exists.

## Stream contract

- Input: complex IQ, interleaved signed `int16`, ordered `I0,Q0,I1,Q1,...`.
- Record length: configurable; baseline is 1024 complex samples.
- Framing: record-level `valid/start/end`; no hidden padding in the reference.
- DC removal: subtract the record mean. A streaming RTL implementation may use
  a configurable IIR estimator, but it must be compared against this block mode.
- Normalization: CPU/configured block gain is preferred for the first RTL
  version. The gain and exponent must be carried as metadata.
- FIR: default 65-tap low-pass; coefficients use signed Q1.15.
- FFT: configurable, default 1024 points with a Hann window (Q1.15).
- FFT ordering: natural input, bit-reversal handled internally, natural-order
  complex output unless an explicit adapter says otherwise.
- Power output: `I^2 + Q^2`, accompanied by FFT scaling/exponent metadata.

## Dynamic-range recommendation

This is an engineering starting point, not a frozen RTL specification:

1. A signed 16 x 16 multiply produces a signed 32-bit result (approximately
   Q2.30 for Q1.15 operands).
2. Summing 65 worst-case products needs `ceil(log2(65)) = 7` guard bits. Use a
   40-bit FIR accumulator, then round and saturate deliberately.
3. An unscaled 1024-point FFT can grow by 10 bits. From a 16-bit input this
   requires at least 26 bits. A 24-bit internal path is acceptable only with
   per-stage or block-floating scaling and an exported exponent.
4. Squaring two signed 24-bit FFT components and adding them needs roughly 49
   bits. Use at least 50 bits internally or a 64-bit power accumulator before
   any controlled truncation/log conversion.
5. Validate crest factor using OFDM and worst-case coherent vectors before
   freezing widths. Report saturation counts as part of every comparison.

The Python implementation in `dsp/golden_reference.py` emits MSE, relative
error, and quantization SNR for the float/fixed paths.

`TODO-HARDWARE`: add RTL dump readers, define AXI4-Stream signal timing, and
compare Procise simulation plus physical FMQL30TAI captures point by point.

