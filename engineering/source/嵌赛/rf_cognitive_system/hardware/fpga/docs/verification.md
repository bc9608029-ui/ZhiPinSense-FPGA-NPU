# Verification Plan and Current Evidence

## Traceable flow

```text
deterministic Python case generator
 -> signed-int16 `iq_input.hex`
 -> SystemVerilog testbench
 -> RTL CSV
 -> column-by-column Python comparison with `expected_core.csv`
```

The vector set has 19 frames (19,456 complex samples): all zero, isolated
full-scale impulse, alternating signs, all maximum positive, all maximum
negative, near-full-scale random, ordinary random, and BPSK/QPSK/16QAM/64QAM
at +20/0/-10 dB. It uses seed 20261001 and does not load or evaluate the sealed
blind test.

Checks cover exact Power/Lag, zero first lag, frame ID/index/start/end, signed
rounding, saturation and counts, channel-major addresses, ping-pong ownership,
and INT8 values. Unit benches additionally exercise the frame controller,
quantizer and tensor packer.

Generate/reference-check with:

```powershell
python hardware/fpga/vectors/generate_vectors.py
python hardware/fpga/tb/run_rtl_compare.py
```

If `iverilog`/`vvp` is unavailable, the second command emits a machine-readable
`SKIPPED` status and does not claim an RTL result. The generated expected CSV
and Python tests still validate the specification, but they do not replace HDL
simulation.

The six existing benches were subsequently compiled and run using WSL
Verilator 5.032 with `--binary --timing` and the default warning-fatal policy.
All six passed. `tb_qam_feature_vectors` and `tb_mandatory_core` then produced
CSV files that matched 97,280 and 233,472 Python elements respectively, with
zero mismatch. Build products are under `tb/results/verilator_closure/` and are
intentionally ignored by Git.

## Gates before synthesis

1. Six current benches and exact Golden comparison: complete.
2. Add randomized ready/valid stalls and assertions for stable payload.
3. Add reset-at-boundary and deliberate upstream-drop/error tests.
4. Run dedicated lint and clock/reset-domain checks.
5. Only then create a Procise wrapper and inspect inferred widths/resources.

## Wideband test plan

The current float reference is tested with separated tones and DDC extraction.
Before wideband RTL, add recorded/replayed cases for adjacent signals, unequal
powers, varying occupancy, noise uncertainty, interferers, band-edge wrapping,
and candidate overlap. Freeze window normalization, PSD width/scaling, noise
estimator, threshold false-alarm policy and descriptor units before fixed-point
RTL. The pre-board format/width plan is now recorded in
`wideband_fixed_point_contract.md`; its FFT/PSD assumptions still require
synthesis and replay evidence. Symbol-rate mismatch is explicitly
`TODO-SYMBOL-RATE`.
