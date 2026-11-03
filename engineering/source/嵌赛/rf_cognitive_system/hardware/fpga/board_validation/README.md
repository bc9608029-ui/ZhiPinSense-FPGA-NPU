# Lite board bit-exact validation package

This package reuses the already frozen deterministic corpus instead of making
a second copy:

- input: `../vectors/iq_input.hex` (`{Q[15:0], I[15:0]}` per line);
- expected raw features and INT8 tensor writes: `../vectors/expected_core.csv`;
- case metadata: `../vectors/manifest.json`;
- package hashes and quantizer settings: `manifest.json`.

The corpus contains 19 complete 1024-sample frames (19,456 complex samples),
including arithmetic edge cases and BPSK/QPSK/16QAM/64QAM at +20/0/-10 dB.
It does not load or evaluate the sealed final blind test.

## Capture rules

Replay words in file order. Capture raw feature rows only when the feature
pipeline output transfer is accepted. Capture tensor rows only when
`m_write_valid && m_write_ready`. Do not record idle cycles as rows.

Raw feature CSV requires:

```text
frame_id,sample_index,power,lag_re,lag_im
```

Tensor CSV requires:

```text
frame_id,sample_index,buffer_id,iq_i_int8,iq_q_int8,power_int8,lag_re_int8,lag_im_int8,iq_i_addr,iq_q_addr,power_addr,lag_re_addr,lag_im_addr
```

Optional tensor columns `frame_start,frame_done,frame_error,irq` are checked if
present. `frame_done` is a valid-qualified last-sample sideband; the accepted
completion event is `irq`.

## PASS/FAIL standard

PASS requires all of the following:

1. the three frozen source files match the SHA-256 values in the package;
2. exactly 19,456 ordered accepted rows are captured, without loss/duplication;
3. every Power/Lag and every INT8/address element matches exactly (zero LSB
   tolerance); first LagRe/LagIm of every frame are exactly zero;
4. buffer ID alternates by frame and optional boundary/IRQ fields match;
5. no unexpected frame error, overflow, or unaccounted saturation is reported.

Any missing/extra row, hash mismatch, sideband mismatch, or nonzero numerical
difference is FAIL. Run:

```powershell
python hardware/fpga/board_validation/compare_board_capture.py --self-test
python hardware/fpga/board_validation/compare_board_capture.py --features path/to/features.csv --tensor path/to/tensor.csv
```

`TODO-HARDWARE`: the capture transport (ILA, BRAM dump, PS utility, or confirmed
DMA path) is intentionally not fixed until the Procise/BSP examples are known.
