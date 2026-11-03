# Hardware integration boundary

No file in this directory claims current hardware operation.

- `TODO-HARDWARE`: define the physical SDR/ADC input and clocking scheme.
- `TODO-HARDWARE`: implement and simulate Procise RTL for DC removal, FIR, FFT,
  power spectrum, framing, and energy detection.
- `TODO-HARDWARE`: define AXI4-Stream/AXI memory-map registers and DMA buffers.
- `TODO-HARDWARE`: compare RTL and board captures against
  `dsp/golden_reference.py` point by point.
- `TODO-HARDWARE`: use Icraft to compile/quantize the selected network and run
  supported-operator, accuracy, and NPU latency tests.
- `TODO-HARDWARE`: measure FPGA timing/resource use, system latency/throughput,
  power, thermal behavior, and long-duration stability on FMQL30TAI.
- `TODO-HARDWARE`: capture real SDR data and quantify Sim-to-Real degradation.

