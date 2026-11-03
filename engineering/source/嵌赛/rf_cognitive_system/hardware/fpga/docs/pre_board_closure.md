# Pre-Board Closure Baseline

## Closed

- Mandatory Core arithmetic and interface semantics.
- Verilator width and missing-pin warnings.
- Six unit/integration simulations under Verilator 5.032.
- Exact Python Golden comparison with zero mismatch.
- int16/Q1.15/FFT/PSD/descriptor pre-board width contract.
- Python-only 32-bit phase, Q1.15-amplitude NCO/DDC evaluation.
- Float FFT wideband detector/extractor Golden Architecture.

## Deliberately open

- Advanced Wideband RTL of any kind.
- PFB and local CFAR selection.
- Final FIR taps/coefficient widths.
- General rational resampling hardware.
- `TODO-SYMBOL-RATE` estimation/adaptation.
- Procise FFT/DMA/DDR interfaces and FMQL30TAI synthesis.
- Board clocks, resets, pins, Device Tree and drivers.
- NPU runtime INT8 calibration and SDR replay/live capture.

No AI architecture, checkpoint, dataset, evaluation result or sealed test was
changed or accessed during closure.
