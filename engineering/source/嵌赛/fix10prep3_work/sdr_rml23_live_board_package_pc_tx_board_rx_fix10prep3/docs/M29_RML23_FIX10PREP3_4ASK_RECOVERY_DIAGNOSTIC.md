# fix10prep3 4ASK recovery diagnostic hotfix

## Purpose

Three unchanged real dual-SDR runs rejected the fixed 4ASK sample before NPU
classification with `PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH` (approximately 0.109,
0.111, and 0.150).  BPSK passed.  CFO, negative control, TX restore, and RX
restore passed.  This hotfix captures evidence without changing recovery or any
acceptance threshold.

## Changes

- Report payload-training correlation on the fractional timing grid.
- Report the payload-training-optimal fraction and the preamble correlation at
  that fraction.  These fields are diagnostic only and do not affect recovery.
- Add `--dump-failed-rx`.  On a fidelity-gate failure it writes
  `failed_rx_<source_index>.ci16` in explicit interleaved little-endian CI16 plus
  a JSON metadata file and SHA-256.
- Add `host_tools/replay_fix10_failed_rx.cpp`, which replays the exact C++
  recovery implementation off-board.  No Python DSP reimplementation is used.

## Red lines

The hotfix does not change the model, canonical frame, payload, RF thresholds,
`iq_rf_sync_recovery.hpp`, CFO ranges, control protocol, or classifier path.

## Board build

Overlay the patch at the root of an existing fix10prep3 full tree, then build:

```bash
cd /root/<fix10prep3-tree>
swapon /swapfile_fix10prep2 2>/dev/null || true
export LIBIIO_ROOT=/opt/sdr/libiio-0.26
nohup env LIBIIO_ROOT="$LIBIIO_ROOT" bash scripts/build_on_board.sh \
  > /root/fix10prep3_4ask_diag_build.log 2>&1 &
```

## Diagnostic run

Run the existing 4ASK-only command and add:

```text
--dump-failed-rx
```

The output directory must then contain `failed_rx_192513.ci16` and
`failed_rx_192513.json` on the observed failure.  Return both files for exact
offline replay.  Do not lower the residual threshold.

