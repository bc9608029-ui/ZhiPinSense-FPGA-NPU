# Raw capture copy required for the last computer-only replay gate

Copy the complete directories, not only `results.json`:

```text
/root/amr_pair_validation_20261026_r1/capture
/root/amr_pair_validation_20261026_r2/capture
```

Expected content per directory includes 240 `NNNN.raw.npy` files.  Place them
under a computer directory of your choice and run:

```powershell
python scripts/replay_raw_capture.py `
  --capture-dir <r1_capture> `
  --board-results ..\amr_rescue_gmsk_candidate_20261026\validation_rf_r1\board_results.json `
  --out evidence\raw_replay_r1.json

python scripts/replay_raw_capture.py `
  --capture-dir <r2_capture> `
  --board-results ..\amr_rescue_gmsk_candidate_20261026\validation_rf_r2\board_results.json `
  --out evidence\raw_replay_r2.json
```

Both commands must report `matched=240`, `expected=240`, `status=PASS` before
changing the integration status to `OFFLINE_GATE_A_COMPLETE`.

