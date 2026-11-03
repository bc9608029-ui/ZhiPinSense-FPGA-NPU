# Ordered FPGA Development Gates

1. **Stage 1 — Power/Lag unit RTL:** exact widths, first-lag reset, pipeline and
   edge/random vector verification.
2. **Stage 2 — Frame controller:** 1024 samples, ID/index/boundaries, sticky error,
   backpressure tests.
3. **Stage 3 — Quantizer:** configurable multiply/shift, ties-away rounding,
   saturation and counters.
4. **Stage 4 — Tensor packer:** fixed NCL channel order, logical addresses,
   ping-pong ownership and completion.
5. **Stage 5 — Core integration:** deterministic full-chain HDL comparison,
   randomized stalls, reset/drop/error injection.
6. **Stage 6 — FFT/PSD golden reference:** replay-driven parameter and fixed-point
   contract freeze; then incremental RTL.
7. **Stage 7 — Signal detector:** noise floor, threshold/CFAR-like decision,
   merging and descriptor RTL after false-alarm/detection tests.
8. **Stage 8 — DDC/FIR/decimation:** freeze NCO/FIR/rate widths from real-rate
   requirements; address `TODO-SYMBOL-RATE`.
9. **Stage 9 — Procise synthesis:** add a thin confirmed-IP wrapper, constraints,
   timing/resource reports; do not change core arithmetic silently.
10. **Stage 10 — FMQL30TAI board:** clock/reset/JTAG and loopback/replay bring-up,
    followed by bit-exact comparison against captured outputs.
11. **Stage 11 — DDR/NPU:** cache/DMA ownership, tensor layout, runtime INT8 scale,
    completion/interrupt and end-to-end replay.
12. **Stage 12 — SDR:** PS USB/GigE transport first, packet-loss accounting,
    rate continuity, then live spectrum/candidate/AMR demonstration.

No later stage may bypass the bit-exact gate of the preceding stage.
