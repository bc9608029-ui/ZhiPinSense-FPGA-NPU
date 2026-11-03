# fix9r2h5 baseline identity contract audit

## Scope

This hotfix changes only the metadata identity check used by the final 46-sample
Route-F acceptance gate. It does not change RF capture, synchronization, gain
recovery, thresholds, preprocessing, model inference, or class mapping.

## Root cause

`route_f_fix9r_exact_baseline.tsv` intentionally stores `original_sha256`, the
identity of the source RadioML sample. The D2 loader previously retained only
manifest column 20 (`quantized_sha256`) in `FrozenIq::sha256`. The final gate
therefore compared baseline `original_sha256` against the quantized ci16 SHA.
These identify different artifacts, so `baseline_identity_ok` was false even
when all 46 source indices, recovered samples, and predictions were correct.

Board evidence before this fix showed `scored=46`, `rf_excluded=0`,
`training_estimates=46`, `prediction_agreement=1.0`, and `rf_accuracy=1.0`, but
the aggregate token remained FAIL solely through the false identity bit.

## Fix

- `FrozenIq` now retains both `original_sha256` and the existing quantized
  artifact `sha256`.
- The D2 manifest loader reads and validates both hashes independently.
- Baseline identity compares original SHA to original SHA.
- Existing quantized-file content verification continues to use
  `FrozenIq::sha256`; its semantics are unchanged.

## Verification

- `test_iq_rf_loopback_23class`: 94 pass, 0 fail, including a regression that
  keeps original and quantized SHA values distinct.
- `host_tests/run_tests.sh`: ALL HOST TESTS PASSED.

The h4 46-sample RF evidence remains valid as measurement evidence. An official
PASS token requires rebuilding with this metadata fix and rerunning the gate so
the corrected fail-closed identity check is evaluated by the board binary.
