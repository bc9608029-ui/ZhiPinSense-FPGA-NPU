# fix9r2h TX-scale contract audit

## Scope

This is a minimal correction on top of fix9r2g1. It does not change the model,
preprocessing, labels, synchronization, frame length, fidelity thresholds, or the
46-sample gate.

## Board evidence and root cause

The fix9r2g R8 run reached the deployed model (`scored=2`, `rf_excluded=0`) but
reported recovered-payload scale ratios of 2.115888 (BPSK) and 2.183607 (4ASK).
The two frozen payloads have complex RMS 1263.930964 and 1263.763129, hence
interleaved-component RMS 893.734156 and 893.615478. With
`--rf-tx-target-rms=2048`, the transfer applies known digital scales 2.291509 and
2.291813 before RF transmission.

The payload-domain pilot correctly estimated RF gain, but recovery removed only
that RF gain and did not remove the known digital payload scale. Consequently the
model received a tensor approximately twice the frozen RadioML amplitude. This is
a digital producer/consumer scale-contract defect, not a model defect.

The original pilot also used complex RMS 2048 while the transfer target is defined
over all interleaved I/Q components. Its per-component RMS was therefore only
1448.15, 3.01 dB below the target payload level.

## Correction

1. `PerFileRecovery::payload_tx_scale` records the exact scale applied to the
   payload before TX (default 1.0 for callers that do not scale).
2. The Route-F runner copies `RfTransferResultFix9r::tx_scale` into that field.
3. Both production `apply()` and diagnostic `provisional_apply_scalar()` divide
   by this scale after removing the RF complex gain. Invalid/non-finite/non-positive
   scales fail closed.
4. The deterministic pilot complex RMS is `sqrt(2)*2048`, so its interleaved I/Q
   component RMS matches the existing target-RMS contract.

No expected payload or label participates in the deployed recovery calculation.

## Verification

- `test_iq_rf_loopback_23class_fix9r2g`: 65 pass, 0 fail, including a new
  two-times digital-TX-scale round-trip regression.
- `test_iq_rf_loopback_23class_fix9r2a`: 38 pass, 0 fail.
- `test_iq_rf_fix9r2b`: 43 pass, 0 fail.
- Complete `host_tests/run_tests.sh`: `ALL HOST TESTS PASSED`.

The next permitted hardware action is the same two-sample BPSK/4ASK R8 smoke test.
The 46-sample accuracy run remains blocked until R8 reports `scored=2`,
`rf_excluded=0`, `prediction_agreement=2`, and payload scale error at most 0.05.
