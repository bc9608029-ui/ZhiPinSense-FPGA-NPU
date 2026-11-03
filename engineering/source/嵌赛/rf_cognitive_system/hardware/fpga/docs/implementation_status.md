# Implementation Status — Pre-Board Closure, 2026-09-09

## Completed and verified

- Portable ready/valid IQ FIFO with explicit dropped-sample counter.
- 1024-point frame controller with index, ID, boundaries and sticky error.
- Two-stage, II=1 exact Power/Lag-1 pipeline.
- Configurable multiplier/shift INT8 quantizer with ties-away rounding.
- Logical NCL tensor packer with ping-pong ownership and completion IRQ.
- Abstract ingress, tensor-write and buffer-transfer interfaces.
- Deterministic 19-frame/19,456-sample Python/RTL vector corpus.
- Six SystemVerilog testbenches run under WSL Verilator 5.032: all PASS.
- Python comparison: 97,280 exact feature elements and 233,472 mandatory-core
  elements checked with zero mismatch.
- Verilator source width/PINMISSING warnings closed without mathematical or
  interface-semantic changes.
- FFT-based float wideband discovery/extraction Golden Reference.
- Pre-board wideband fixed-point interface and Python Q1.15 NCO/DDC reference.

## Frozen evidence

- Baseline V1 SHA-256 lock: 17/17 verified.
- QAM-Aware V2 source/config SHA-256 lock: 18/18 verified.
- Vector seed/cases/samples: 20261001 / 19 / 19,456.
- `iq_input.hex` SHA-256:
  `5B720B7725A712D0CAC0AB33FB13FF2D18A4B372ED948AC20D3B0E6B824852E7`.
- `expected_core.csv` SHA-256:
  `8EE0B763597492EFBCE3A8ADE9A30E925958818982F566CFEEA06931438F0A82`.
- `manifest.json` SHA-256:
  `B8568F715D5A82AD2BA3056C1DCD1FB68A393D916ADF2892803B0313CE10FA16`.

The sealed-blind-specific pytest module remains excluded. No sealed sample or
model prediction has been accessed.

## Tool note

Verilator compilation now completes with its default warning-fatal policy and
no Verilator RTL/TB warning. GNU Make still reports sub-two-second clock skew
because generated files reside on a Windows-mounted mobile drive; all targets
were freshly built and executed. This is a filesystem timestamp issue, not a
source lint warning or a measured hardware timing result.

## Not implemented or claimed

- No Advanced Wideband RTL, PFB, local CFAR, final FIR, arbitrary resampler or
  symbol-rate estimator.
- No Procise synthesis, place-and-route, STA, resource or power result.
- No board clock/reset, pin, BSP, Device Tree, DMA/DDR or interrupt adapter.
- No NPU or live SDR execution and no QAT/model retraining.
- NCO phase-to-amplitude LUT/CORDIC error is not modeled; current reference
  quantizes ideal accumulator phase directly to Q1.15 sine/cosine.

## Board-arrival gates

Confirm Procise device/IP support, create a thin adapter, verify clock/reset and
CDC, synthesize exact widths, repeat captured-output bit comparison, then close
DDR coherency, interrupts, NPU tensor calibration and PS SDR transport.
