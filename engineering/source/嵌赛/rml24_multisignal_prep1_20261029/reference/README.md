# reference/ — read-only verbatim snapshots for offline replay

These files are **unmodified read-only copies** of the real production modules,
vendored only so the offline replay tests in `tests/test_real_entry_replay.py`
can run self-contained without importing from (or writing to) the A/B trees.

Provenance (all copied verbatim, no edits):

| File | Source tree (read-only) |
|------|-------------------------|
| `scan_runtime.py` | `rml24_scan_final_prep1_20261027/runtime/scan_runtime.py` (authoritative scan front-end: `ScanConfig`, `detect_public_training`, `scan_and_select`) |
| `receiver_core.py` | `rml24_scan_final_prep1_20261027/build_host/integration_assembled_final/rml24_final/runtime/receiver_core.py` (`CLASS_NAMES`, `tensorize`, `recover_frame`) |
| `candidate_two_dc.py` | `rml24_scan_final_prep1_20261027/build_host/integration_assembled_final/rml24_final/recovery/candidate_two_dc.py` (two-DC recovery + train/tail recipe) |
| `ui_event.py` | `rml24_mainchain_finalize1_20261028/candidate/runtime/ui_event.py` (final UI event adapter) |
| `standalone_control.py` | `rml24_mainchain_finalize1_20261028/candidate/runtime/standalone_control.py` (control server + `Controller`) |
| `scan_lock_policy.py` | `rml24_mainchain_finalize1_20261028/candidate/runtime/scan_lock_policy.py` (`LockHysteresis`) |

Note: `ui_event.py` imports `receiver_core.CLASS_NAMES`; the replay test adds this
`reference/` directory to `sys.path` so that import resolves to the vendored copy.

These snapshots are for OFFLINE replay only. The live entry still loads its own
copies from the board legacy root; nothing here changes the A/B trees.
