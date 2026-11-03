# Wideband Fixed-Point Interface Contract

The machine-readable companion is `configs/wideband_fixed_point.yaml`. This is
a pre-board arithmetic contract, not a Procise FFT-IP interface assumption.

## Input and window

Wideband input is interleaved signed int16 `{I,Q}` with an explicit receiver
scale and sample rate. Per-record normalization is forbidden. The symmetric
Hann coefficients are signed Q1.15 int16 (`0..32767`). Each s16×s16 window
product is s32, rounded nearest with exact halves away from zero after a
15-bit shift, then saturated to s16 for the abstract FFT input.

## Abstract FFT boundary

For the 1024-point V1 reference, an unscaled coherent sum needs ten growth
bits. The portable contract is therefore:

```text
input:  frame_id, sample_index, s16 real, s16 imag, valid/start/end/error
output: frame_id, bin_index, s26 real, s26 imag,
        exponent, valid/start/end/overflow
```

Input is natural time order. An adapter must declare native FFT output order
and convert it to the project's fftshift bin convention. A scaled or
block-floating implementation is allowed only when its exponent accompanies
every frame and reconstructs the same values in Python. No ready/latency/burst
behavior of a Procise IP is assumed.

## Power and PSD widths

With s26 FFT real/imaginary outputs:

```text
magnitude_square = Re^2 + Im^2       unsigned 51 bits
M-frame accumulator width = 51 + ceil(log2(M))
M=32 reference accumulator           unsigned 56 bits
```

For 32-frame averaging, division may be a five-bit right shift. The current
Python window-energy correction remains a CPU/reference operation until its
fixed-point rounding and calibration policy are frozen.

## Raw FPGA candidate descriptor

The initial hardware-facing descriptor contains raw/non-logarithmic data:

- version u8, flags u16, analysis frame ID u32, sample timestamp u64;
- candidate ID u16;
- first/last/peak bin and bin count as u16 fields;
- FFT exponent s8 and PSD right-shift u8;
- noise floor, integrated excess power and peak power as u64;
- optional weighted-bin-power sum as u72 transported in three 32-bit words.

Flags include valid, arithmetic overflow, FFT-edge wrapping, descriptor
saturation and frame error. Fixed transport packing/endian order remains a
future board-adapter decision.

FPGA outputs bin indices, mantissas, exponents and sums. CPU performs:

```text
frequency_hz = (signed_shifted_bin / FFT_length) * sample_rate
bandwidth_hz = bin_count * sample_rate / FFT_length
center_hz    = weighted_bin_sum / integrated_power -> bin -> Hz
snr_db       = 10*log10(integrated_excess / (noise_floor*bin_count))
```

CPU also applies receiver/window/FFT calibration to obtain physical power.
This keeps division, logarithm and floating-point Hz/dB conversions out of the
first FPGA detector.

## NCO/DDC reference

The evaluated NCO uses a 32-bit wrapping phase accumulator and signed Q1.15
int16 sine/cosine. Negative-frequency mixing uses four s16×s16 products and
two s33 add/sub results, followed by ties-away shift 15 and int16 saturation.

At 1.024 MS/s with a 0.7-full-scale coherent input:

| Requested frequency | Signed tuning word | Word error | RMSE | EVM | Residual frequency |
|---:|---:|---:|---:|---:|---:|
| -240 kHz | -1006632960 | 0 Hz | 1.377e-5 | -94.12 dB | 0 Hz |
| +90 kHz | 377487360 | 0 Hz | 1.522e-5 | -93.25 dB | approximately 0 Hz |
| +260 kHz | 1090519040 | 0 Hz | 1.402e-5 | -93.97 dB | approximately 0 Hz |

All three had zero saturation. These frequencies happen to be exactly
representable at this sample rate. Results include phase-word and Q1.15
amplitude quantization but exclude finite LUT address depth, interpolation,
CORDIC iteration and future FIR effects. Full-scale arbitrary complex IQ can
grow beyond int16 during rotation; receiver headroom or a configurable
post-mixer shift remains mandatory.
