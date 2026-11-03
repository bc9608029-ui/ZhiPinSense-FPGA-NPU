# Board-Independent FPGA Preparation

This directory is the verified hand-off boundary between the frozen radio-ML
software and a future FMQL30TAI board project. Nothing here instantiates a
Procise/vendor IP, fixes a board clock, or assigns a pin.

## Frozen heterogeneous split

```text
SDR -> PS USB/GigE -> PS DDR/replay
                         |
                         v
PL wideband discovery/extraction -> PL Power/Lag/INT8 packing -> DDR
                                                                  |
                                                                  v
                                                     NPU TimePowerPhase
                                                                  |
                                                                  v
                                             CPU scheduling/UI/logging
```

The first hardware version is explicitly memory-fed: SDR transport terminates
in the PS, records enter DDR, and a future board adapter feeds the generic IQ
ready/valid port. Direct-to-PL radio interfaces are a later option, not an
assumption in this RTL.

The formal division is:

> FPGA负责发现与提取无线信号，NPU负责理解无线信号，CPU负责管理无线信号。

## Directory map

- `rtl/common`: portable FIFO and mandatory-core integration.
- `rtl/framing`: 1024-sample frame identity and status.
- `rtl/features`: exact integer Power and Lag-1 pipeline.
- `rtl/quantization`: configurable multiplier/shift INT8 quantizer.
- `rtl/tensor`: logical `[2,1024]` IQ and `[3,1024]` physical packing.
- `rtl/interfaces`: abstract buffer-write transaction definition.
- `rtl/top`: conservative Lite-board wrapper; no vendor IP or pin constraint.
- `rtl/wideband`: intentionally contains no RTL in this stage.
- `python`: bit-exact mandatory reference and wideband orchestration reference.
- `vectors`: deterministic inputs and expected outputs.
- `board_validation`: frozen-vector board capture and zero-tolerance comparator.
- `tb`: unit/integration SystemVerilog testbenches and comparison runner.
- `docs`: numerical, architecture, interface, verification, and roadmap details.

Wideband-specific status and contracts are in
`docs/wideband_golden_audit.md`, `docs/wideband_interface.md`, and
`docs/wideband_fixed_point_contract.md`. The current hand-off checklist is
`docs/pre_board_closure.md`.

Lite-specific facts and the Procise hand-off plan are kept at
`../../docs/board_lite_contract.md` and `../../docs/procise_integration_plan.md`.

## Reference commands

```powershell
python hardware/fpga/vectors/generate_vectors.py
python hardware/fpga/tb/run_rtl_compare.py
python -m pytest -q --ignore=tests/test_final_blind_test.py
```

The final command excludes the sealed-test-specific test module so this stage
does not instantiate or sample `final_blind_test`. Other project tests still
run. The RTL runner reports `SKIPPED` rather than fabricating results if no
Icarus simulator is installed.

See `docs/verification.md` before any synthesis work.
