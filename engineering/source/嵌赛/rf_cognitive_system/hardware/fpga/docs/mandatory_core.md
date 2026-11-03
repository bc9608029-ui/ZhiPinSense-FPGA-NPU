# Mandatory Core Path

## Numerical contract

Input is one accepted signed-int16 complex sample per ready/valid transfer.
The exact feature equations are:

```text
Power = I*I + Q*Q                         unsigned 32-bit
LagRe = I[n]*I[n-1] + Q[n]*Q[n-1]        signed 33-bit
LagIm = Q[n]*I[n-1] - I[n]*Q[n-1]        signed 33-bit
```

At `sample_index=0`, both lag outputs are exactly zero. Previous IQ state is
also cleared after each accepted `frame_end`; frame start therefore cannot
inherit data from another frame.

The configurable quantizer implements:

```text
q = saturate[-127,127](round_ties_away(raw * multiplier / 2**shift))
```

The frozen reference-test values are IQ `(127,15)` and physical `(127,31)`.
They are algebraically identical to Q1.15 ADC conversion followed by frozen
reference scales `1/127` for IQ and `2/127` for Power/Lag. They are not final
radio/NPU calibration values. A new calibrated multiplier/shift may be loaded,
but the formula, rounding and saturation rules must not silently change.

## Modules and interfaces

| Module | Input | Output | No-stall latency | II |
|---|---|---|---:|---:|
| `iq_stream_fifo` | int16 I/Q, error, valid; explicit drop event | int16 I/Q, error, valid; occupancy/drop count | 1 clock from push into empty FIFO | 1 |
| `iq_frame_controller` | IQ ready/valid | IQ + index/start/end/id/error | 0 clocks | 1 |
| `qam_feature_pipeline` | framed IQ + sidebands | IQ, u32 Power, s33 LagRe/LagIm + sidebands | 2 clocks | 1 |
| five `feature_quantizer` instances | raw integer + multiplier/shift | signed INT8 + saturation flag/count | 1 clock | 1 |
| `tensor_packer` | five synchronized INT8 channels | five logical buffer writes + valid/done/IRQ | 0 clocks | 1 |

With an initially empty FIFO and no stalls, a source beat accepted at the input
is presented as a tensor write after four rising edges: FIFO storage (1), two
feature stages (2), and quantizer register (1). From an already-valid FIFO
output, the path is three registered clocks. This is a theoretical RTL latency,
not a placed-and-routed timing result.

## Tensor contract

Both tensors use contiguous NCL byte planes for batch size one:

```text
IQ [2,1024]:       I offsets 0..1023, Q offsets 1024..2047
Physical [3,1024]: Power 0..1023, LagRe 1024..2047, LagIm 2048..3071
```

The packer emits five writes in parallel. A future adapter may preserve banked
writes or serialize/coalesce them into DDR bursts, but it must preserve these
logical offsets and the channel order `Power, LagRe, LagIm`.

## Theoretical resources

The fully parallel exact feature pipeline performs six signed 16x16 products
per accepted sample and three wide add/sub operations. It is designed for one
complex sample per clock. Five generic configurable quantizers add five integer
multipliers; their eventual LUT/DSP mapping depends on synthesis, multiplier
values and the target DSP primitive. Fixed reference multiplier 127 could be
strength-reduced to `(x<<7)-x`, but the present generic interface deliberately
does not assume calibration remains 127.

Minimum logical buffering in this reference is:

- Input FIFO: `16 * (16+16+1) = 528` payload bits, plus pointers/counters.
- Two complete packed tensor slots: `2 * (2+3) * 1024 * 8 = 81,920` bits
  (10,240 bytes), if materialized as ping-pong BRAM.
- Feature pipeline/metadata: registers only; no full exact-feature frame store.

No FMQL30TAI DSP-slice or BRAM-block count is claimed. A 33x32 configurable
quantizer multiply may consume multiple physical DSP primitives; only Procise
synthesis can determine the mapping. If the fabric clock-to-sample-rate ratio
allows, products can later be scheduled over fewer multipliers, but such a
variant needs its own bit-exact and throughput verification.

## Error semantics

Backpressure is normal and is not overflow. `s_overflow_event` must only pulse
when an upstream adapter actually drops a sample. `s_error` is sticky within a
frame. Each quantizer separately counts saturation. `frame_id`, buffer ID,
sample index, frame boundary, error and valid remain aligned under downstream
backpressure.
